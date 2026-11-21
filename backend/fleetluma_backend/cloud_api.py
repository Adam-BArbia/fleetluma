"""FL-16: Vercel FastAPI entrypoint with Postgres and fail-closed operator auth.

Unlike local app.py, this module never runs SQLite initialization or a
background HTTP-checking thread. Monitoring probes are tracked separately.
"""
import os
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse

from .contracts import Report
from .operator_auth import require_operator, configure_cors, cloud_mode, issuer, allowed_operators
from .postgres_store import PostgresStore


def create_cloud_app(store_factory=PostgresStore):
    if not cloud_mode():
        raise RuntimeError("Vercel API refuses to start unless FLEETLUMA_MODE=cloud")
    issuer()
    allowed_operators()
    if not os.environ.get("FLEETLUMA_DATABASE_URL"):
        raise RuntimeError("Cloud API requires FLEETLUMA_DATABASE_URL")

    # Do not expose enrollment until database migration and workspace scoping land.
    pairing_enabled = os.environ.get("FLEETLUMA_PAIRING_ENABLED") == "true"
    if pairing_enabled and os.environ.get("FLEETLUMA_WORKSPACE_ENFORCEMENT_ENABLED") != "true":
        raise RuntimeError("Pairing requires fully enforced workspace-scoped API")
    if pairing_enabled and len(os.environ.get("FLEETLUMA_PAIRING_PEPPER", "")) < 32:
        raise RuntimeError("Pairing requires private secure HMAC secret")

    app = FastAPI(title="FleetLuma Cloud API", version="0.1.0")
    configure_cors(app)
    if pairing_enabled:
        from .pairing_routes import make_pairing_router
        app.include_router(make_pairing_router())

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        code = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND",
                409: "CONFLICT", 410: "EXPIRED", 429: "RATE_LIMITED",
                503: "UNAVAILABLE", 422: "INVALID_REQUEST"}.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(status_code=exc.status_code,
                            content={"error": {"code": code, "message": str(exc.detail)}})

    @app.post("/api/v1/agent/reports", status_code=202)
    def agent_report(report: Report, authorization: str | None = Header(default=None)):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Agent authentication required")
        token = authorization[len("Bearer "):].strip()
        if len(token) < 16:
            raise HTTPException(401, "Agent authentication required")
        accepted = store_factory().accept_report(
            token, report.sampled_at, report.metrics.model_dump(),
            [process.model_dump() for process in report.processes]
            if report.processes is not None else None,
        )
        if not accepted:
            raise HTTPException(401, "Agent authentication required")
        return accepted

    @app.get("/api/v1/hosts")
    def hosts(workspace_id: str | None = Query(default=None),
              operator: str = Depends(require_operator)):
        if pairing_enabled:
            if not workspace_id:
                raise HTTPException(422, "workspace_id is required")
            try:
                return {"items": store_factory().hosts_scoped(operator, workspace_id)}
            except ValueError:
                raise HTTPException(422, "Invalid workspace identifier") from None
            except PermissionError:
                raise HTTPException(403, "Workspace access denied") from None
        return {"items": store_factory().hosts()}

    @app.get("/api/v1/hosts/{id}")
    def host(id: str, operator: str = Depends(require_operator)):
        try:
            row = (store_factory().host_scoped(id, operator)
                   if pairing_enabled else store_factory().host(id))
        except ValueError:
            row = None
        if row is None:
            raise HTTPException(404, "Unknown host")
        return row

    @app.get("/api/v1/hosts/{id}/history")
    def history(id: str, window: str = Query(default="1h", pattern="^(15m|1h|24h)$"),
                operator: str = Depends(require_operator)):
        try:
            row = store_factory().host(id)
        except ValueError:
            row = None
        if row is None:
            raise HTTPException(404, "Unknown host")
        return (store_factory().history_scoped(id, window, operator)
                if pairing_enabled else store_factory().history(id, window))

    @app.get("/api/v1/hosts/{id}/processes")
    def processes(id: str, operator: str = Depends(require_operator)):
        try:
            row = store_factory().host(id)
        except ValueError:
            row = None
        if row is None:
            raise HTTPException(404, "Unknown host")
        return (store_factory().processes_scoped(id, operator)
                if pairing_enabled else store_factory().processes(id))

    @app.get("/api/v1/services")
    def services(workspace_id: str | None = Query(default=None),
                 operator: str = Depends(require_operator)):
        if pairing_enabled:
            if not workspace_id:
                raise HTTPException(422, "workspace_id is required")
            try:
                return {"items": store_factory().services_scoped(operator, workspace_id)}
            except ValueError:
                raise HTTPException(422, "Invalid workspace identifier") from None
            except PermissionError:
                raise HTTPException(403, "Workspace access denied") from None
        return {"items": store_factory().services()}

    @app.get("/api/v1/services/{id}/checks")
    def checks(id: str, window: str = Query(default="1h", pattern="^(15m|1h|24h)$"),
               operator: str = Depends(require_operator)):
        try:
            identifier = str(UUID(id))
        except ValueError:
            raise HTTPException(404, "Unknown service")
        if pairing_enabled:
            # Verify authorization via a workspace-scoped query; never expose
            # the existence of a service owned by another workspace.
            return store_factory().service_checks_scoped(identifier, window, operator)
        if not any(x["id"] == identifier for x in store_factory().services()):
            raise HTTPException(404, "Unknown service")
        return store_factory().service_checks(identifier, window)

    @app.get("/health")
    def health():
        # A live Python process without a reachable database is not ready.
        try:
            if not store_factory().ping():
                raise RuntimeError("PostgreSQL readiness probe failed")
        except Exception:
            # Never disclose connection strings or internal DB errors.
            return JSONResponse(status_code=503, content={"status": "unavailable", "mode": "cloud"})
        return {"status": "ready", "mode": "cloud"}

    return app
