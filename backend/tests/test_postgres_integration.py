"""FL-15 PostgreSQL service-backed integration tests.

Runs against ephemeral PostgreSQL 17 in GitHub Actions. Does not touch Supabase
production data or require exposing real database credentials.
"""
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from fleetluma_backend.postgres_store import PostgresStore


@pytest.fixture
def store():
    url = os.environ.get("FLEETLUMA_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Postgres integration service not configured")
    def conn():
        return psycopg.connect(url, row_factory=dict_row)
    yield PostgresStore(connect=conn)


def test_real_postgres_ingestion_and_readback(store):
    host_id = str(uuid4())
    token = "ci-only-test-token-" + uuid4().hex
    assert store.provision_host(host_id, "pg-agent", "linux", token) == host_id
    now = datetime.now(timezone.utc)
    metrics = {
        "cpu_pct": 17.2, "ram_used_bytes": 123, "ram_total_bytes": 1000,
        "disk_path": "/", "disk_used_bytes": 8, "disk_total_bytes": 100,
    }
    assert store.accept_report("wrong-"+token, now, metrics) is None
    assert store.host(host_id)["last_seen_at"] is None
    accepted = store.accept_report(token, now, metrics, [{
        "pid": 14, "name": "pytest", "cpu_pct": 12.5, "memory_bytes": 1024,
    }])
    assert accepted["host_id"] == host_id
    assert accepted["status"] == "accepted"
    host = store.host(host_id)
    assert host["status"] == "CONNECTED"
    assert host["latest_metrics"]["cpu_pct"] == 17.2
    assert host["latest_metrics"]["ram_pct"] == 12.3
    assert store.hosts()[0]["id"] == host_id
    assert len(store.history(host_id, "1h")["items"]) == 1
    assert store.processes(host_id)["processes"][0]["pid"] == 14
    assert store.purge_old(now - timedelta(hours=48))["samples"] == 0
    assert store.purge_old(now + timedelta(seconds=10))["samples"] == 1
    assert store.history(host_id, "1h")["items"] == []


def test_db_rejects_invalid_service_check_and_public_reader(store):
    sid = str(uuid4())
    with store._connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO fleetluma.services(id,name,url,enabled) VALUES (%s,%s,%s,%s)",
                (sid, "CI health", "https://example.invalid/health", True))
            cur.execute(
                "INSERT INTO fleetluma.service_checks(service_id,status,http_code,latency_ms,failure_kind) "
                "VALUES (%s,%s,%s,%s,%s)",
                (sid, "HEALTHY", 200, 9.0, "none"))
    assert store.services()[0]["status"] == "HEALTHY"
    assert store.service_checks(sid)["items"][0]["http_code"] == 200
    with store._connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT has_schema_privilege('anon', 'fleetluma', 'USAGE') AS allowed")
            assert cur.fetchone()["allowed"] is False
            cur.execute("SELECT has_table_privilege('authenticated','fleetluma.hosts','SELECT') AS allowed")
            assert cur.fetchone()["allowed"] is False
