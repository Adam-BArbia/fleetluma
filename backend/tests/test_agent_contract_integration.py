"""Real psutil agent payload -> FastAPI test client -> SQLite -> query.

This is an in-process integration test, not a two-computer or network deployment.
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "agent"))

from fleetluma_agent.collector import build_report
from fleetluma_backend.app import app, provision


def test_real_collector_report_to_coordinator(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        host_id = str(uuid4())
        secret = "local-demo-only-" + uuid4().hex
        monkeypatch.setenv("FLEETLUMA_DATABASE_PATH", str(Path(tmp) / "monitor.db"))
        monkeypatch.setenv("FLEETLUMA_HOSTS_JSON", json.dumps([{
            "id": host_id, "name": "qa-host", "os": "linux", "token": secret
        }]))
        provision()
        # Collect actual metrics from the CI host using psutil.
        # No mocks: the body comes from the same collector used by the agent.
        report = build_report(os.path.abspath(os.sep), include_processes=True)
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/agent/reports",
                headers={"Authorization": "Bearer " + secret},
                json=report,
            )
            assert resp.status_code == 202, resp.text
            assert resp.json()["host_id"] == host_id
            host = client.get("/api/v1/hosts/" + host_id)
            assert host.status_code == 200
            body = host.json()
            assert body["status"] == "CONNECTED"
            assert body["latest_metrics"]["cpu_pct"] >= 0
            assert body["latest_metrics"]["ram_total_bytes"] > 0
            assert body["latest_metrics"]["disk_total_bytes"] > 0
            assert len(client.get("/api/v1/hosts/" + host_id +
                                  "/history?window=15m").json()["items"]) == 1
            snapshot = client.get("/api/v1/hosts/" + host_id + "/processes").json()
            assert len(snapshot["processes"]) <= 10
            assert all(set(proc) == {"pid", "name", "cpu_pct", "memory_bytes"}
                       for proc in snapshot["processes"])
