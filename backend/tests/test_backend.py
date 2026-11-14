import json
import os
import tempfile
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from fleetluma_backend.app import app, provision


@pytest.fixture
def client(monkeypatch):
    with tempfile.TemporaryDirectory() as temp:
        host_id = str(uuid4())
        monkeypatch.setenv("FLEETLUMA_DATABASE_PATH", os.path.join(temp, "test.db"))
        monkeypatch.setenv("FLEETLUMA_HOSTS_JSON", json.dumps([{
            "id": host_id, "name": "test-linux", "os": "linux",
            "token": "demo-token-at-least-16-chars"}]))
        provision()
        with TestClient(app) as api:
            yield api, host_id


REPORT = {"sampled_at": "2026-11-14T11:30:00Z",
          "metrics": {"cpu_pct": 25, "ram_used_bytes": 20, "ram_total_bytes": 100,
                      "disk_path": "/", "disk_used_bytes": 50, "disk_total_bytes": 100},
          "processes": [{"pid": 123, "name": "demo", "cpu_pct": 110, "memory_bytes": 1234}]}


def test_authentication_and_storage(client):
    api, host_id = client
    assert api.get("/api/v1/hosts").json()["items"][0]["status"] == "PENDING"
    assert api.post("/api/v1/agent/reports", json=REPORT).status_code == 401
    assert api.get("/api/v1/hosts").json()["items"][0]["last_seen_at"] is None
    headers = {"Authorization": "Bearer demo-token-at-least-16-chars"}
    r = api.post("/api/v1/agent/reports", json=REPORT, headers=headers)
    assert r.status_code == 202, r.text
    assert r.json()["host_id"] == host_id
    host = api.get("/api/v1/hosts/" + host_id).json()
    assert host["status"] == "CONNECTED"
    assert host["latest_metrics"]["ram_pct"] == 20
    assert len(api.get("/api/v1/hosts/" + host_id + "/history?window=24h").json()["items"]) == 1
    assert api.get("/api/v1/hosts/" + host_id + "/processes").json()["processes"][0]["pid"] == 123


def test_validation_does_not_refresh_heartbeat(client):
    api, host_id = client
    headers = {"Authorization": "Bearer demo-token-at-least-16-chars"}
    bad = {**REPORT, "metrics": {**REPORT["metrics"], "cpu_pct": 101}}
    assert api.post("/api/v1/agent/reports", json=bad, headers=headers).status_code == 422
    assert api.get("/api/v1/hosts/" + host_id).json()["last_seen_at"] is None
    assert api.get("/api/v1/hosts/bad-id").status_code == 404
