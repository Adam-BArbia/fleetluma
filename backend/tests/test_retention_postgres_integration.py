"""FL-36: verify 24-hour retention on isolated PostgreSQL, never live FleetLuma."""
from datetime import datetime, timedelta, timezone
import hashlib
import os
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row


def connect():
    return psycopg.connect(os.environ["FLEETLUMA_TEST_DATABASE_URL"],
                           row_factory=dict_row)


@pytest.mark.skipif(
    not os.getenv("FLEETLUMA_TEST_DATABASE_URL"),
    reason="Disposable PostgreSQL CI service required",
)
def test_retention_removes_only_older_monitoring_rows():
    host_id, service_id = str(uuid4()), str(uuid4())
    metrics = '{"cpu_pct":15,"ram_used_bytes":20,"ram_total_bytes":100,"disk_path":"/","disk_used_bytes":10,"disk_total_bytes":100}'
    now = datetime.now(timezone.utc)
    sample_ids = []
    check_ids = []
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT workspace_id FROM fleetluma.workspace_memberships "
                    "WHERE role='owner' LIMIT 1")
        workspace_id = cur.fetchone()["workspace_id"]
        cur.execute("""
          INSERT INTO fleetluma.hosts (id,name,os,token_hash,workspace_id)
          VALUES (%s,%s,'linux',%s,%s)
        """, (host_id, "retention-ci-" + host_id,
              hashlib.sha256(host_id.encode()).hexdigest(), workspace_id))
        cur.execute("""
          INSERT INTO fleetluma.services (id,name,url,enabled,workspace_id)
          VALUES (%s,'retention-ci-check','https://example.test/health',false,%s)
        """, (service_id, workspace_id))
        for age in (timedelta(hours=49), timedelta(hours=2)):
            cur.execute("""
              INSERT INTO fleetluma.samples
                (host_id,sampled_at,received_at,metrics)
              VALUES (%s,%s,%s,%s::jsonb) RETURNING id
            """, (host_id, now-age, now-age, metrics))
            sample_ids.append(cur.fetchone()["id"])
            cur.execute("""
              INSERT INTO fleetluma.service_checks
                (service_id,checked_at,status,http_code,latency_ms,failure_kind)
              VALUES (%s,%s,'HEALTHY',200,15,'none') RETURNING id
            """, (service_id, now-age))
            check_ids.append(cur.fetchone()["id"])

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM fleetluma.prune_expired_history()")
        counts = cur.fetchone()
        assert counts["samples_deleted"] >= 1
        assert counts["checks_deleted"] >= 1
        cur.execute("SELECT id FROM fleetluma.samples WHERE id=ANY(%s)",
                    (sample_ids,))
        assert {x["id"] for x in cur.fetchall()} == {sample_ids[1]}
        cur.execute("SELECT id FROM fleetluma.service_checks WHERE id=ANY(%s)",
                    (check_ids,))
        assert {x["id"] for x in cur.fetchall()} == {check_ids[1]}
        for role in ("anon", "authenticated"):
            cur.execute("""
              SELECT has_function_privilege(
                %s, 'fleetluma.prune_expired_history()', 'EXECUTE'
              ) AS allowed
            """, (role,))
            assert cur.fetchone()["allowed"] is False
        cur.execute("SELECT * FROM fleetluma.prune_expired_history()")
        again = cur.fetchone()
        assert again == {"samples_deleted": 0, "checks_deleted": 0}

    with connect() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM fleetluma.services WHERE id=%s", (service_id,))
        cur.execute("DELETE FROM fleetluma.hosts WHERE id=%s", (host_id,))
