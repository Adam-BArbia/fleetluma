"""FL-15: isolated PostgreSQL persistence adapter for the future cloud API.

No SQLite runtime behavior is changed by merely importing this module.
Requires a server-side pooler connection string, never available to Flutter.
"""
import hashlib
import hmac
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

WINDOWS = {"15m": timedelta(minutes=15), "1h": timedelta(hours=1), "24h": timedelta(hours=24)}


def iso(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@contextmanager
def connection():
    url = os.environ.get("FLEETLUMA_DATABASE_URL")
    if not url:
        raise RuntimeError("FLEETLUMA_DATABASE_URL missing (server-side only)")
    # Supabase transaction-pooler DSN recommended; require TLS.
    with psycopg.connect(url, row_factory=dict_row, connect_timeout=5, sslmode="require",
                         prepare_threshold=None) as conn:
        yield conn


def host_state(last_seen_at, now=None, stale_seconds=35):
    if last_seen_at is None:
        return "PENDING"
    now = now or datetime.now(timezone.utc)
    return "STALE" if now - last_seen_at > timedelta(seconds=stale_seconds) else "CONNECTED"


class PostgresStore:
    def __init__(self, connect=connection):
        self._connect = connect

    def ping(self):
        """Readiness requires private schema/table SELECT grants as well as a live DB."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT (
                        has_schema_privilege(current_user, 'fleetluma', 'USAGE')
                        AND has_table_privilege(current_user, 'fleetluma.hosts', 'SELECT')
                        AND has_table_privilege(current_user, 'fleetluma.samples', 'SELECT')
                        AND has_table_privilege(current_user, 'fleetluma.process_snapshots', 'SELECT')
                        AND has_table_privilege(current_user, 'fleetluma.services', 'SELECT')
                        AND has_table_privilege(current_user, 'fleetluma.service_checks', 'SELECT')
                    ) AS ready
                """)
                return cur.fetchone()["ready"] is True

    def provision_host(self, host_id, name, os_name, token):
        """Provision explicitly from privileged backend control path, never user GET."""
        identifier = str(UUID(str(host_id)))
        if os_name not in ("linux", "windows") or len(token) < 16:
            raise ValueError("Invalid OS or token")
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT token_hash FROM fleetluma.hosts WHERE id=%s", (identifier,))
                existing = cur.fetchone()
                if existing is not None and not hmac.compare_digest(existing["token_hash"], digest):
                    raise ValueError("Changing an existing agent token requires a deliberate rotation")
                cur.execute("""
                    INSERT INTO fleetluma.hosts(id,name,os,token_hash)
                    VALUES (%s,%s,%s,%s)
                    ON CONFLICT (id) DO UPDATE
                    SET name=excluded.name, os=excluded.os
                """, (identifier, name, os_name, digest))
        return identifier

    def accept_report(self, token, sampled_at, metrics, processes=None):
        """Authenticate and commit sample+process snapshot+heartbeat atomically."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self._connect() as conn:
            with conn.cursor() as cur:
                # Exact hashed match; token hashes never leave the DB/API.
                if os.environ.get("FLEETLUMA_PAIRING_ENABLED") == "true":
                    # Serialize against revoke(); rejected reports never mutate
                    # samples or heartbeat even under concurrent requests.
                    cur.execute("""
                        SELECT id FROM fleetluma.hosts
                        WHERE token_hash=%s AND lifecycle='ACTIVE' FOR UPDATE
                    """, (token_hash,))
                else:
                    cur.execute("SELECT id FROM fleetluma.hosts WHERE token_hash=%s", (token_hash,))
                row = cur.fetchone()
                if row is None:
                    return None
                host_id = row["id"]
                # Use server receipt time for freshness, independently of host clock.
                cur.execute("""
                    INSERT INTO fleetluma.samples(host_id,sampled_at,metrics)
                    VALUES (%s,%s,%s) RETURNING received_at
                """, (host_id, sampled_at, Jsonb(metrics)))
                received_at = cur.fetchone()["received_at"]
                if processes is not None:
                    cur.execute("""
                        INSERT INTO fleetluma.process_snapshots(host_id,captured_at,processes)
                        VALUES (%s,%s,%s)
                        ON CONFLICT (host_id) DO UPDATE SET
                        captured_at=excluded.captured_at, processes=excluded.processes
                    """, (host_id, sampled_at, Jsonb(processes)))
                cur.execute("UPDATE fleetluma.hosts SET last_seen_at=%s WHERE id=%s",
                            (received_at, host_id))
        return {"host_id": str(host_id), "received_at": iso(received_at), "status": "accepted"}

    def _serialize_host(self, conn, host):
        with conn.cursor() as cur:
            cur.execute("""
                SELECT sampled_at,received_at,metrics
                FROM fleetluma.samples WHERE host_id=%s
                ORDER BY id DESC LIMIT 1
            """, (host["id"],))
            row = cur.fetchone()
        metrics = None
        if row is not None:
            m = dict(row["metrics"])
            m.update(ram_pct=round(m["ram_used_bytes"] * 100 / m["ram_total_bytes"], 2),
                     disk_pct=round(m["disk_used_bytes"] * 100 / m["disk_total_bytes"], 2),
                     sampled_at=iso(row["sampled_at"]),
                     received_at=iso(row["received_at"]))
            metrics = m
        return {"id": str(host["id"]), "name": host["name"], "os": host["os"],
                "status": host_state(host["last_seen_at"]),
                "last_seen_at": iso(host["last_seen_at"]) if host["last_seen_at"] else None,
                "latest_metrics": metrics}

    def hosts(self):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM fleetluma.hosts ORDER BY name")
                rows = cur.fetchall()
            return [self._serialize_host(conn, row) for row in rows]

    def host(self, host_id):
        identifier = str(UUID(str(host_id)))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM fleetluma.hosts WHERE id=%s", (identifier,))
                row = cur.fetchone()
            return self._serialize_host(conn, row) if row else None

    def history(self, host_id, window="1h"):
        interval = WINDOWS[window]
        host_id = str(UUID(str(host_id)))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT sampled_at,received_at,metrics
                    FROM fleetluma.samples
                    WHERE host_id=%s AND received_at >= %s
                    ORDER BY received_at ASC LIMIT 10000
                """, (host_id, datetime.now(timezone.utc) - interval))
                rows = cur.fetchall()
        result = []
        for row in rows:
            m = row["metrics"]
            result.append({
                "sampled_at": iso(row["sampled_at"]), "received_at": iso(row["received_at"]),
                "cpu_pct": m["cpu_pct"],
                "ram_pct": round(100 * m["ram_used_bytes"]/m["ram_total_bytes"], 2),
                "disk_pct": round(100 * m["disk_used_bytes"]/m["disk_total_bytes"], 2),
            })
        return {"host_id": host_id, "window": window, "items": result}

    def processes(self, host_id):
        host_id = str(UUID(str(host_id)))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT captured_at,processes FROM fleetluma.process_snapshots WHERE host_id=%s",
                            (host_id,))
                row = cur.fetchone()
        return {"host_id": host_id, "captured_at": iso(row["captured_at"]) if row else None,
                "processes": row["processes"] if row else []}

    def services(self):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT s.*, c.checked_at, c.status, c.latency_ms
                    FROM fleetluma.services s
                    LEFT JOIN LATERAL (
                        SELECT checked_at,status,latency_ms
                        FROM fleetluma.service_checks
                        WHERE service_id=s.id ORDER BY id DESC LIMIT 1
                    ) c ON TRUE ORDER BY s.name
                """)
                rows = cur.fetchall()
        return [{"id": str(r["id"]), "host_id": str(r["host_id"]) if r["host_id"] else None,
                 "name": r["name"], "url": r["url"], "enabled": r["enabled"],
                 "status": r["status"] or "UNKNOWN",
                 "checked_at": iso(r["checked_at"]) if r["checked_at"] else None,
                 "latency_ms": r["latency_ms"]} for r in rows]

    def service_checks(self, service_id, window="1h"):
        sid = str(UUID(str(service_id)))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT checked_at,status,http_code,latency_ms,failure_kind
                    FROM fleetluma.service_checks
                    WHERE service_id=%s AND checked_at >= %s
                    ORDER BY checked_at ASC LIMIT 10000
                """, (sid, datetime.now(timezone.utc) - WINDOWS[window]))
                rows = cur.fetchall()
        return {"service_id": sid, "window": window,
                "items": [dict(r, checked_at=iso(r["checked_at"])) for r in rows]}

    def purge_old(self, before=None):
        """Call only from a trusted scheduled worker; never on GET requests."""
        cutoff = before or datetime.now(timezone.utc) - timedelta(hours=24)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM fleetluma.samples WHERE received_at < %s", (cutoff,))
                metrics_deleted = cur.rowcount
                cur.execute("DELETE FROM fleetluma.service_checks WHERE checked_at < %s", (cutoff,))
                checks_deleted = cur.rowcount
        return {"samples": metrics_deleted, "checks": checks_deleted}

    # FL-32 target: workspace-filtered monitor query methods. None of these
    # rely on user-controlled JWT metadata; 'actor' is the verified sub claim.
    # These are invoked only when FLEETLUMA_PAIRING_ENABLED=true after migration.

    @staticmethod
    def _uuid(value):
        return str(UUID(str(value)))

    @staticmethod
    def _membership(cur, actor, workspace_id):
        cur.execute("""
          SELECT 1 FROM fleetluma.workspace_memberships
          WHERE user_id=%s AND workspace_id=%s
        """, (actor, workspace_id))
        if cur.fetchone() is None:
            raise PermissionError("Workspace access denied")

    def hosts_scoped(self, actor, workspace_id):
        workspace_id, actor = self._uuid(workspace_id), self._uuid(actor)
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._membership(cur, actor, workspace_id)
                cur.execute("""
                  SELECT * FROM fleetluma.hosts
                  WHERE workspace_id=%s ORDER BY name
                """, (workspace_id,))
                rows=cur.fetchall()
            return [self._serialize_host_scoped(conn, row) for row in rows]

    def _serialize_host_scoped(self, conn, row):
        record=self._serialize_host(conn, row)
        record["workspace_id"]=str(row["workspace_id"])
        record["lifecycle"]=row["lifecycle"]
        if row["lifecycle"] == "REVOKED":
            record["status"]="REVOKED"
        return record

    def host_scoped(self, host_id, actor):
        host_id, actor = self._uuid(host_id), self._uuid(actor)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                  SELECT h.* FROM fleetluma.hosts h
                  JOIN fleetluma.workspace_memberships m
                    ON m.workspace_id=h.workspace_id
                  WHERE h.id=%s AND m.user_id=%s
                """, (host_id, actor))
                row=cur.fetchone()
            return self._serialize_host_scoped(conn, row) if row else None

    def history_scoped(self, host_id, window, actor):
        host_id, actor = self._uuid(host_id), self._uuid(actor)
        cutoff=datetime.now(timezone.utc)-WINDOWS[window]
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                  SELECT s.sampled_at,s.received_at,s.metrics
                  FROM fleetluma.samples s
                  JOIN fleetluma.hosts h ON h.id=s.host_id
                  JOIN fleetluma.workspace_memberships m ON m.workspace_id=h.workspace_id
                  WHERE s.host_id=%s AND m.user_id=%s AND s.received_at >= %s
                  ORDER BY s.received_at ASC LIMIT 10000
                """, (host_id, actor, cutoff))
                rows=cur.fetchall()
        return {"host_id":host_id,"window":window,"items":[{
            "sampled_at": iso(r["sampled_at"]),
            "received_at": iso(r["received_at"]),
            "cpu_pct": r["metrics"]["cpu_pct"],
            "ram_pct": round(100*r["metrics"]["ram_used_bytes"]/r["metrics"]["ram_total_bytes"],2),
            "disk_pct": round(100*r["metrics"]["disk_used_bytes"]/r["metrics"]["disk_total_bytes"],2),
        } for r in rows]}

    def processes_scoped(self, host_id, actor):
        host_id, actor = self._uuid(host_id), self._uuid(actor)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                  SELECT p.captured_at,p.processes FROM fleetluma.process_snapshots p
                  JOIN fleetluma.hosts h ON h.id=p.host_id
                  JOIN fleetluma.workspace_memberships m ON m.workspace_id=h.workspace_id
                  WHERE p.host_id=%s AND m.user_id=%s
                """, (host_id, actor))
                row=cur.fetchone()
        return {"host_id":host_id,
                "captured_at":iso(row["captured_at"]) if row else None,
                "processes":row["processes"] if row else []}

    def services_scoped(self, actor, workspace_id):
        workspace_id, actor = self._uuid(workspace_id), self._uuid(actor)
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._membership(cur,actor,workspace_id)
                cur.execute("""
                  SELECT s.*,c.checked_at,c.status,c.latency_ms
                  FROM fleetluma.services s
                  LEFT JOIN LATERAL (
                    SELECT checked_at,status,latency_ms
                    FROM fleetluma.service_checks
                    WHERE service_id=s.id ORDER BY id DESC LIMIT 1
                  ) c ON TRUE
                  WHERE s.workspace_id=%s ORDER BY s.name
                """, (workspace_id,))
                rows=cur.fetchall()
        return [{ "id":str(r["id"]),
                  "host_id":str(r["host_id"]) if r["host_id"] else None,
                  "name":r["name"],"url":r["url"],"enabled":r["enabled"],
                  "status":r["status"] or "UNKNOWN",
                  "checked_at":iso(r["checked_at"]) if r["checked_at"] else None,
                  "latency_ms":r["latency_ms"]} for r in rows]

    def service_checks_scoped(self, service_id, window, actor):
        service_id,actor=self._uuid(service_id),self._uuid(actor)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                  SELECT c.checked_at,c.status,c.http_code,c.latency_ms,c.failure_kind
                  FROM fleetluma.service_checks c
                  JOIN fleetluma.services s ON s.id=c.service_id
                  JOIN fleetluma.workspace_memberships m ON m.workspace_id=s.workspace_id
                  WHERE c.service_id=%s AND m.user_id=%s AND
                    c.checked_at >= %s ORDER BY c.checked_at ASC LIMIT 10000
                """, (service_id, actor, datetime.now(timezone.utc)-WINDOWS[window]))
                rows=cur.fetchall()
        return {"service_id":service_id,"window":window,
                "items":[dict(r,checked_at=iso(r["checked_at"])) for r in rows]}

    def service_visible_to(self, service_id, actor):
        service_id, actor = self._uuid(service_id), self._uuid(actor)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                  SELECT 1 FROM fleetluma.services s
                  JOIN fleetluma.workspace_memberships m
                    ON m.workspace_id=s.workspace_id
                  WHERE s.id=%s AND m.user_id=%s
                """,(service_id,actor))
                return cur.fetchone() is not None
