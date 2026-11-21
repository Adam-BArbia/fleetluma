"""FL-32 private PostgreSQL adapter for v0.1.0 device enrollment.

No public tables, no direct browser database connections, no user-code-only
authorization. Every transition is transactional and durable across Vercel calls.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from .pairing_core import (
    POLL_INTERVAL_SECONDS, code_digest, hash_secret, new_pairing_ticket,
    normalize_code, validate_agent_metadata,
)
from .postgres_store import PostgresStore, iso


class PairingFailure(Exception):
    """Safe-to-disclose status; never contains credentials."""

    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(message)


def _uuid(value: str) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise PairingFailure(404, "Device not found") from None


class PairingStore(PostgresStore):
    def __init__(self, pepper: str, connect=None):
        if len(pepper) < 32:
            raise ValueError("Missing secure enrollment signing key")
        super().__init__(connect=connect) if connect is not None else super().__init__()
        self.pepper = pepper

    def _subject(self, value: str) -> str:
        return code_digest_hash(self.pepper, value)

    def _consume_limit(self, scope: str, digest: str, maximum: int):
        # A rejection in the *business transaction* must never roll back a
        # consumed attempt. Persist limit in a separate committed transaction.
        with self._connect() as conn:
            with conn.cursor() as cur:
                allowed = self._limit(cur, scope, digest, maximum)
        if not allowed:
            raise PairingFailure(429, "Too many requests; try again later")

    @staticmethod
    def _limit(cur, scope: str, digest: str, maximum: int,
               window: timedelta = timedelta(minutes=10)):
        """Atomic rate-limit counter using a durable row, safe for serverless."""
        cur.execute("""
          INSERT INTO fleetluma.pairing_rate_limits
            (scope,subject_digest,window_start,attempts)
          VALUES (%s,%s,now(),1)
          ON CONFLICT (scope,subject_digest) DO UPDATE SET
            attempts = CASE
              WHEN fleetluma.pairing_rate_limits.window_start < now() - %s::interval
              THEN 1
              ELSE fleetluma.pairing_rate_limits.attempts + 1
            END,
            window_start = CASE
              WHEN fleetluma.pairing_rate_limits.window_start < now() - %s::interval
              THEN now()
              ELSE fleetluma.pairing_rate_limits.window_start
            END
          RETURNING attempts
        """, (scope, digest, window, window))
        return cur.fetchone()["attempts"] <= maximum

    def _admin(self, cur, actor: str, workspace: str | None = None):
        """Return one authorized workspace or fail closed."""
        if workspace:
            cur.execute("""
              SELECT role FROM fleetluma.workspace_memberships
              WHERE user_id=%s AND workspace_id=%s AND role IN('owner','admin')
            """, (actor, workspace))
        else:
            cur.execute("""
              SELECT role FROM fleetluma.workspace_memberships
              WHERE user_id=%s AND role IN('owner','admin') LIMIT 1
            """, (actor,))
        if cur.fetchone() is None:
            raise PairingFailure(403, "Workspace administrator permission required")

    def create(self, *, hostname, platform, agent_version,
               report_token_sha256, capabilities, client_key):
        validate_agent_metadata(hostname, platform, agent_version,
                                report_token_sha256, capabilities)
        client_digest = self._subject("create:" + client_key)
        self._consume_limit("create", client_digest, maximum=5)
        with self._connect() as conn:
            with conn.cursor() as cur:
                # Serialize global budget checks; no in-memory rate counters.
                cur.execute("SELECT pg_advisory_xact_lock(5432101)")
                cur.execute("""
                  SELECT count(*) AS n FROM fleetluma.pairing_sessions
                  WHERE created_at >= now()-interval '10 minutes'
                """)
                if cur.fetchone()["n"] >= 250:
                    raise PairingFailure(429, "Enrollment temporarily unavailable")
                for attempt in range(3):
                    ticket = new_pairing_ticket(self.pepper)
                    try:
                        cur.execute("""
                          INSERT INTO fleetluma.pairing_sessions
                            (id,user_code_hash,device_code_hash,report_token_hash,
                             display_name,platform,agent_version,capabilities,
                             expires_at,client_key_hash)
                          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """, (str(uuid4()), ticket.user_code_hash,
                              ticket.device_code_hash, report_token_sha256,
                              hostname, platform, agent_version, Jsonb(capabilities),
                              ticket.expires_at, client_digest))
                        break
                    except psycopg.errors.UniqueViolation:
                        # A collision is fantastically unlikely, but a transaction
                        # requires savepoint-based recovery before another attempt.
                        raise PairingFailure(503, "Retry device enrollment") from None
        return {
            "device_code": ticket.device_code, "user_code": ticket.user_code,
            "verification_uri": "https://fleetluma-web.vercel.app/devices/pair",
            "expires_in": 600, "interval": POLL_INTERVAL_SECONDS,
        }

    def poll(self, device_code: str):
        if not isinstance(device_code, str) or not (32 <= len(device_code) <= 256):
            raise PairingFailure(401, "Invalid enrollment session")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                  SELECT id,status,expires_at,next_poll_at,host_id,workspace_id
                  FROM fleetluma.pairing_sessions WHERE device_code_hash=%s
                  FOR UPDATE
                """, (hash_secret(device_code),))
                row = cur.fetchone()
                if row is None:
                    raise PairingFailure(401, "Invalid enrollment session")
                if row["expires_at"] <= datetime.now(timezone.utc):
                    raise PairingFailure(410, "Enrollment expired")
                if row["status"] == "DENIED":
                    raise PairingFailure(403, "Enrollment denied")
                if row["status"] in ("CANCELLED", "EXPIRED"):
                    raise PairingFailure(410, "Enrollment no longer active")
                if row["status"] == "CONSUMED":
                    return {"status": "paired", "host_id": str(row["host_id"]),
                            "workspace_id": str(row["workspace_id"])}
                if row["next_poll_at"] and row["next_poll_at"] > datetime.now(timezone.utc):
                    raise PairingFailure(429, "Polling too frequently")
                if row["status"] == "APPROVED":
                    cur.execute("""
                      UPDATE fleetluma.pairing_sessions
                      SET status='CONSUMED',consumed_at=now()
                      WHERE id=%s
                    """, (row["id"],))
                    return {"status": "paired", "host_id": str(row["host_id"]),
                            "workspace_id": str(row["workspace_id"])}
                cur.execute("""
                  UPDATE fleetluma.pairing_sessions
                  SET next_poll_at=now()+interval '5 seconds' WHERE id=%s
                """, (row["id"],))
                return {"status": "pending"}

    def cancel(self, device_code: str):
        if not isinstance(device_code, str) or not (32 <= len(device_code) <= 256):
            raise PairingFailure(401, "Invalid enrollment session")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                  SELECT id,status FROM fleetluma.pairing_sessions
                  WHERE device_code_hash=%s FOR UPDATE
                """, (hash_secret(device_code),))
                row = cur.fetchone()
                if not row:
                    raise PairingFailure(401, "Invalid enrollment session")
                if row["status"] == "PENDING":
                    cur.execute("""
                      UPDATE fleetluma.pairing_sessions
                      SET status='CANCELLED' WHERE id=%s
                    """, (row["id"],))

    def workspaces(self, actor):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                  SELECT w.id,w.name,m.role FROM fleetluma.workspaces w
                  JOIN fleetluma.workspace_memberships m ON m.workspace_id=w.id
                  WHERE m.user_id=%s ORDER BY w.name
                """, (_uuid(actor),))
                return {"items": [{**r, "id": str(r["id"])} for r in cur.fetchall()]}

    def resolve(self, code, actor):
        actor = _uuid(actor)
        try:
            digest = code_digest(code, self.pepper)
        except ValueError:
            # Still charge rate-limit budget for malformed codes.
            digest = None
        self._consume_limit("resolve", self._subject("resolve:" + actor), 10)
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._admin(cur, actor)
                row = None
                if digest:
                    cur.execute("""
                      SELECT * FROM fleetluma.pairing_sessions
                      WHERE user_code_hash=%s FOR UPDATE
                    """, (digest,))
                    row = cur.fetchone()
                if (row is None or row["status"] != "PENDING"
                        or row["expires_at"] <= datetime.now(timezone.utc)):
                    raise PairingFailure(404, "Pairing code not available")
                cur.execute("""
                  INSERT INTO fleetluma.pairing_reviews(pairing_id,operator_id)
                  VALUES(%s,%s) ON CONFLICT(pairing_id,operator_id)
                  DO UPDATE SET reviewed_at=now()
                """, (row["id"], actor))
                return {
                    "pairing_id": str(row["id"]), "hostname": row["display_name"],
                    "platform": row["platform"], "agent_version": row["agent_version"],
                    "capabilities": row["capabilities"], "expires_at": iso(row["expires_at"]),
                }

    def _reviewed(self, cur, pairing_id, actor):
        cur.execute("""
          SELECT 1 FROM fleetluma.pairing_reviews
          WHERE pairing_id=%s AND operator_id=%s
        """, (pairing_id, actor))
        if cur.fetchone() is None:
            raise PairingFailure(403, "Review this pairing code before approving")

    def approve(self, pairing_id, workspace_id, actor):
        pairing_id, workspace_id, actor = _uuid(pairing_id), _uuid(workspace_id), _uuid(actor)
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._admin(cur, actor, workspace_id)
                self._reviewed(cur, pairing_id, actor)
                cur.execute("""
                  SELECT * FROM fleetluma.pairing_sessions WHERE id=%s FOR UPDATE
                """, (pairing_id,))
                row = cur.fetchone()
                if not row:
                    raise PairingFailure(404, "Pairing code not available")
                if row["expires_at"] <= datetime.now(timezone.utc):
                    raise PairingFailure(410, "Enrollment expired")
                if row["status"] in ("APPROVED","CONSUMED"):
                    if row["approved_by"] == UUID(actor) and row["workspace_id"] == UUID(workspace_id):
                        return {"status": "approved", "host_id": str(row["host_id"]),
                                "workspace_id": workspace_id}
                    raise PairingFailure(409, "Pairing was already approved")
                if row["status"] != "PENDING":
                    raise PairingFailure(409, "Pairing is no longer pending")
                host_id = str(uuid4())
                cur.execute("""
                  INSERT INTO fleetluma.hosts
                    (id,name,os,token_hash,workspace_id,lifecycle,enrolled_at,agent_version)
                  VALUES(%s,%s,%s,%s,%s,'ACTIVE',now(),%s)
                """, (host_id,row["display_name"],row["platform"],
                      row["report_token_hash"],workspace_id,row["agent_version"]))
                cur.execute("""
                  UPDATE fleetluma.pairing_sessions
                  SET status='APPROVED',approved_by=%s,workspace_id=%s,
                      host_id=%s,approved_at=now()
                  WHERE id=%s
                """, (actor, workspace_id, host_id, pairing_id))
                cur.execute("""
                  INSERT INTO fleetluma.device_audit_events
                    (host_id,pairing_id,workspace_id,actor_user_id,action,details)
                  VALUES(%s,%s,%s,%s,'approved','{}'::jsonb)
                """, (host_id,pairing_id,workspace_id,actor))
        return {"status": "approved", "host_id": host_id, "workspace_id": workspace_id}

    def deny(self, pairing_id, actor):
        pairing_id, actor = _uuid(pairing_id), _uuid(actor)
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._admin(cur, actor)
                self._reviewed(cur, pairing_id, actor)
                cur.execute("""
                  SELECT status,expires_at FROM fleetluma.pairing_sessions
                  WHERE id=%s FOR UPDATE
                """, (pairing_id,))
                row = cur.fetchone()
                if not row or row["expires_at"] <= datetime.now(timezone.utc):
                    raise PairingFailure(404, "Pairing code not available")
                if row["status"] == "PENDING":
                    cur.execute("""
                      UPDATE fleetluma.pairing_sessions SET status='DENIED' WHERE id=%s
                    """, (pairing_id,))

    def managed_hosts(self, workspace_id, actor):
        workspace_id, actor = _uuid(workspace_id), _uuid(actor)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                  SELECT 1 FROM fleetluma.workspace_memberships
                  WHERE user_id=%s AND workspace_id=%s
                """, (actor,workspace_id))
                if cur.fetchone() is None:
                    raise PairingFailure(403, "Workspace access denied")
                cur.execute("""
                  SELECT id,workspace_id,name,os,lifecycle,agent_version,last_seen_at
                  FROM fleetluma.hosts WHERE workspace_id=%s ORDER BY name
                """, (workspace_id,))
                rows=cur.fetchall()
                from .postgres_store import host_state
                return {"items": [{
                    "id": str(r["id"]), "workspace_id": str(r["workspace_id"]),
                    "name": r["name"], "os": r["os"], "lifecycle": r["lifecycle"],
                    "status": ("REVOKED" if r["lifecycle"] == "REVOKED"
                               else host_state(r["last_seen_at"])),
                    "agent_version": r["agent_version"],
                    "last_seen_at": iso(r["last_seen_at"]) if r["last_seen_at"] else None,
                } for r in rows]}

    def revoke(self, host_id, actor):
        host_id, actor = _uuid(host_id), _uuid(actor)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                  SELECT workspace_id,lifecycle FROM fleetluma.hosts
                  WHERE id=%s FOR UPDATE
                """, (host_id,))
                host=cur.fetchone()
                if not host:
                    raise PairingFailure(404, "Device not found")
                workspace_id=str(host["workspace_id"])
                self._admin(cur,actor,workspace_id)
                if host["lifecycle"] != "REVOKED":
                    cur.execute("""
                      UPDATE fleetluma.hosts
                      SET lifecycle='REVOKED',revoked_at=now() WHERE id=%s
                    """, (host_id,))
                    cur.execute("""
                      INSERT INTO fleetluma.device_audit_events
                        (host_id,workspace_id,actor_user_id,action)
                      VALUES(%s,%s,%s,'revoked')
                    """, (host_id,workspace_id,actor))
        return self._managed_single(host_id,actor)

    def _managed_single(self,host_id,actor):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT workspace_id FROM fleetluma.hosts WHERE id=%s", (host_id,))
                row=cur.fetchone()
                if not row:
                    raise PairingFailure(404,"Device not found")
        return next(x for x in self.managed_hosts(str(row["workspace_id"]),actor)["items"]
                    if x["id"]==host_id)

    def rename(self,host_id,name,actor):
        host_id,actor=_uuid(host_id),_uuid(actor)
        if not isinstance(name,str) or not 2<=len(name.strip())<=64:
            raise PairingFailure(422,"Invalid device name")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT workspace_id FROM fleetluma.hosts WHERE id=%s FOR UPDATE",(host_id,))
                row=cur.fetchone()
                if not row:
                    raise PairingFailure(404,"Device not found")
                self._admin(cur,actor,str(row["workspace_id"]))
                cur.execute("UPDATE fleetluma.hosts SET name=%s WHERE id=%s",(name.strip(),host_id))
        return self._managed_single(host_id,actor)

    def audit(self,workspace_id,actor,limit=50):
        workspace_id,actor=_uuid(workspace_id),_uuid(actor)
        limit=max(1,min(100,int(limit)))
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._admin(cur,actor,workspace_id)
                cur.execute("""
                  SELECT id,host_id,action,created_at,details
                  FROM fleetluma.device_audit_events
                  WHERE workspace_id=%s ORDER BY created_at DESC LIMIT %s
                """,(workspace_id,limit+1))
                rows=cur.fetchall()
        return {"items":[{
            "id":str(r["id"]),"host_id":str(r["host_id"]) if r["host_id"] else None,
            "action":r["action"],"created_at":iso(r["created_at"]),
            "details":r["details"],
        } for r in rows[:limit]],"has_more":len(rows)>limit}


def code_digest_hash(pepper: str, value: str):
    """Opaque deterministic HMAC namespace for rate-limit subjects."""
    import hmac
    return hmac.new(pepper.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()
