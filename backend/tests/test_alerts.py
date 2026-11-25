"""Pure rule transitions and API permission tests for the optional alert feature."""
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from fleetluma_backend.alerts import (
    RuleCreate, RuleEdit, make_alert_router, transition_for_sample,
)
from fleetluma_backend.operator_auth import require_operator


@pytest.mark.parametrize("current,threshold,required,previous,active,count,action", [
    (84.0, 85.0, 2, 0, False, 0, None),
    (90.0, 85.0, 2, 0, False, 1, None),
    (90.0, 85.0, 2, 1, False, 2, "OPEN"),
    (91.0, 85.0, 2, 2, True, 2, None),
    (65.0, 85.0, 2, 2, True, 0, "RESOLVE"),
    (65.0, 85.0, 2, 2, False, 0, None),
])
def test_threshold_transitions(current, threshold, required, previous,
                               active, count, action):
    assert transition_for_sample(current,threshold,required,previous,active) == (count,action)


def test_invalid_thresholds_fail_closed():
    with pytest.raises(ValidationError):
        RuleCreate(workspace_id=uuid4(),host_id=uuid4(),
                   metric="cpu_pct",threshold_pct=0)
    with pytest.raises(ValidationError):
        RuleCreate(workspace_id=uuid4(),host_id=uuid4(),
                   metric="unknown",threshold_pct=50)
    with pytest.raises(ValidationError):
        RuleEdit(consecutive_required=9)


def test_router_rejects_unauthenticated_operator(monkeypatch):
    monkeypatch.setenv("FLEETLUMA_MODE", "cloud")
    app = FastAPI()
    app.include_router(make_alert_router(store_factory=lambda: object()))
    with TestClient(app) as client:
        result = client.get("/api/v1/alerts/rules",
                            params={"workspace_id": str(uuid4())})
    assert result.status_code == 401


def test_router_maps_unauthorized_access_to_403_without_data_leak():
    class RejectingStore:
        def list_rules(self, actor, workspace_id):
            raise PermissionError("private membership information")
    app = FastAPI()
    app.include_router(make_alert_router(store_factory=RejectingStore))
    app.dependency_overrides[require_operator] = lambda: str(uuid4())
    with TestClient(app) as client:
        result = client.get("/api/v1/alerts/rules",
                            params={"workspace_id": str(uuid4())})
    assert result.status_code == 403
    assert "private membership information" not in result.text
