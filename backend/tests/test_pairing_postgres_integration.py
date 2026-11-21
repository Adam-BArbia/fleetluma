"""FL-32 isolated PostgreSQL protocol acceptance tests; never touches Supabase prod."""
import hashlib
import os
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from fleetluma_backend.pairing_core import new_reporting_token
from fleetluma_backend.pairing_store import PairingFailure, PairingStore
from fleetluma_backend.postgres_store import PostgresStore

OWNER = "11111111-1111-4111-8111-111111111111"
TUFFEST = "22222222-2222-4222-8222-222222222222"
PEPPER = "ci-only-very-long-pairing-key-32-chars-min"


def _connection():
    return psycopg.connect(os.environ["FLEETLUMA_TEST_DATABASE_URL"],
                           row_factory=dict_row)


@pytest.fixture
def pairer():
    if not os.environ.get("FLEETLUMA_TEST_DATABASE_URL"):
        pytest.skip("Requires isolated PostgreSQL service")
    return PairingStore(pepper=PEPPER, connect=_connection)


def _request(store, name="integration-linux", key="ci-client"):
    token = new_reporting_token()
    result = store.create(
        hostname=name, platform="linux", agent_version="0.1.0",
        report_token_sha256=hashlib.sha256(token.encode()).hexdigest(),
        capabilities=["cpu","ram","disk","processes"], client_key=key,
    )
    return result, token


def test_preserves_existing_machine_metrics_and_private_grants(pairer):
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id,workspace_id,token_hash,lifecycle FROM fleetluma.hosts WHERE id=%s",
                        (TUFFEST,))
            row = cur.fetchone()
            assert row is not None
            assert row["lifecycle"] == "ACTIVE"
            assert row["token_hash"] == "a"*64
            assert row["workspace_id"] is not None
            cur.execute("SELECT count(*) AS n FROM fleetluma.samples WHERE host_id=%s", (TUFFEST,))
            assert cur.fetchone()["n"] == 1
            cur.execute("SELECT count(*) AS n FROM fleetluma.workspaces")
            assert cur.fetchone()["n"] == 1
            cur.execute("SELECT role FROM fleetluma.workspace_memberships WHERE user_id=%s",
                        (OWNER,))
            assert cur.fetchone()["role"] == "owner"
            cur.execute("SELECT has_schema_privilege('authenticated','fleetluma','USAGE') AS allowed")
            assert cur.fetchone()["allowed"] is False
            cur.execute("SELECT has_table_privilege('anon','fleetluma.pairing_sessions','SELECT') AS allowed")
            assert cur.fetchone()["allowed"] is False


def test_pairing_approve_poll_ingest_revoke_and_reject_old_token(pairer):
    operator_ws = pairer.workspaces(OWNER)["items"][0]["id"]
    ticket, token = _request(pairer)
    assert len(ticket["user_code"]) == 9
    assert ticket["expires_in"] == 600
    assert pairer.poll(ticket["device_code"]) == {"status": "pending"}

    # Wrong operator cannot resolve a pairing and unknown display codes do not
    # allow pairing. The real device code is never sent to the browser.
    with pytest.raises(PairingFailure) as denied:
        pairer.resolve(ticket["user_code"], str(uuid4()))
    assert denied.value.status == 403
    with pytest.raises(PairingFailure) as unknown:
        pairer.resolve("AAAA-AAAA", OWNER)
    assert unknown.value.status == 404

    reviewed = pairer.resolve(ticket["user_code"], OWNER)
    assert reviewed["platform"] == "linux"
    with pytest.raises(PairingFailure) as no_access:
        pairer.approve(reviewed["pairing_id"], str(uuid4()), OWNER)
    assert no_access.value.status == 403

    approval = pairer.approve(reviewed["pairing_id"], operator_ws, OWNER)
    assert approval["status"] == "approved"
    # Repeated approval by the same actor is idempotent; no duplicate host.
    assert pairer.approve(reviewed["pairing_id"], operator_ws, OWNER) == approval
    polled = pairer.poll(ticket["device_code"])
    assert polled == {"status": "paired", "host_id": approval["host_id"],
                      "workspace_id": operator_ws}
    assert pairer.poll(ticket["device_code"]) == polled

    store=PostgresStore(connect=_connection)
    metrics={"cpu_pct":11,"ram_used_bytes":100,"ram_total_bytes":1000,
             "disk_path":"/","disk_used_bytes":20,"disk_total_bytes":200}
    accepted=store.accept_report(token,datetime.now(timezone.utc),metrics)
    assert accepted["status"]=="accepted"
    assert store.host_scoped(approval["host_id"],OWNER)["status"]=="CONNECTED"
    assert len(store.history_scoped(approval["host_id"],"1h",OWNER)["items"])==1
    assert approval["host_id"] in {
        x["id"] for x in store.hosts_scoped(OWNER,operator_ws)
    }

    revoked=pairer.revoke(approval["host_id"],OWNER)
    assert revoked["status"]=="REVOKED"
    assert revoked["lifecycle"]=="REVOKED"
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT last_seen_at FROM fleetluma.hosts WHERE id=%s",
                        (approval["host_id"],))
            before=cur.fetchone()["last_seen_at"]
            cur.execute("SELECT count(*) AS n FROM fleetluma.samples WHERE host_id=%s",
                        (approval["host_id"],))
            count=cur.fetchone()["n"]
    assert store.accept_report(token,datetime.now(timezone.utc),metrics) is None
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT last_seen_at FROM fleetluma.hosts WHERE id=%s",
                        (approval["host_id"],))
            assert cur.fetchone()["last_seen_at"]==before
            cur.execute("SELECT count(*) AS n FROM fleetluma.samples WHERE host_id=%s",
                        (approval["host_id"],))
            assert cur.fetchone()["n"]==count


def test_unreviewed_id_cannot_approve_and_cancelled_code_cannot_pair(pairer):
    workspace=pairer.workspaces(OWNER)["items"][0]["id"]
    ticket,token=_request(pairer,name="test-cancel",key="ci-client-cancel")
    # Session UUID by itself provides no approval capability.
    arbitrary=str(uuid4())
    with pytest.raises(PairingFailure) as err:
        pairer.approve(arbitrary,workspace,OWNER)
    assert err.value.status==403
    pairer.cancel(ticket["device_code"])
    with pytest.raises(PairingFailure) as err:
        pairer.poll(ticket["device_code"])
    assert err.value.status==410


def test_rate_limit_denied_requests_persist(pairer):
    # Independent admin avoids coupling to previous tests' rate limit state.
    admin=str(uuid4())
    workspace=pairer.workspaces(OWNER)["items"][0]["id"]
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO auth.users(id) VALUES (%s)",(admin,))
            cur.execute("""
              INSERT INTO fleetluma.workspace_memberships(workspace_id,user_id,role)
              VALUES(%s,%s,'admin')
            """,(workspace,admin))
    for i in range(10):
        with pytest.raises(PairingFailure) as err:
            pairer.resolve("AAAA-AAAA",admin)
        assert err.value.status==404
    with pytest.raises(PairingFailure) as limit:
        pairer.resolve("AAAA-AAAA",admin)
    assert limit.value.status==429
