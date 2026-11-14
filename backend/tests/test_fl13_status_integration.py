"""FL-13: deterministic in-process behavior for multiple provisioned hosts.

These are automated contract/regression tests, not a real two-PC LAN demo.
"""
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from fleetluma_backend import app as backend


def test_two_distinct_tokens_and_heartbeat_staleness(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        a, b = str(uuid4()), str(uuid4())
        monkeypatch.setenv("FLEETLUMA_DATABASE_PATH", os.path.join(tmp, "fleet.db"))
        monkeypatch.setenv("FLEETLUMA_HOSTS_JSON", json.dumps([
            {"id": a, "name": "host-a", "os": "linux", "token": "token-a-" + a},
            {"id": b, "name": "host-b", "os": "windows", "token": "token-b-" + b},
        ]))
        backend.provision()
        report = {"sampled_at": datetime.now(timezone.utc).isoformat(),
                  "metrics": {"cpu_pct": 19, "ram_used_bytes": 20, "ram_total_bytes": 100,
                              "disk_path": "/", "disk_used_bytes": 50,
                              "disk_total_bytes": 100}}
        with TestClient(backend.app) as client:
            before = client.get("/api/v1/hosts").json()["items"]
            assert len(before) == 2
            assert {host["status"] for host in before} == {"PENDING"}
            assert client.post("/api/v1/agent/reports", json=report,
                               headers={"Authorization": "Bearer token-a-" + a}).json()["host_id"] == a
            assert client.post("/api/v1/agent/reports", json=report,
                               headers={"Authorization": "Bearer token-b-" + b}).json()["host_id"] == b
            connected = client.get("/api/v1/hosts").json()["items"]
            assert all(h["status"] == "CONNECTED" for h in connected)
            seen_b = next(h["last_seen_at"] for h in connected if h["id"] == b)
            assert client.post("/api/v1/agent/reports", json=report,
                               headers={"Authorization": "Bearer wrong-token"}).status_code == 401
            assert client.get("/api/v1/hosts/" + b).json()["last_seen_at"] == seen_b
            # Simulate silence via a previous server-generated timestamp: no waiting required.
            with backend.db() as conn:
                conn.execute("UPDATE hosts SET last_seen_at=? WHERE id=?",
                             (backend.stamp(backend.utcnow() - timedelta(seconds=45)), b))
            result = {h["id"]: h for h in client.get("/api/v1/hosts").json()["items"]}
            assert result[a]["status"] == "CONNECTED"
            assert result[b]["status"] == "STALE"
            # Recovery is an actual accepted report, not a manual status flip.
            assert client.post("/api/v1/agent/reports", json=report,
                               headers={"Authorization": "Bearer token-b-" + b}).status_code == 202
            assert client.get("/api/v1/hosts/" + b).json()["status"] == "CONNECTED"
