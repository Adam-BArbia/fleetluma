-- FL-32: add workspace ownership and pairing state to the private cloud schema.
-- REVIEWED DESIGN MIGRATION; NOT AUTOMATICALLY EXECUTED IN PRODUCTION.
-- Preconditions: Supabase auth.users exists; single-user private pilot has one
-- account. With >1 auth users and no workspace, abort instead of guessing owner.
-- All DDL and backfill run in one transaction; existing host UUIDs/samples remain.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

CREATE TABLE IF NOT EXISTS fleetluma.workspaces (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL CHECK (char_length(trim(name)) BETWEEN 2 AND 80),
  created_by uuid NOT NULL REFERENCES auth.users(id),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS fleetluma.workspace_memberships (
  workspace_id uuid NOT NULL REFERENCES fleetluma.workspaces(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role text NOT NULL CHECK(role IN ('owner','admin','viewer')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (workspace_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_fl_memberships_user ON fleetluma.workspace_memberships(user_id,workspace_id);

ALTER TABLE fleetluma.hosts ADD COLUMN IF NOT EXISTS workspace_id uuid;
ALTER TABLE fleetluma.hosts ADD COLUMN IF NOT EXISTS lifecycle text NOT NULL DEFAULT 'ACTIVE';
ALTER TABLE fleetluma.hosts ADD COLUMN IF NOT EXISTS enrolled_at timestamptz;
ALTER TABLE fleetluma.hosts ADD COLUMN IF NOT EXISTS revoked_at timestamptz;
ALTER TABLE fleetluma.hosts ADD COLUMN IF NOT EXISTS agent_version text;
ALTER TABLE fleetluma.hosts ADD COLUMN IF NOT EXISTS credential_version integer NOT NULL DEFAULT 1;
ALTER TABLE fleetluma.services ADD COLUMN IF NOT EXISTS workspace_id uuid;

DO $migration$
DECLARE bootstrap_user uuid;
DECLARE bootstrap_workspace uuid;
BEGIN
  IF EXISTS (SELECT 1 FROM fleetluma.hosts WHERE workspace_id IS NULL)
     OR EXISTS (SELECT 1 FROM fleetluma.services WHERE workspace_id IS NULL) THEN
    IF (SELECT count(*) FROM auth.users) <> 1 THEN
      RAISE EXCEPTION 'FL-32: ambiguous bootstrap operator; abort and use explicitly reviewed ownership mapping';
    END IF;
    SELECT id INTO STRICT bootstrap_user FROM auth.users;
    SELECT id INTO bootstrap_workspace
      FROM fleetluma.workspaces WHERE created_by = bootstrap_user ORDER BY created_at LIMIT 1;
    IF bootstrap_workspace IS NULL THEN
      INSERT INTO fleetluma.workspaces(name,created_by)
        VALUES ('Personal Fleet',bootstrap_user) RETURNING id INTO bootstrap_workspace;
    END IF;
    INSERT INTO fleetluma.workspace_memberships(workspace_id,user_id,role)
      VALUES(bootstrap_workspace,bootstrap_user,'owner')
      ON CONFLICT(workspace_id,user_id) DO NOTHING;
    UPDATE fleetluma.hosts SET workspace_id=bootstrap_workspace WHERE workspace_id IS NULL;
    UPDATE fleetluma.services SET workspace_id=bootstrap_workspace WHERE workspace_id IS NULL;
  END IF;
END
$migration$;

-- No ghost/ownerless active rows. A fresh DB needs an explicit authorized
-- bootstrap workspace before first enrollment.
ALTER TABLE fleetluma.hosts ALTER COLUMN workspace_id SET NOT NULL;
ALTER TABLE fleetluma.services ALTER COLUMN workspace_id SET NOT NULL;
ALTER TABLE fleetluma.hosts
  ADD CONSTRAINT fl_hosts_workspace_fk FOREIGN KEY(workspace_id)
  REFERENCES fleetluma.workspaces(id);
ALTER TABLE fleetluma.services
  ADD CONSTRAINT fl_services_workspace_fk FOREIGN KEY(workspace_id)
  REFERENCES fleetluma.workspaces(id);
ALTER TABLE fleetluma.hosts
  ADD CONSTRAINT fl_hosts_lifecycle CHECK(lifecycle IN ('ACTIVE','REVOKED'));
ALTER TABLE fleetluma.hosts
  ADD CONSTRAINT fl_hosts_credential_version CHECK(credential_version > 0);
CREATE INDEX IF NOT EXISTS idx_fl_hosts_workspace ON fleetluma.hosts(workspace_id,name);
CREATE INDEX IF NOT EXISTS idx_fl_services_workspace ON fleetluma.services(workspace_id,name);

CREATE TABLE IF NOT EXISTS fleetluma.pairing_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_code_hash text NOT NULL UNIQUE CHECK(user_code_hash ~ '^[a-f0-9]{64}$'),
  device_code_hash text NOT NULL UNIQUE CHECK(device_code_hash ~ '^[a-f0-9]{64}$'),
  report_token_hash text NOT NULL CHECK(report_token_hash ~ '^[a-f0-9]{64}$'),
  client_key_hash text NOT NULL CHECK(client_key_hash ~ '^[a-f0-9]{64}$'),
  display_name text NOT NULL CHECK(char_length(display_name) BETWEEN 1 AND 64),
  platform text NOT NULL CHECK(platform IN('windows','linux')),
  agent_version text NOT NULL CHECK(char_length(agent_version) BETWEEN 1 AND 64),
  capabilities jsonb NOT NULL DEFAULT '[]'::jsonb CHECK(jsonb_typeof(capabilities)='array'),
  status text NOT NULL DEFAULT 'PENDING'
     CHECK(status IN('PENDING','APPROVED','CONSUMED','DENIED','EXPIRED','CANCELLED')),
  expires_at timestamptz NOT NULL,
  attempts int NOT NULL DEFAULT 0 CHECK(attempts >= 0 AND attempts <= 1000),
  next_poll_at timestamptz,
  approved_by uuid REFERENCES auth.users(id),
  workspace_id uuid REFERENCES fleetluma.workspaces(id),
  host_id uuid REFERENCES fleetluma.hosts(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  approved_at timestamptz,
  consumed_at timestamptz,
  CHECK(expires_at > created_at),
  CHECK(status NOT IN('APPROVED','CONSUMED') OR
    (approved_by IS NOT NULL AND workspace_id IS NOT NULL AND host_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_fl_pairing_expiry ON fleetluma.pairing_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_fl_pairing_state ON fleetluma.pairing_sessions(status,created_at);
CREATE INDEX IF NOT EXISTS idx_fl_pairing_client_window
 ON fleetluma.pairing_sessions(client_key_hash,created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_fl_pairing_host_consumed
 ON fleetluma.pairing_sessions(host_id) WHERE status IN('APPROVED','CONSUMED');

-- An operator cannot approve merely by guessing a UUID.
CREATE TABLE IF NOT EXISTS fleetluma.pairing_reviews (
  pairing_id uuid NOT NULL REFERENCES fleetluma.pairing_sessions(id) ON DELETE CASCADE,
  operator_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  reviewed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(pairing_id,operator_id)
);

-- Persisted throttling survives ephemeral Vercel function instances.
CREATE TABLE IF NOT EXISTS fleetluma.pairing_rate_limits (
  scope text NOT NULL CHECK(scope IN('create','resolve')),
  subject_digest text NOT NULL CHECK(subject_digest ~ '^[a-f0-9]{64}$'),
  window_start timestamptz NOT NULL,
  attempts integer NOT NULL DEFAULT 1 CHECK(attempts >= 0),
  PRIMARY KEY(scope,subject_digest)
);

CREATE TABLE IF NOT EXISTS fleetluma.device_audit_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  host_id uuid REFERENCES fleetluma.hosts(id),
  pairing_id uuid REFERENCES fleetluma.pairing_sessions(id),
  workspace_id uuid REFERENCES fleetluma.workspaces(id),
  actor_user_id uuid REFERENCES auth.users(id),
  action text NOT NULL CHECK(char_length(action) BETWEEN 1 AND 60),
  created_at timestamptz NOT NULL DEFAULT now(),
  details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK(jsonb_typeof(details)='object')
);
CREATE INDEX IF NOT EXISTS idx_fl_audit_workspace_time
 ON fleetluma.device_audit_events(workspace_id,created_at DESC);

-- Private schema inaccessible to browser-facing Supabase API roles.
ALTER TABLE fleetluma.workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE fleetluma.workspace_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE fleetluma.pairing_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE fleetluma.pairing_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE fleetluma.pairing_rate_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE fleetluma.device_audit_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA fleetluma FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA fleetluma FROM PUBLIC, anon, authenticated;

COMMIT;
