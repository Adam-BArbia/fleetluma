"""FL-48: host detail endpoints must not reveal other workspace host IDs."""
from uuid import uuid4

from fastapi.testclient import TestClient

from fleetluma_backend.cloud_api import create_cloud_app
from fleetluma_backend.operator_auth import require_operator


OPERATOR = str(uuid4())
VISIBLE = str(uuid4())
FOREIGN = str(uuid4())


class ScopedHostStore:
    def __init__(self):
        self.unscoped_host_reads = 0

    def host(self, host_id):
        self.unscoped_host_reads += 1
        raise AssertionError("Never perform an unscoped host lookup in pairing mode")

    def host_scoped(self, host_id, operator):
        assert operator == OPERATOR
        if host_id == VISIBLE:
            return {"id": VISIBLE, "status": "CONNECTED"}
        return None

    def history_scoped(self, host_id, window, operator):
        assert host_id == VISIBLE and operator == OPERATOR
        return {"host_id": VISIBLE, "window": window, "items": []}

    def processes_scoped(self, host_id, operator):
        assert host_id == VISIBLE and operator == OPERATOR
        return {"host_id": VISIBLE, "captured_at": None, "processes": []}


def test_host_details_are_not_enumerable_cross_workspace(monkeypatch):
    monkeypatch.setenv("FLEETLUMA_MODE", "cloud")
    monkeypatch.setenv("FLEETLUMA_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("FLEETLUMA_DATABASE_URL", "postgresql://ci-only")
    monkeypatch.setenv("FLEETLUMA_OPERATOR_IDS", OPERATOR)
    monkeypatch.setenv("FLEETLUMA_PAIRING_ENABLED", "true")
    monkeypatch.setenv("FLEETLUMA_WORKSPACE_ENFORCEMENT_ENABLED", "true")
    monkeypatch.setenv("FLEETLUMA_PAIRING_PEPPER", "isolated-ci-pepper-32-or-more-characters")
    instances = []
    def factory():
        item = ScopedHostStore()
        instances.append(item)
        return item
    app = create_cloud_app(store_factory=factory)
    app.dependency_overrides[require_operator] = lambda: OPERATOR
    with TestClient(app) as client:
        for host_id in (FOREIGN, str(uuid4())):
            for route in (f"/api/v1/hosts/{host_id}",
                          f"/api/v1/hosts/{host_id}/history",
                          f"/api/v1/hosts/{host_id}/processes"):
                result = client.get(route)
                assert result.status_code == 404, (route, result.text)
                assert result.json()["error"]["message"] == "Unknown host"
        assert client.get(f"/api/v1/hosts/{VISIBLE}").status_code == 200
        assert client.get(f"/api/v1/hosts/{VISIBLE}/history").status_code == 200
        assert client.get(f"/api/v1/hosts/{VISIBLE}/processes").status_code == 200
    assert all(s.unscoped_host_reads == 0 for s in instances)
