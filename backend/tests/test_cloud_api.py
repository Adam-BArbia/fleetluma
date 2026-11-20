"""FL-16: hosted entry point is isolated from local SQLite startup."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from fleetluma_backend.cloud_api import create_cloud_app
from fleetluma_backend.operator_auth import require_operator


@pytest.fixture
def environment(monkeypatch):
    monkeypatch.setenv("FLEETLUMA_MODE", "cloud")
    monkeypatch.setenv("FLEETLUMA_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("FLEETLUMA_DATABASE_URL", "postgresql://no_real_credentials")
    monkeypatch.setenv("FLEETLUMA_WEB_ORIGINS", "https://fleetluma.example.test")
    monkeypatch.setenv("FLEETLUMA_OPERATOR_IDS", str(uuid4()))


class FakeStore:
    def ping(self): return True
    def hosts(self): return []
    def host(self, host_id): return None
    def services(self): return []
    def accept_report(self, token, sampled_at, metrics, processes=None):
        if token != "ci-fleetluma-agent-valid-token": return None
        return {"host_id": str(uuid4()), "received_at": "2026-11-14T12:00:00Z", "status": "accepted"}


def test_cloud_mode_fails_closed_without_configuration(monkeypatch):
    monkeypatch.delenv("FLEETLUMA_MODE", raising=False)
    with pytest.raises(RuntimeError):
        create_cloud_app()


def test_unauthorized_cloud_read_is_blocked(environment):
    client = TestClient(create_cloud_app(store_factory=FakeStore))
    assert client.get("/api/v1/hosts").status_code == 401
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/services").status_code == 401


def test_authorized_reads_and_separate_agent_token(environment):
    app = create_cloud_app(store_factory=FakeStore)
    app.dependency_overrides[require_operator] = lambda: "test-operator"
    with TestClient(app) as client:
        assert client.get("/api/v1/hosts").json()["items"] == []
        assert client.get("/api/v1/hosts/missing").status_code == 404
        payload = {
            "sampled_at": "2026-11-14T12:00:00Z",
            "metrics": {"cpu_pct": 20, "ram_used_bytes": 100,
                        "ram_total_bytes": 1000, "disk_path": "/",
                        "disk_used_bytes": 250, "disk_total_bytes": 500},
        }
        assert client.post("/api/v1/agent/reports", json=payload).status_code == 401
        result = client.post("/api/v1/agent/reports", json=payload,
            headers={"Authorization": "Bearer ci-fleetluma-agent-valid-token"})
        assert result.status_code == 202, result.text


def test_cloud_cors_is_allowlisted(environment):
    client = TestClient(create_cloud_app(store_factory=FakeStore))
    headers = {"Origin": "https://fleetluma.example.test",
               "Access-Control-Request-Method": "GET"}
    ok = client.options("/api/v1/hosts", headers=headers)
    assert ok.status_code == 200
    assert ok.headers["access-control-allow-origin"] == headers["Origin"]
    blocked = client.options("/api/v1/hosts",
        headers={**headers,"Origin": "https://untrusted.example.test"})
    assert blocked.status_code == 400


def test_health_is_unavailable_without_database(environment):
    class BrokenStore(FakeStore):
        def ping(self):
            raise ConnectionError("private DB connection string should never leak")
    client = TestClient(create_cloud_app(store_factory=BrokenStore))
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "mode": "cloud"}
    assert "connection string" not in response.text


def test_health_rejects_failed_database_probe(environment):
    class DownStore(FakeStore):
        def ping(self): return False
    client = TestClient(create_cloud_app(store_factory=DownStore))
    assert client.get("/health").status_code == 503


def test_cloud_api_only_preview_disables_cors_until_web_origin_known(environment, monkeypatch):
    monkeypatch.delenv("FLEETLUMA_WEB_ORIGINS", raising=False)
    client = TestClient(create_cloud_app(store_factory=FakeStore))
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/hosts").status_code == 401
    response = client.options("/api/v1/hosts", headers={
        "Origin": "https://untrusted.example.test",
        "Access-Control-Request-Method": "GET",
    })
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("origin", [
    "http://fleetluma.example.test",
    "https://user@fleetluma.example.test",
    "https://fleetluma.example.test:8443",
    "https://fleetluma.example.test/path",
    "https://fleetluma.example.test?token=value",
    "https://fleetluma.example.test#part",
    "https://*.example.test",
])
def test_cloud_cors_rejects_invalid_origins(environment, monkeypatch, origin):
    monkeypatch.setenv("FLEETLUMA_WEB_ORIGINS", origin)
    with pytest.raises(RuntimeError, match="CORS"):
        create_cloud_app(store_factory=FakeStore)
