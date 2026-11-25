"""Isolated PostgreSQL integration for optional FleetLuma alerts (FL-34).

The CI workflow applies FL-40 only to a disposable PostgreSQL container.
No production Supabase migration and no external network calls occur here.
"""
import hashlib
import os
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from fleetluma_backend.alerts import AlertStore, RuleCreate, RuleEdit
from fleetluma_backend.postgres_store import PostgresStore

OWNER = "11111111-1111-4111-8111-111111111111"


def connect():
    return psycopg.connect(os.environ["FLEETLUMA_TEST_DATABASE_URL"],
                           row_factory=dict_row)


@pytest.mark.skipif(
    not os.environ.get("FLEETLUMA_TEST_DATABASE_URL"),
    reason="Isolated PostgreSQL CI service required",
)
def test_real_agent_report_alert_lifecycle_and_workspace_permissions(monkeypatch):
    monkeypatch.setenv("FLEETLUMA_PAIRING_ENABLED", "true")
    monkeypatch.setenv("FLEETLUMA_ALERTS_ENABLED", "true")

    viewer = str(uuid4())
    outsider = str(uuid4())
    host_id = str(uuid4())
    token = "ci-report-only-token-not-used-in-production"
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT workspace_id FROM fleetluma.workspace_memberships "
                    "WHERE user_id=%s AND role='owner'", (OWNER,))
        workspace = str(cur.fetchone()["workspace_id"])
        cur.execute("INSERT INTO auth.users(id) VALUES(%s),(%s)", (viewer, outsider))
        cur.execute("""
            INSERT INTO fleetluma.workspace_memberships(workspace_id,user_id,role)
            VALUES(%s,%s,'viewer')
        """, (workspace, viewer))
        cur.execute("""
            INSERT INTO fleetluma.hosts(id,name,os,token_hash,workspace_id)
            VALUES(%s,'alert-ci-host','linux',%s,%s)
        """, (host_id, token_hash, workspace))

    rules = AlertStore(connect=connect)
    ingest = PostgresStore(connect=connect)
    cpu = rules.create_rule(OWNER, RuleCreate(
        workspace_id=workspace, host_id=host_id,
        metric="cpu_pct", threshold_pct=80, consecutive_required=2))
    ram = rules.create_rule(OWNER, RuleCreate(
        workspace_id=workspace, host_id=host_id,
        metric="ram_pct", threshold_pct=65, consecutive_required=1))
    assert len(rules.list_rules(viewer, workspace)) >= 2
    with pytest.raises(PermissionError):
        rules.create_rule(viewer, RuleCreate(
            workspace_id=workspace, host_id=host_id,
            metric="disk_pct", threshold_pct=60))
    with pytest.raises(PermissionError):
        rules.list_rules(outsider, workspace)
    with pytest.raises(PermissionError):
        rules.edit_rule(viewer, cpu["id"], RuleEdit(threshold_pct=90))
    # A non-member must not learn whether an arbitrary rule ID exists:
    # the scoped lookup deliberately returns 404 / KeyError.
    with pytest.raises(KeyError):
        rules.archive_rule(outsider, cpu["id"])

    def report(cpu_pct, ram_used, disk_used=10):
        metrics = {
            "cpu_pct": cpu_pct,
            "ram_used_bytes": ram_used, "ram_total_bytes": 100,
            "disk_path": "/", "disk_used_bytes": disk_used,
            "disk_total_bytes": 100,
        }
        return ingest.accept_report(
            token, datetime.now(timezone.utc), metrics)

    assert report(90, 40)["status"] == "accepted"
    assert rules.list_incidents(OWNER, workspace) == []

    # One consecutive CPU breach opens CPU, one high RAM sample opens RAM.
    assert report(92, 70)["status"] == "accepted"
    incidents = rules.list_incidents(OWNER, workspace)
    assert len(incidents) == 2
    opened = {i["metric"]: i for i in incidents}
    assert opened["cpu_pct"]["status"] == "OPEN"
    assert opened["ram_pct"]["status"] == "OPEN"

    # Further breaching samples must update existing incidents, not duplicate.
    assert report(95, 80)["status"] == "accepted"
    assert len(rules.list_incidents(OWNER, workspace)) == 2

    with pytest.raises(PermissionError):
        rules.acknowledge(viewer, opened["cpu_pct"]["id"])
    ack = rules.acknowledge(OWNER, opened["cpu_pct"]["id"])
    assert ack["status"] == "ACKNOWLEDGED"
    with pytest.raises(ValueError):
        rules.acknowledge(OWNER, opened["cpu_pct"]["id"])

    assert report(20, 20)["status"] == "accepted"
    resolved = {i["metric"]: i for i in rules.list_incidents(OWNER, workspace)}
    assert resolved["cpu_pct"]["status"] == "RESOLVED"
    assert resolved["ram_pct"]["status"] == "RESOLVED"
    assert resolved["cpu_pct"]["resolved_at"] is not None

    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
          SELECT event_type, count(*) AS n
          FROM fleetluma.incident_events e
          JOIN fleetluma.incidents i ON i.id=e.incident_id
          WHERE i.host_id=%s
          GROUP BY event_type
        """, (host_id,))
        events = {x["event_type"]: x["n"] for x in cur.fetchall()}
        assert events == {"OPENED": 2, "ACKNOWLEDGED": 1, "RESOLVED": 2}
        for table in ("alert_rules", "alert_rule_state", "incidents",
                      "incident_events"):
            cur.execute("""
              SELECT has_table_privilege('anon',%s,'SELECT') AS anon_read,
                     has_table_privilege('authenticated',%s,'SELECT') AS user_read
            """, (f"fleetluma.{table}", f"fleetluma.{table}"))
            row = cur.fetchone()
            assert row["anon_read"] is False
            assert row["user_read"] is False

    # Editing rules keeps history; archiving disables future evaluations.
    assert rules.edit_rule(OWNER, cpu["id"],
                           RuleEdit(threshold_pct=95))["threshold_pct"] == 95
    assert rules.archive_rule(OWNER, ram["id"]) == {"archived": True}
    assert report(98, 100)["status"] == "accepted"
    assert report(98, 100)["status"] == "accepted"
    recent = rules.list_incidents(OWNER, workspace)
    assert len(recent) == 3
    assert len([i for i in recent if i["status"] == "OPEN"]) == 1
    assert recent[0]["metric"] == "cpu_pct"

    # Editing an active threshold must retire the old incident and restart
    # consecutive-sample evaluation under the new rule configuration.
    assert rules.edit_rule(OWNER, cpu["id"],
                           RuleEdit(threshold_pct=97))["threshold_pct"] == 97
    assert not any(i["status"] in ("OPEN", "ACKNOWLEDGED")
                   for i in rules.list_incidents(OWNER, workspace))
    assert report(99, 30)["status"] == "accepted"
    assert not any(i["status"] == "OPEN"
                   for i in rules.list_incidents(OWNER, workspace))
    assert report(99, 30)["status"] == "accepted"
    assert len([i for i in rules.list_incidents(OWNER, workspace)
                if i["status"] == "OPEN"]) == 1

    # A revoked reporting credential cannot mutate metric or alert history.
    with connect() as conn, conn.cursor() as cur:
        cur.execute("UPDATE fleetluma.hosts SET lifecycle='REVOKED' WHERE id=%s",
                    (host_id,))
        cur.execute("SELECT count(*) AS n FROM fleetluma.incident_events")
        before_events = cur.fetchone()["n"]
    assert report(99, 99) is None
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM fleetluma.incident_events")
        assert cur.fetchone()["n"] == before_events
