"""Workspace-scoped CPU/RAM/disk alert rules and incident lifecycle.

Cloud-only, feature-gated behind FLEETLUMA_ALERTS_ENABLED. This code never
executes on its own, never sends notifications or remote commands, and uses
the same private database transaction as an accepted agent metric report.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Literal

from .operator_auth import require_operator
from .postgres_store import connection, iso


class RuleCreate(BaseModel):
    workspace_id: UUID
    host_id: UUID
    metric: Literal["cpu_pct", "ram_pct", "disk_pct"]
    threshold_pct: float = Field(ge=1, le=100)
    consecutive_required: int = Field(default=2, ge=1, le=5)


class RuleEdit(BaseModel):
    threshold_pct: float | None = Field(default=None, ge=1, le=100)
    consecutive_required: int | None = Field(default=None, ge=1, le=5)
    enabled: bool | None = None


def transition_for_sample(value: float, threshold: float,
                          required: int, previous: int,
                          has_active_incident: bool) -> tuple[int, str | None]:
    """Pure, deterministic transition logic; a process cannot invent an incident."""
    if not 1 <= required <= 5 or not 0 <= previous <= 5:
        raise ValueError("Invalid alert-state counters")
    if value >= threshold:
        next_count = min(required, previous + 1)
        return next_count, (
            "OPEN" if next_count >= required and not has_active_incident else None
        )
    return 0, "RESOLVE" if has_active_incident else None


def evaluate_host_report(cur, host_id, metrics, received_at):
    """Call after an authenticated, accepted report, before transaction COMMIT."""
    cur.execute("""
      SELECT id, workspace_id, metric, threshold_pct, consecutive_required
      FROM fleetluma.alert_rules
      WHERE host_id=%s AND enabled=true AND archived_at IS NULL
      ORDER BY id FOR UPDATE
    """, (host_id,))
    rules = cur.fetchall()
    for rule in rules:
        value = float(metrics[rule["metric"]])
        cur.execute("""SELECT consecutive_breaches
                       FROM fleetluma.alert_rule_state WHERE rule_id=%s
                       FOR UPDATE""", (rule["id"],))
        existing = cur.fetchone()
        previous = existing["consecutive_breaches"] if existing else 0
        cur.execute("""SELECT id,status FROM fleetluma.incidents
                       WHERE rule_id=%s AND status IN ('OPEN','ACKNOWLEDGED')
                       FOR UPDATE""", (rule["id"],))
        active = cur.fetchone()
        count, action = transition_for_sample(
            value, float(rule["threshold_pct"]),
            rule["consecutive_required"], previous, active is not None)
        cur.execute("""
          INSERT INTO fleetluma.alert_rule_state
            (rule_id,consecutive_breaches,last_received_at)
          VALUES (%s,%s,%s)
          ON CONFLICT(rule_id) DO UPDATE SET
            consecutive_breaches=EXCLUDED.consecutive_breaches,
            last_received_at=EXCLUDED.last_received_at,
            updated_at=now()
        """, (rule["id"], count, received_at))
        if action == "OPEN":
            cur.execute("""
              INSERT INTO fleetluma.incidents
                (rule_id,workspace_id,host_id,metric,threshold_pct,
                 observed_value,status,opened_at,last_value,last_seen_at)
              VALUES (%s,%s,%s,%s,%s,%s,'OPEN',%s,%s,%s)
              RETURNING id
            """, (rule["id"], rule["workspace_id"], host_id,
                  rule["metric"], rule["threshold_pct"], value,
                  received_at, value, received_at))
            incident_id = cur.fetchone()["id"]
            cur.execute("""
              INSERT INTO fleetluma.incident_events
                (incident_id,event_type,observed_value)
              VALUES (%s,'OPENED',%s)
            """, (incident_id, value))
        elif action == "RESOLVE" and active is not None:
            cur.execute("""
              UPDATE fleetluma.incidents
              SET status='RESOLVED',resolved_at=%s,last_value=%s,last_seen_at=%s
              WHERE id=%s
            """, (received_at, value, received_at, active["id"]))
            cur.execute("""
              INSERT INTO fleetluma.incident_events
                (incident_id,event_type,observed_value)
              VALUES (%s,'RESOLVED',%s)
            """, (active["id"], value))
        elif active is not None:
            cur.execute("""
              UPDATE fleetluma.incidents SET last_value=%s,last_seen_at=%s
              WHERE id=%s
            """, (value, received_at, active["id"]))


def _uuid(value):
    return str(UUID(str(value)))


def _as_json(row):
    result = {}
    for key, value in row.items():
        if key in ("id","workspace_id","host_id","rule_id","created_by",
                   "acknowledged_by","actor_id") and value is not None:
            result[key] = str(value)
        elif hasattr(value, "isoformat"):
            result[key] = iso(value)
        elif isinstance(value, Decimal):
            result[key] = float(value)
        else:
            result[key] = value
    return result


class AlertStore:
    def __init__(self, connect=connection):
        self._connect = connect

    @staticmethod
    def _check_workspace(cur, actor, workspace, write=False):
        cur.execute("""
          SELECT role FROM fleetluma.workspace_memberships
          WHERE user_id=%s AND workspace_id=%s
        """, (_uuid(actor), _uuid(workspace)))
        row = cur.fetchone()
        if row is None:
            raise PermissionError("Workspace access denied")
        if write and row["role"] not in ("owner", "admin"):
            raise PermissionError("Workspace administrator permission required")

    @staticmethod
    def _check_rule(cur, actor, rule_id, write=False):
        cur.execute("""
          SELECT r.*, m.role FROM fleetluma.alert_rules r
          JOIN fleetluma.workspace_memberships m
            ON m.workspace_id=r.workspace_id AND m.user_id=%s
          WHERE r.id=%s AND r.archived_at IS NULL
          FOR UPDATE OF r
        """, (_uuid(actor), _uuid(rule_id)))
        row = cur.fetchone()
        if row is None:
            raise KeyError("Rule not found")
        if write and row["role"] not in ("owner", "admin"):
            raise PermissionError("Workspace administrator permission required")
        return row

    def list_rules(self, actor, workspace_id):
        with self._connect() as conn, conn.cursor() as cur:
            self._check_workspace(cur, actor, workspace_id)
            cur.execute("""
              SELECT id,workspace_id,host_id,metric,threshold_pct,
                     consecutive_required,enabled,created_at,updated_at
              FROM fleetluma.alert_rules
              WHERE workspace_id=%s AND archived_at IS NULL
              ORDER BY created_at DESC LIMIT 100
            """, (_uuid(workspace_id),))
            return [_as_json(r) for r in cur.fetchall()]

    def create_rule(self, actor, body: RuleCreate):
        with self._connect() as conn, conn.cursor() as cur:
            self._check_workspace(cur, actor, body.workspace_id, write=True)
            cur.execute("""SELECT id FROM fleetluma.hosts
                           WHERE id=%s AND workspace_id=%s
                             AND lifecycle='ACTIVE'""",
                        (_uuid(body.host_id), _uuid(body.workspace_id)))
            if cur.fetchone() is None:
                raise KeyError("Host unavailable in workspace")
            cur.execute("""
              INSERT INTO fleetluma.alert_rules
                (workspace_id,host_id,metric,threshold_pct,
                 consecutive_required,created_by)
              VALUES (%s,%s,%s,%s,%s,%s) RETURNING *
            """, (_uuid(body.workspace_id), _uuid(body.host_id),
                  body.metric, body.threshold_pct,
                  body.consecutive_required, _uuid(actor)))
            return _as_json(cur.fetchone())

    def edit_rule(self, actor, rule_id, body: RuleEdit):
        if not body.model_fields_set:
            raise ValueError("No changes specified")
        with self._connect() as conn, conn.cursor() as cur:
            row = self._check_rule(cur, actor, rule_id, write=True)
            threshold = (body.threshold_pct if body.threshold_pct is not None
                         else float(row["threshold_pct"]))
            required = (body.consecutive_required
                        if body.consecutive_required is not None
                        else row["consecutive_required"])
            enabled = body.enabled if body.enabled is not None else row["enabled"]
            cur.execute("""
              UPDATE fleetluma.alert_rules
              SET threshold_pct=%s, consecutive_required=%s,
                  enabled=%s,updated_at=now()
              WHERE id=%s RETURNING *
            """, (threshold, required, enabled, row["id"]))
            updated = _as_json(cur.fetchone())
            # Reset consecutive counter whenever rules change. Retain history.
            cur.execute("""
              UPDATE fleetluma.alert_rule_state
              SET consecutive_breaches=0,updated_at=now() WHERE rule_id=%s
            """, (row["id"],))
            if not enabled:
                self._close_incident(cur, row["id"], "ARCHIVED")
            return updated

    @staticmethod
    def _close_incident(cur, rule_id, event_type):
        cur.execute("""
          UPDATE fleetluma.incidents
          SET status='RESOLVED',resolved_at=now(),last_seen_at=now()
          WHERE rule_id=%s AND status IN ('OPEN','ACKNOWLEDGED')
          RETURNING id,last_value
        """, (rule_id,))
        for incident in cur.fetchall():
            cur.execute("""
              INSERT INTO fleetluma.incident_events
              (incident_id,event_type,observed_value) VALUES (%s,%s,%s)
            """, (incident["id"],event_type,incident["last_value"]))

    def archive_rule(self, actor, rule_id):
        with self._connect() as conn, conn.cursor() as cur:
            row = self._check_rule(cur, actor, rule_id, write=True)
            self._close_incident(cur, row["id"], "ARCHIVED")
            cur.execute("""
              UPDATE fleetluma.alert_rules
              SET archived_at=now(),enabled=false,updated_at=now()
              WHERE id=%s
            """, (row["id"],))
        return {"archived": True}

    def list_incidents(self, actor, workspace_id):
        with self._connect() as conn, conn.cursor() as cur:
            self._check_workspace(cur, actor, workspace_id)
            cur.execute("""
              SELECT id,rule_id,workspace_id,host_id,metric,
                     threshold_pct,observed_value,status,opened_at,
                     acknowledged_at,acknowledged_by,resolved_at,
                     last_value,last_seen_at
              FROM fleetluma.incidents
              WHERE workspace_id=%s ORDER BY opened_at DESC LIMIT 100
            """, (_uuid(workspace_id),))
            return [_as_json(r) for r in cur.fetchall()]

    def acknowledge(self, actor, incident_id):
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""
              SELECT i.id,i.status,m.role
              FROM fleetluma.incidents i
              JOIN fleetluma.workspace_memberships m
                ON m.workspace_id=i.workspace_id AND m.user_id=%s
              WHERE i.id=%s FOR UPDATE OF i
            """, (_uuid(actor), _uuid(incident_id)))
            row = cur.fetchone()
            if row is None:
                raise KeyError("Incident not found")
            if row["role"] not in ("owner","admin"):
                raise PermissionError("Workspace administrator permission required")
            if row["status"] != "OPEN":
                raise ValueError("Only open incidents can be acknowledged")
            cur.execute("""
              UPDATE fleetluma.incidents
              SET status='ACKNOWLEDGED',acknowledged_at=now(),
                  acknowledged_by=%s WHERE id=%s RETURNING *
            """, (_uuid(actor), row["id"]))
            updated = _as_json(cur.fetchone())
            cur.execute("""
              INSERT INTO fleetluma.incident_events
                (incident_id,event_type,actor_id)
              VALUES (%s,'ACKNOWLEDGED',%s)
            """, (row["id"],_uuid(actor)))
            return updated


def make_alert_router(store_factory=AlertStore):
    router = APIRouter(prefix="/api/v1/alerts")

    def run(action):
        try:
            return action()
        except KeyError:
            raise HTTPException(404, "Resource not found") from None
        except PermissionError:
            raise HTTPException(403, "Workspace access denied") from None
        except ValueError:
            raise HTTPException(422, "Invalid alert request") from None

    @router.get("/rules")
    def list_rules(workspace_id: UUID = Query(...),
                   operator: str = Depends(require_operator)):
        return {"items": run(lambda: store_factory().list_rules(operator, workspace_id))}

    @router.post("/rules", status_code=201)
    def create_rule(body: RuleCreate, operator: str = Depends(require_operator)):
        return run(lambda: store_factory().create_rule(operator, body))

    @router.patch("/rules/{rule_id}")
    def edit_rule(rule_id: UUID, body: RuleEdit,
                  operator: str = Depends(require_operator)):
        return run(lambda: store_factory().edit_rule(operator, rule_id, body))

    @router.delete("/rules/{rule_id}")
    def archive_rule(rule_id: UUID, operator: str = Depends(require_operator)):
        return run(lambda: store_factory().archive_rule(operator, rule_id))

    @router.get("/incidents")
    def incidents(workspace_id: UUID = Query(...),
                  operator: str = Depends(require_operator)):
        return {"items": run(lambda: store_factory().list_incidents(operator, workspace_id))}

    @router.post("/incidents/{incident_id}/acknowledge")
    def acknowledge(incident_id: UUID, operator: str = Depends(require_operator)):
        return run(lambda: store_factory().acknowledge(operator, incident_id))

    return router
