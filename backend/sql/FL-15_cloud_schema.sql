-- FL-15: FleetLuma private PostgreSQL schema for the cloud deployment.
-- This file is reviewed source SQL, NOT automatically run at FastAPI startup.
-- Run in an authorized Supabase project only after schema review.
BEGIN;

CREATE SCHEMA IF NOT EXISTS fleetluma;
REVOKE ALL ON SCHEMA fleetluma FROM PUBLIC;
REVOKE ALL ON SCHEMA fleetluma FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA fleetluma REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA fleetluma REVOKE ALL ON TABLES FROM anon, authenticated;

CREATE TABLE IF NOT EXISTS fleetluma.hosts (
    id uuid PRIMARY KEY,
    name text NOT NULL CHECK (length(trim(name)) > 0),
    os text NOT NULL CHECK (os IN ('linux', 'windows')),
    token_hash text NOT NULL UNIQUE CHECK (token_hash ~ '^[a-f0-9]{64}$'),
    last_seen_at timestamptz
);

CREATE TABLE IF NOT EXISTS fleetluma.samples (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    host_id uuid NOT NULL REFERENCES fleetluma.hosts(id) ON DELETE CASCADE,
    sampled_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    metrics jsonb NOT NULL CHECK (jsonb_typeof(metrics) = 'object')
);
CREATE INDEX IF NOT EXISTS idx_fl_samples_host_received
    ON fleetluma.samples(host_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_fl_samples_received
    ON fleetluma.samples(received_at);

CREATE TABLE IF NOT EXISTS fleetluma.process_snapshots (
    host_id uuid PRIMARY KEY REFERENCES fleetluma.hosts(id) ON DELETE CASCADE,
    captured_at timestamptz NOT NULL,
    processes jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(processes) = 'array')
);

CREATE TABLE IF NOT EXISTS fleetluma.services (
    id uuid PRIMARY KEY,
    host_id uuid REFERENCES fleetluma.hosts(id) ON DELETE SET NULL,
    name text NOT NULL CHECK (length(trim(name)) > 0),
    url text NOT NULL,
    enabled boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS fleetluma.service_checks (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    service_id uuid NOT NULL REFERENCES fleetluma.services(id) ON DELETE CASCADE,
    checked_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL CHECK (status IN ('HEALTHY','UNHEALTHY')),
    http_code integer CHECK (http_code BETWEEN 100 AND 599),
    latency_ms double precision CHECK (latency_ms >= 0),
    failure_kind text NOT NULL CHECK (failure_kind IN ('none','http_error','timeout','network_error'))
);
CREATE INDEX IF NOT EXISTS idx_fl_service_checks_service_time
    ON fleetluma.service_checks(service_id, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_fl_service_checks_time
    ON fleetluma.service_checks(checked_at);

-- Deny read access from browser-facing PostgREST roles, even if a future
-- deployment mistakenly includes this schema in exposed API schemas.
ALTER TABLE fleetluma.hosts ENABLE ROW LEVEL SECURITY;
ALTER TABLE fleetluma.samples ENABLE ROW LEVEL SECURITY;
ALTER TABLE fleetluma.process_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE fleetluma.services ENABLE ROW LEVEL SECURITY;
ALTER TABLE fleetluma.service_checks ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON ALL TABLES IN SCHEMA fleetluma FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA fleetluma FROM PUBLIC, anon, authenticated;

COMMENT ON SCHEMA fleetluma IS 'Private FleetLuma monitoring data. No direct browser/Data API access.';

COMMIT;
