"""FL-47: actual agent urllib client -> FastAPI -> isolated PostgreSQL.

Run only in the GitHub-hosted disposable PostgreSQL CI service. An in-process
HTTPS transport adapter avoids any external network requests and passes exact
HTTP requests through FastAPI TestClient. The live cloud/Supabase is untouched.
"""
import hashlib
import os
import sys
from pathlib import Path
from urllib import error
from unittest.mock import patch

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

# Use the production Python agent implementation, not a protocol rewrite.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agent"))
from fleetluma_agent.collector import build_report
from fleetluma_agent.pairing_client import PairingHttpClient
from fleetluma_agent.service_runtime import EnrollmentController

from fleetluma_backend.cloud_api import create_cloud_app
from fleetluma_backend.operator_auth import require_operator
from fleetluma_backend.pairing_store import PairingStore
from fleetluma_backend.postgres_store import PostgresStore

OWNER = "11111111-1111-4111-8111-111111111111"
EXISTING_TUFFEST = "22222222-2222-4222-8222-222222222222"
PEPPER = "full-stack-ci-only-pairing-pepper-not-for-prod"
HTTPS_ORIGIN = "https://fleetluma-ci.example.test"


def connect():
    return psycopg.connect(
        os.environ["FLEETLUMA_TEST_DATABASE_URL"], row_factory=dict_row)


class TransportResponse:
    def __init__(self, response):
        self.status = response.status_code
        self.data = response.content

    def read(self, maximum=-1):
        return self.data[:maximum] if maximum >= 0 else self.data

    def __enter__(self):
        return self

    def __exit__(self, typ, value, traceback):
        return False


class FastApiOpener:
    """Adapt urllib to the real API routes without opening any TCP socket."""
    def __init__(self, client):
        self.client = client

    def open(self, req, timeout=8):
        assert req.full_url.startswith(HTTPS_ORIGIN + "/")
        headers = dict(req.header_items())
        response = self.client.request(
            req.get_method(),
            req.full_url[len(HTTPS_ORIGIN):],
            content=req.data,
            headers=headers,
        )
        if response.status_code >= 400:
            raise error.HTTPError(
                req.full_url, response.status_code, "Request rejected",
                response.headers, None)
        return TransportResponse(response)


class VolatileServiceState:
    """Temporary identity repository, no user home or production secrets."""
    def __init__(self):
        self.identity = None

    def load(self):
        from fleetluma_agent.secure_state import CredentialMissing
        if self.identity is None:
            raise CredentialMissing()
        return self.identity

    def store(self, identity):
        if self.identity is not None:
            raise FileExistsError("Already paired")
        self.identity = identity


@pytest.mark.skipif(
    not os.environ.get("FLEETLUMA_TEST_DATABASE_URL"),
    reason="Requires isolated PostgreSQL test database",
)
def test_installed_agent_protocol_through_real_api_db_and_revocation(monkeypatch):
    monkeypatch.setenv("FLEETLUMA_MODE", "cloud")
    monkeypatch.setenv("FLEETLUMA_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("FLEETLUMA_DATABASE_URL",
                       os.environ["FLEETLUMA_TEST_DATABASE_URL"])
    monkeypatch.setenv("FLEETLUMA_OPERATOR_IDS", OWNER)
    monkeypatch.setenv("FLEETLUMA_WEB_ORIGINS", "https://fleetluma.example.test")
    monkeypatch.setenv("FLEETLUMA_PAIRING_ENABLED", "true")
    monkeypatch.setenv("FLEETLUMA_WORKSPACE_ENFORCEMENT_ENABLED", "true")
    monkeypatch.setenv("FLEETLUMA_PAIRING_PEPPER", PEPPER)
    app = create_cloud_app(
        store_factory=lambda: PostgresStore(connect=connect),
        pairing_store_factory=lambda pepper: PairingStore(
            pepper=pepper, connect=connect))
    # A real JWT verifier is independently tested; simulate already-verified
    # subject at the FastAPI auth dependency boundary.
    app.dependency_overrides[require_operator] = lambda: OWNER

    with TestClient(app) as api:
        workspace_response = api.get("/api/v1/operator/workspaces")
        assert workspace_response.status_code == 200
        workspace = workspace_response.json()["items"][0]["id"]
        assert workspace_response.json()["items"][0]["role"] == "owner"

        agent_client = PairingHttpClient(
            HTTPS_ORIGIN, opener=FastApiOpener(api))
        state = VolatileServiceState()
        clock = [100.0]
        enrollment = EnrollmentController(
            state, agent_client, clock=lambda: clock[0])

        with patch("fleetluma_agent.service_runtime.platform.system",
                   return_value="Linux"), patch(
                "fleetluma_agent.service_runtime.socket.gethostname",
                return_value="ci-e2e-linux"):
            pending = enrollment.begin("0.1.0")
        assert pending.status == "waiting"
        assert pending.user_code
        assert "device_code" not in repr(pending)
        assert "report_token" not in repr(pending)
        assert state.identity is None

        # Approval must be an explicit, reviewed operator action.
        result = api.post("/api/v1/operator/pairings/resolve", json={
            "user_code": pending.user_code})
        assert result.status_code == 200, result.text
        preview = result.json()
        assert preview["hostname"] == "ci-e2e-linux"
        assert preview["platform"] == "linux"
        assert "report_token" not in result.text
        assert "device_code" not in result.text

        approved = api.post(
            f"/api/v1/operator/pairings/{preview['pairing_id']}/approve",
            json={"workspace_id": workspace})
        assert approved.status_code == 200, approved.text

        clock[0] += 5
        final = enrollment.poll_once()
        assert final.status == "paired"
        assert state.identity.host_id == approved.json()["host_id"]
        assert state.identity.workspace_id == workspace
        assert len(state.identity.report_token) >= 40

        # Actual psutil collector payload, not a synthetic API request shape.
        report = build_report("/", include_processes=False)
        ingested = api.post(
            "/api/v1/agent/reports",
            json=report,
            headers={"Authorization": "Bearer " + state.identity.report_token})
        assert ingested.status_code == 202, ingested.text
        assert ingested.json()["host_id"] == state.identity.host_id
        visible = api.get("/api/v1/hosts", params={"workspace_id": workspace})
        assert visible.status_code == 200
        selected = next(h for h in visible.json()["items"]
                        if h["id"] == state.identity.host_id)
        assert selected["status"] == "CONNECTED"
        assert selected["latest_metrics"] is not None

        with connect() as db:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT count(*) AS total FROM fleetluma.samples "
                    "WHERE host_id=%s", (state.identity.host_id,))
                before_count = cur.fetchone()["total"]
                cur.execute(
                    "SELECT last_seen_at FROM fleetluma.hosts WHERE id=%s",
                    (state.identity.host_id,))
                before_seen = cur.fetchone()["last_seen_at"]

        revoked = api.post(
            f"/api/v1/operator/hosts/{state.identity.host_id}/revoke")
        assert revoked.status_code == 200
        rejected = api.post(
            "/api/v1/agent/reports", json=report,
            headers={"Authorization": "Bearer " + state.identity.report_token})
        assert rejected.status_code == 401
        with connect() as db:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT count(*) AS total FROM fleetluma.samples "
                    "WHERE host_id=%s", (state.identity.host_id,))
                assert cur.fetchone()["total"] == before_count
                cur.execute(
                    "SELECT last_seen_at FROM fleetluma.hosts WHERE id=%s",
                    (state.identity.host_id,))
                assert cur.fetchone()["last_seen_at"] == before_seen
                cur.execute(
                    "SELECT count(*) AS total FROM fleetluma.samples "
                    "WHERE host_id=%s", (EXISTING_TUFFEST,))
                assert cur.fetchone()["total"] == 1
        after = api.get("/api/v1/hosts", params={"workspace_id": workspace})
        target = next(x for x in after.json()["items"]
                      if x["id"] == state.identity.host_id)
        assert target["status"] == "REVOKED"
        assert "report_token" not in after.text
