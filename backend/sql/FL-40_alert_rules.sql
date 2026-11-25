-- Proposed additive private-schema migration for FleetLuma alert-rule CRUD.
-- Stage only. Do not apply to the demo DB before review and a backup.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

CREATE TABLE IF NOT EXISTS fleetluma.alert_rules (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES fleetluma.workspaces(id),
  host_id uuid NOT NULL REFERENCES fleetluma.hosts(id),
  metric text NOT NULL CHECK (metric IN ('cpu_pct','ram_pct','disk_pct')),
  threshold_pct numeric(5,2) NOT NULL CHECK (threshold_pct >= 1 AND threshold_pct <= 100),
  consecutive_required smallint NOT NULL DEFAULT 2 CHECK (consecutive_required BETWEEN 1 AND 5),
  enabled boolean NOT NULL DEFAULT true,
  archived_at timestamptz,
  created_by uuid NOT NULL REFERENCES auth.users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS fl_alert_rules_workspace ON fleetluma.alert_rules(workspace_id,host_id);
CREATE INDEX IF NOT EXISTS fl_alert_rules_active_host
  ON fleetluma.alert_rules(host_id) WHERE enabled AND archived_at IS NULL;

CREATE TABLE IF NOT EXISTS fleetluma.incidents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_id uuid NOT NULL REFERENCES fleetluma.alert_rules(id),
  workspace_id uuid NOT NULL REFERENCES fleetluma.workspaces(id),
  host_id uuid NOT NULL REFERENCES fleetluma.hosts(id),
  metric text NOT NULL CHECK (metric IN ('cpu_pct','ram_pct','disk_pct')),
  threshold_pct numeric(5,2) NOT NULL,
  observed_value numeric(6,2) NOT NULL,
  status text NOT NULL CHECK (status IN ('OPEN','ACKNOWLEDGED','RESOLVED')),
  opened_at timestamptz NOT NULL DEFAULT now(),
  acknowledged_at timestamptz,
  acknowledged_by uuid REFERENCES auth.users(id),
  resolved_at timestamptz,
  last_value numeric(6,2) NOT NULL,
  last_seen_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS fl_incidents_one_active
  ON fleetluma.incidents(rule_id) WHERE status IN ('OPEN','ACKNOWLEDGED');
CREATE INDEX IF NOT EXISTS fl_incidents_workspace_opened
  ON fleetluma.incidents(workspace_id,opened_at DESC);

CREATE TABLE IF NOT EXISTS fleetluma.alert_rule_state (
  rule_id uuid PRIMARY KEY REFERENCES fleetluma.alert_rules(id) ON DELETE CASCADE,
  consecutive_breaches smallint NOT NULL DEFAULT 0 CHECK (consecutive_breaches BETWEEN 0 AND 5),
  last_received_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fleetluma.incident_events (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  incident_id uuid NOT NULL REFERENCES fleetluma.incidents(id),
  event_type text NOT NULL CHECK (event_type IN ('OPENED','ACKNOWLEDGED','RESOLVED','ARCHIVED')),
  actor_id uuid REFERENCES auth.users(id),
  observed_value numeric(6,2),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS fl_incident_events_incident ON fleetluma.incident_events(incident_id,created_at);

-- All tables remain exclusively in the private fleetluma schema.
-- The app's restricted backend role must be granted only the required CRUD;
-- do not grant the public anon or authenticated PostgREST roles access.
COMMIT;
