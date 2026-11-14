"""Administrator-configured HTTP probes; never fetch arbitrary viewer-supplied URLs."""
import json
import os
import socket
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib import error, request
from urllib.parse import urlsplit
from uuid import UUID


_STOP = threading.Event()
_THREAD = None


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def provision_services(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS services (
        id TEXT PRIMARY KEY,
        host_id TEXT REFERENCES hosts(id),
        name TEXT NOT NULL,
        url TEXT NOT NULL,
        enabled INTEGER NOT NULL CHECK(enabled IN (0,1))
    );
    CREATE TABLE IF NOT EXISTS service_checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service_id TEXT NOT NULL REFERENCES services(id),
        checked_at TEXT NOT NULL,
        status TEXT NOT NULL,
        http_code INTEGER,
        latency_ms REAL,
        failure_kind TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_service_checks_time
        ON service_checks(service_id, checked_at);
    """)
    config = json.loads(os.environ.get("FLEETLUMA_SERVICES_JSON", "[]"))
    if not isinstance(config, list):
        raise RuntimeError("FLEETLUMA_SERVICES_JSON must be a JSON array")
    for item in config:
        service_id = str(UUID(item["id"]))
        host_id = str(UUID(item["host_id"])) if item.get("host_id") else None
        name = str(item["name"]).strip()
        url = str(item["url"])
        enabled = item.get("enabled", True)
        parsed = urlsplit(url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.fragment
                or parsed.query or not name or not isinstance(enabled, bool)):
            raise RuntimeError("Invalid HTTP service configuration; URLs cannot carry secrets")
        # Explicit administrator provisioning only; no API to register arbitrary URLs.
        conn.execute("""
            INSERT INTO services(id,host_id,name,url,enabled)
            VALUES(?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                host_id=excluded.host_id,name=excluded.name,
                url=excluded.url,enabled=excluded.enabled
        """, (service_id, host_id, name, url, int(enabled)))


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def probe(url, timeout=4):
    """Read headers only; 3xx redirects are classified without being followed."""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Invalid configured service URL")
    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    req = request.Request(url, method="GET", headers={"User-Agent": "FleetLuma-Health/0.1"})
    started = time.monotonic()
    try:
        with opener.open(req, timeout=timeout) as response:
            status_code = response.status
    except error.HTTPError as exc:
        # HTTP 3xx redirects and 4xx/5xx still provide a response code.
        status_code = exc.code
        exc.close()
    except (error.URLError, socket.timeout, TimeoutError, OSError) as exc:
        kind = "timeout" if isinstance(exc, (socket.timeout, TimeoutError)) or isinstance(
            getattr(exc, "reason", None), (socket.timeout, TimeoutError)) else "network_error"
        return {"checked_at": utcnow(), "status": "UNHEALTHY", "http_code": None,
                "latency_ms": None, "failure_kind": kind}
    latency = round((time.monotonic() - started) * 1000, 2)
    healthy = 200 <= status_code < 400
    return {"checked_at": utcnow(), "status": "HEALTHY" if healthy else "UNHEALTHY",
            "http_code": status_code, "latency_ms": latency,
            "failure_kind": "none" if healthy else "http_error"}


def check_enabled(db_factory):
    """Check explicitly provisioned URLs without holding SQLite locks over network I/O."""
    with db_factory() as conn:
        active = [dict(row) for row in conn.execute(
            "SELECT id,url FROM services WHERE enabled=1 ORDER BY name")]
    for entry in active:
        result = probe(entry["url"])
        with db_factory() as conn:
            conn.execute("""
                INSERT INTO service_checks(service_id,checked_at,status,http_code,latency_ms,failure_kind)
                VALUES(?,?,?,?,?,?)
            """, (entry["id"], result["checked_at"], result["status"], result["http_code"],
                  result["latency_ms"], result["failure_kind"]))


def list_services(conn):
    rows = conn.execute("""
        SELECT s.*, c.checked_at, c.status, c.latency_ms
        FROM services s
        LEFT JOIN service_checks c ON c.id = (
            SELECT id FROM service_checks
            WHERE service_id=s.id ORDER BY id DESC LIMIT 1)
        ORDER BY s.name
    """).fetchall()
    return [{"id": r["id"], "host_id": r["host_id"], "name": r["name"],
             "url": r["url"], "enabled": bool(r["enabled"]),
             "status": r["status"] or "UNKNOWN", "checked_at": r["checked_at"],
             "latency_ms": r["latency_ms"]} for r in rows]


def read_checks(conn, service_id, window):
    cutoff = (datetime.now(timezone.utc) - window).isoformat().replace("+00:00", "Z")
    rows = conn.execute("""
        SELECT checked_at,status,http_code,latency_ms,failure_kind
        FROM service_checks
        WHERE service_id=? AND checked_at>=?
        ORDER BY checked_at ASC LIMIT 10000
    """, (service_id, cutoff)).fetchall()
    return [dict(row) for row in rows]


def _loop(db_factory, interval):
    while not _STOP.is_set():
        try:
            check_enabled(db_factory)
        except Exception:
            # Do not crash FastAPI if a probe or persistence operation fails.
            # Keep details out of logs until safe structured logging is added.
            pass
        _STOP.wait(interval)


def start_worker(db_factory):
    global _THREAD
    stop_worker()
    with db_factory() as conn:
        enabled = conn.execute("SELECT 1 FROM services WHERE enabled=1 LIMIT 1").fetchone()
    if not enabled:
        return
    interval = int(os.environ.get("FLEETLUMA_CHECK_INTERVAL_SECONDS", "20"))
    if interval < 5 or interval > 3600:
        raise RuntimeError("Service check interval must be between 5 and 3600 seconds")
    _STOP.clear()
    _THREAD = threading.Thread(target=_loop, args=(db_factory, interval), daemon=True)
    _THREAD.start()


def stop_worker():
    global _THREAD
    _STOP.set()
    if _THREAD is not None:
        _THREAD.join(timeout=6)
        _THREAD = None
