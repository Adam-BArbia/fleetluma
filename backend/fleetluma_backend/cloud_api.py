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

    app = FastAPI(title="FleetLuma Cloud API", version="0.1.0")
    configure_cors(app)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        code = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND",
                422: "INVALID_REQUEST"}.get(exc.status_code, "HTTP_ERROR")
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
    def hosts(operator: str = Depends(require_operator)):
        return {"items": store_factory().hosts()}

    @app.get("/api/v1/hosts/{id}")
    def host(id: str, operator: str = Depends(require_operator)):
        try:
            row = store_factory().host(id)
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
        return store_factory().history(id, window)

    @app.get("/api/v1/hosts/{id}/processes")
    def processes(id: str, operator: str = Depends(require_operator)):
        try:
            row = store_factory().host(id)
        except ValueError:
            row = None
        if row is None:
            raise HTTPException(404, "Unknown host")
        return store_factory().processes(id)

    @app.get("/api/v1/services")
    def services(operator: str = Depends(require_operator)):
        return {"items": store_factory().services()}

    @app.get("/api/v1/services/{id}/checks")
    def checks(id: str, window: str = Query(default="1h", pattern="^(15m|1h|24h)$"),
               operator: str = Depends(require_operator)):
        try:
            identifier = str(UUID(id))
        except ValueError:
            raise HTTPException(404, "Unknown service")
        if not any(x["id"] == identifier for x in store_factory().services()):
            raise HTTPException(404, "Unknown service")
        return store_factory().service_checks(identifier, window)

    @app.get("/health")
    def health():
        # Readiness does not expose configuration or privileged monitoring data.
        return {"status": "ready", "mode": "cloud"}

    return app
