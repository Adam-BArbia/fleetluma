-- FleetLuma FL-29 scheduler prerequisite migration.
-- Applied to Supabase FleetLuma project mulsyhgdigonccziywet on 2026-11-25.
-- Supabase migration record: fleetluma_fl29_scheduler_extensions_only.
-- No Cron schedules and no network requests are created by this migration.
-- Vault already existed as extension supabase_vault; do not reinstall it.
CREATE EXTENSION IF NOT EXISTS pg_cron;
CREATE EXTENSION IF NOT EXISTS pg_net WITH SCHEMA extensions;
