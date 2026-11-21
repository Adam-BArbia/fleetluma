"""FL-32: pairing is gated and operator approval never requires an agent secret."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from fleetluma_backend.cloud_api import create_cloud_app
from fleetluma_backend.operator_auth import require_operator

PEPPER = "ci-only-32-character-private-pepper-for-tests"
WORKSPACE = str(uuid4())
OPERATOR = str(uuid4())
HOST = str(uuid4())
PAIRING = str(uuid4())


class FakeLegacyStore:
    def ping(self): return True
    def hosts(self): return []
    def services(self): return []
    def host(self, host_id): return None


class FakePairingStore:
    instances = []
    def __init__(self, pepper):
        assert pepper == PEPPER
        self.calls = []
        self.instances.append(self)

    def create(self, **kwargs):
        self.calls.append(("create", kwargs))
        return {"device_code": "private-device-code-not-display-123456789",
                "user_code": "ABCD-7294",
                "verification_uri": "https://fleetluma-web.vercel.app/devices/pair",
                "expires_in": 600, "interval": 5}

    def poll(self, device_code):
        assert device_code == "private-device-code-not-display-123456789"
        return {"status": "pending"}

    def resolve(self, code, actor):
        assert code == "ABCD-7294" and actor == OPERATOR
        return {"pairing_id": PAIRING, "hostname": "TUFFEST", "platform": "windows",
                "agent_version": "0.1.0", "capabilities": ["cpu","ram"],
                "expires_at": "2026-11-21T01:00:00Z"}

    def approve(self, pairing_id, workspace_id, actor):
        assert (pairing_id, workspace_id, actor) == (PAIRING, WORKSPACE, OPERATOR)
        return {"status": "approved", "host_id": HOST, "workspace_id": WORKSPACE}

    def workspaces(self, actor):
        assert actor == OPERATOR
        return {"items": [{"id": WORKSPACE, "name": "Personal Fleet", "role": "owner"}]}

    def managed_hosts(self, workspace, actor):
        assert workspace == WORKSPACE and actor == OPERATOR
        return {"items": []}


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("FLEETLUMA_MODE", "cloud")
    monkeypatch.setenv("FLEETLUMA_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("FLEETLUMA_DATABASE_URL", "postgresql://no-real-secrets")
    monkeypatch.setenv("FLEETLUMA_OPERATOR_IDS", OPERATOR)
    monkeypatch.setenv("FLEETLUMA_WEB_ORIGINS", "https://fleetluma.example.test")
    monkeypatch.setenv("FLEETLUMA_PAIRING_PEPPER", PEPPER)


def _app():
    return create_cloud_app(store_factory=FakeLegacyStore,
                            pairing_store_factory=FakePairingStore)


def test_pairing_disabled_by_default(env, monkeypatch):
    monkeypatch.delenv("FLEETLUMA_PAIRING_ENABLED", raising=False)
    app = _app()
    assert TestClient(app).post("/api/v1/agent/pairings", json={}).status_code == 404


def test_pairing_fails_closed_if_workspace_enforcement_missing(env, monkeypatch):
    monkeypatch.setenv("FLEETLUMA_PAIRING_ENABLED", "true")
    monkeypatch.delenv("FLEETLUMA_WORKSPACE_ENFORCEMENT_ENABLED", raising=False)
    with pytest.raises(RuntimeError, match="workspace"):
        _app()


def test_pairing_fails_closed_if_key_missing(env, monkeypatch):
    monkeypatch.setenv("FLEETLUMA_PAIRING_ENABLED", "true")
    monkeypatch.setenv("FLEETLUMA_WORKSPACE_ENFORCEMENT_ENABLED", "true")
    monkeypatch.delenv("FLEETLUMA_PAIRING_PEPPER")
    with pytest.raises(RuntimeError, match="HMAC"):
        _app()


def test_pairing_routes_are_not_operator_credentials(env, monkeypatch):
    monkeypatch.setenv("FLEETLUMA_PAIRING_ENABLED", "true")
    monkeypatch.setenv("FLEETLUMA_WORKSPACE_ENFORCEMENT_ENABLED", "true")
    with TestClient(_app()) as client:
        payload = {
            "hostname": "TUFFEST", "platform": "windows",
            "agent_version": "0.1.0", "report_token_sha256": "a"*64,
            "capabilities": ["cpu", "ram"],
        }
        result = client.post("/api/v1/agent/pairings", json=payload)
        assert result.status_code == 201, result.text
        assert result.json()["user_code"] == "ABCD-7294"
        # Agent's pairing session secret is only for polling.
        poll = client.post("/api/v1/agent/pairings/token", json={
            "device_code": result.json()["device_code"]
        })
        assert poll.status_code == 200 and poll.json()["status"] == "pending"
        assert client.post("/api/v1/operator/pairings/resolve",
                           json={"user_code": "ABCD-7294"}).status_code == 401
        assert client.get("/api/v1/operator/workspaces").status_code == 401
        # A browser from an untrusted origin cannot preflight approval.
        preflight=client.options("/api/v1/operator/pairings/resolve",headers={
            "Origin": "https://attacker.invalid",
            "Access-Control-Request-Method": "POST",
        })
        assert preflight.status_code == 400


def test_owner_can_review_and_approve_via_separate_jwt(env, monkeypatch):
    monkeypatch.setenv("FLEETLUMA_PAIRING_ENABLED", "true")
    monkeypatch.setenv("FLEETLUMA_WORKSPACE_ENFORCEMENT_ENABLED", "true")
    app = _app()
    app.dependency_overrides[require_operator] = lambda: OPERATOR
    with TestClient(app) as client:
        ws = client.get("/api/v1/operator/workspaces")
        assert ws.status_code == 200
        resolve = client.post("/api/v1/operator/pairings/resolve",
                              json={"user_code": "ABCD-7294"})
        assert resolve.status_code == 200
        approved = client.post(f"/api/v1/operator/pairings/{PAIRING}/approve",
                               json={"workspace_id": WORKSPACE})
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        # The operator never receives the private reporting credential.
        assert "device_code" not in approved.text
        assert "report_token" not in approved.text
        assert client.get("/api/v1/operator/hosts?workspace_id=" + WORKSPACE).status_code == 200
        assert client.get("/api/v1/hosts").status_code == 422
