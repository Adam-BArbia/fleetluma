"""FL-32 HTTP enrollment endpoints (feature-gated until full rollout).

Design-only routes have no operational effect unless the cloud app explicitly
enables the feature and the private migration/authorization gates are ready.
"""
from __future__ import annotations

import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .operator_auth import require_operator
from .pairing_store import PairingFailure, PairingStore


class PairingCreateRequest(BaseModel):
    hostname: str = Field(min_length=1, max_length=64)
    platform: Literal["windows", "linux"]
    agent_version: str = Field(min_length=1, max_length=64)
    report_token_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    capabilities: list[str] = Field(default_factory=list, max_length=20)


class DeviceCodeRequest(BaseModel):
    device_code: str = Field(min_length=32, max_length=256)


class ResolveCodeRequest(BaseModel):
    user_code: str = Field(min_length=8, max_length=9)


class ApprovePairingRequest(BaseModel):
    workspace_id: str


class RenameHostRequest(BaseModel):
    name: str = Field(min_length=2, max_length=64)


def make_pairing_router(store_factory=PairingStore):
    """Factory injected for deterministic tests, no global connection object."""
    router = APIRouter()

    def store():
        pepper = os.environ.get("FLEETLUMA_PAIRING_PEPPER", "")
        if len(pepper) < 32:
            # Do not expose underlying configuration to the HTTP caller.
            raise HTTPException(503, "Enrollment is not configured")
        return store_factory(pepper=pepper)

    def guarded(call):
        try:
            return call()
        except PairingFailure as exc:
            raise HTTPException(exc.status, str(exc)) from None

    @router.post("/api/v1/agent/pairings", status_code=201)
    def start_pairing(body: PairingCreateRequest, request: Request):
        # Never trust an unverified user-controlled X-Forwarded-For header.
        # This key supplements a global DB request cap, not a security identity.
        peer = request.client.host if request.client else "unknown"
        return guarded(lambda: store().create(
            hostname=body.hostname, platform=body.platform,
            agent_version=body.agent_version,
            report_token_sha256=body.report_token_sha256,
            capabilities=body.capabilities, client_key=peer,
        ))

    @router.post("/api/v1/agent/pairings/token")
    def poll_pairing(body: DeviceCodeRequest):
        return guarded(lambda: store().poll(body.device_code))

    @router.post("/api/v1/agent/pairings/cancel", status_code=204)
    def cancel_pairing(body: DeviceCodeRequest):
        guarded(lambda: store().cancel(body.device_code))
        return None

    @router.get("/api/v1/operator/workspaces")
    def list_workspaces(operator: str = Depends(require_operator)):
        return guarded(lambda: store().workspaces(operator))

    @router.post("/api/v1/operator/pairings/resolve")
    def resolve_pairing(body: ResolveCodeRequest,
                        operator: str = Depends(require_operator)):
        return guarded(lambda: store().resolve(body.user_code, operator))

    @router.post("/api/v1/operator/pairings/{id}/approve")
    def approve_pairing(id: str, body: ApprovePairingRequest,
                        operator: str = Depends(require_operator)):
        return guarded(lambda: store().approve(id, body.workspace_id, operator))

    @router.post("/api/v1/operator/pairings/{id}/deny", status_code=204)
    def deny_pairing(id: str, operator: str = Depends(require_operator)):
        guarded(lambda: store().deny(id, operator))
        return None

    @router.get("/api/v1/operator/hosts")
    def list_managed_hosts(workspace_id: str = Query(...),
                           operator: str = Depends(require_operator)):
        return guarded(lambda: store().managed_hosts(workspace_id, operator))

    @router.patch("/api/v1/operator/hosts/{id}")
    def rename_host(id: str, body: RenameHostRequest,
                    operator: str = Depends(require_operator)):
        return guarded(lambda: store().rename(id, body.name, operator))

    @router.post("/api/v1/operator/hosts/{id}/revoke")
    def revoke_host(id: str, operator: str = Depends(require_operator)):
        return guarded(lambda: store().revoke(id, operator))

    @router.get("/api/v1/operator/device-audit")
    def device_audit(workspace_id: str = Query(...), limit: int = Query(50, ge=1, le=100),
                     operator: str = Depends(require_operator)):
        return guarded(lambda: store().audit(workspace_id, operator, limit))

    return router
