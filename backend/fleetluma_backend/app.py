"""Contract-first FastAPI coordinator. SQLite, locally provisioned agents."""
import hashlib
import hmac
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from . import service_checks

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from .operator_auth import require_operator, configure_cors
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

app = FastAPI(title="FleetLuma API", version="0.1.0")
configure_cors(app)


def utcnow():
    return datetime.now(timezone.utc)


def stamp(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def database_path():
    return os.environ.get("FLEETLUMA_DATABASE_PATH", "./fleetluma.db")


@contextmanager
def db():
    connection = sqlite3.connect(database_path(), timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def provision():
    """Provision host/token pairs from an out-of-band JSON configuration."""
    raw = os.environ.get("FLEETLUMA_HOSTS_JSON", "[]")
    items = json.loads(raw)
    if not isinstance(items, list):
        raise RuntimeError("FLEETLUMA_HOSTS_JSON must be an array")
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS hosts (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, os TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE, last_seen_at TEXT
        );
        CREATE TABLE IF NOT EXISTS samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            host_id TEXT NOT NULL REFERENCES hosts(id),
            sampled_at TEXT NOT NULL, received_at TEXT NOT NULL,
            metrics TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_samples_host_time ON samples(host_id, received_at);
        CREATE TABLE IF NOT EXISTS process_snapshots (
            host_id TEXT PRIMARY KEY REFERENCES hosts(id),
            captured_at TEXT NOT NULL, processes TEXT NOT NULL
        );
        """)
        for item in items:
            identifier = str(UUID(item["id"]))
            name = str(item["name"])
            osname = str(item["os"]).lower()
            token = str(item["token"])
            if osname not in {"linux", "windows"} or len(token) < 16:
                raise RuntimeError("Invalid host OS or short token")
            digest = hashlib.sha256(token.encode()).hexdigest()
            existing = conn.execute("SELECT token_hash FROM hosts WHERE id=?", (identifier,)).fetchone()
            if existing and existing["token_hash"] != digest:
                raise RuntimeError("Cannot change a host token implicitly")
            conn.execute(
                "INSERT OR IGNORE INTO hosts(id,name,os,token_hash) VALUES(?,?,?,?)",
                (identifier, name, osname, digest))
        service_checks.provision_services(conn)


@app.on_event("startup")
def startup():
    provision()
    service_checks.start_worker(db)


@app.on_event("shutdown")
def shutdown():
    service_checks.stop_worker()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Metrics(StrictModel):
    cpu_pct: float = Field(ge=0, le=100)
    ram_used_bytes: int = Field(ge=0)
    ram_total_bytes: int = Field(gt=0)
    disk_path: str = Field(min_length=1)
    disk_used_bytes: int = Field(ge=0)
    disk_total_bytes: int = Field(gt=0)

    @model_validator(mode="after")
    def valid_usage(self):
        if self.ram_used_bytes > self.ram_total_bytes or self.disk_used_bytes > self.disk_total_bytes:
            raise ValueError("Used bytes cannot exceed total")
        return self


class Process(StrictModel):
    pid: int = Field(ge=0)
    name: str
    cpu_pct: float = Field(ge=0)
    memory_bytes: int = Field(ge=0)


class Report(StrictModel):
    sampled_at: datetime
    metrics: Metrics
    processes: list[Process] | None = Field(default=None, max_length=10)


@app.exception_handler(HTTPException)
async def errors(request, exc):
    code = {401: "UNAUTHORIZED_AGENT", 404: "NOT_FOUND", 422: "INVALID_REQUEST"}.get(exc.status_code, "HTTP_ERROR")
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": code, "message": str(exc.detail)}})


def require_host(conn, token):
    if not token:
        raise HTTPException(401, "Agent credentials were not accepted.")
    digest = hashlib.sha256(token.encode()).hexdigest()
    for row in conn.execute("SELECT id, token_hash FROM hosts"):
        if hmac.compare_digest(row["token_hash"], digest):
            return row["id"]
    raise HTTPException(401, "Agent credentials were not accepted.")


def require_known_host(conn, host_id):
    try:
        normalized = str(UUID(host_id))
    except ValueError:
        raise HTTPException(404, "Unknown host")
    record = conn.execute("SELECT * FROM hosts WHERE id=?", (normalized,)).fetchone()
    if record is None:
        raise HTTPException(404, "Unknown host")
    return record


@app.post("/api/v1/agent/reports", status_code=202)
def accept(report: Report, authorization: str | None = Header(default=None)):
    # Pydantic validates payload before the handler; neither invalid payloads nor auth
    # failures modify heartbeat. Host identity is derived exclusively from the token.
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Agent credentials were not accepted.")
    token = authorization[7:]
    with db() as conn:
        host_id = require_host(conn, token)
        receipt = stamp(utcnow())
        conn.execute(
            "INSERT INTO samples(host_id,sampled_at,received_at,metrics) VALUES(?,?,?,?)",
            (host_id, stamp(report.sampled_at), receipt, report.metrics.model_dump_json()))
        if report.processes is not None:
            conn.execute(
                "INSERT INTO process_snapshots(host_id,captured_at,processes) VALUES(?,?,?) "
                "ON CONFLICT(host_id) DO UPDATE SET captured_at=excluded.captured_at, processes=excluded.processes",
                (host_id, stamp(report.sampled_at),
                 json.dumps([item.model_dump() for item in report.processes])))
        conn.execute("UPDATE hosts SET last_seen_at=? WHERE id=?", (receipt, host_id))
    return {"host_id": host_id, "received_at": receipt, "status": "accepted"}


def latest_metrics(conn, host_id):
    sample = conn.execute(
        "SELECT * FROM samples WHERE host_id=? ORDER BY id DESC LIMIT 1", (host_id,)).fetchone()
    if sample is None:
        return None
    m = json.loads(sample["metrics"])
    m["ram_pct"] = round(100 * m["ram_used_bytes"] / m["ram_total_bytes"], 2)
    m["disk_pct"] = round(100 * m["disk_used_bytes"] / m["disk_total_bytes"], 2)
    m.update(sampled_at=sample["sampled_at"], received_at=sample["received_at"])
    return m


def serialize_host(conn, row):
    seen = row["last_seen_at"]
    status = "PENDING" if not seen else (
        "STALE" if utcnow() - datetime.fromisoformat(seen.replace("Z", "+00:00")) > timedelta(seconds=35)
        else "CONNECTED")
    return {"id": row["id"], "name": row["name"], "os": row["os"],
            "status": status, "last_seen_at": seen,
            "latest_metrics": latest_metrics(conn, row["id"])}


@app.get("/api/v1/hosts")
def hosts(operator: str | None = Depends(require_operator)):
    with db() as conn:
        return {"items": [serialize_host(conn, row) for row in conn.execute("SELECT * FROM hosts ORDER BY name")]}


@app.get("/api/v1/hosts/{id}")
def host(id: str, operator: str | None = Depends(require_operator)):
    with db() as conn:
        return serialize_host(conn, require_known_host(conn, id))


WINDOWS = {"15m": timedelta(minutes=15), "1h": timedelta(hours=1), "24h": timedelta(hours=24)}


@app.get("/api/v1/hosts/{id}/history")
def history(id: str, window: str = Query(default="1h", pattern="^(15m|1h|24h)$"), operator: str | None = Depends(require_operator)):
    with db() as conn:
        row = require_known_host(conn, id)
        cutoff = stamp(utcnow() - WINDOWS[window])
        samples = conn.execute(
            "SELECT sampled_at,received_at,metrics FROM samples WHERE host_id=? "
            "AND received_at>=? ORDER BY received_at ASC LIMIT 10000",
            (row["id"], cutoff)).fetchall()
        items = []
        for s in samples:
            m = json.loads(s["metrics"])
            items.append({"sampled_at": s["sampled_at"], "received_at": s["received_at"],
                          "cpu_pct": m["cpu_pct"],
                          "ram_pct": round(100*m["ram_used_bytes"]/m["ram_total_bytes"],2),
                          "disk_pct": round(100*m["disk_used_bytes"]/m["disk_total_bytes"],2)})
        return {"host_id": row["id"], "window": window, "items": items}


@app.get("/api/v1/hosts/{id}/processes")
def processes(id: str, operator: str | None = Depends(require_operator)):
    with db() as conn:
        row = require_known_host(conn, id)
        snap = conn.execute("SELECT * FROM process_snapshots WHERE host_id=?", (row["id"],)).fetchone()
        return {"host_id": row["id"], "captured_at": snap["captured_at"] if snap else None,
                "processes": json.loads(snap["processes"]) if snap else []}


@app.get("/api/v1/services")
def list_services(operator: str | None = Depends(require_operator)):
    with db() as conn:
        return {"items": service_checks.list_services(conn)}


@app.get("/api/v1/services/{id}/checks")
def list_service_checks(id: str, window: str = Query(default="1h", pattern="^(15m|1h|24h)$"), operator: str | None = Depends(require_operator)):
    with db() as conn:
        try:
            normalized = str(UUID(id))
        except ValueError:
            raise HTTPException(404, "Unknown service")
        if conn.execute("SELECT 1 FROM services WHERE id=?", (normalized,)).fetchone() is None:
            raise HTTPException(404, "Unknown service")
        return {"service_id": normalized, "window": window,
                "items": service_checks.read_checks(conn, normalized, WINDOWS[window])}
