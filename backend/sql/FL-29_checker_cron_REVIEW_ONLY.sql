-- FleetLuma HTTP checker: MANUAL REVIEW TEMPLATE, NOT AUTOMATICALLY APPLIED.
-- This is *not* a migration; do not add to production startup or migrations.
-- Preconditions: approved DNS/egress strategy, tested legacy JWT-compatible
-- service authorization, separate >=32-character Cron shared secret, and
-- Vault + pg_net + pg_cron installed by an authorized administrator.
--
-- In Supabase Vault, provision by dashboard WITHOUT printing values:
-- fleetluma_checker_gateway_jwt  -- JWT-compatible Bearer credential
-- fleetluma_checker_cron_secret  -- identical to FLEETLUMA_CRON_SECRET in Edge
-- The worker MUST have FLEETLUMA_PUBLIC_PROBES_ENABLED=true and exact
-- FLEETLUMA_CHECK_ALLOWED_HOSTS set separately. Never commit their values.
--
-- WARNING: Supabase pg_net temporarily stores headers in the internal
-- request queue in decrypted form. Privileged DB users can read them.
-- Prefer the latest Supabase 'auth: secret' scheme after reviewing migration
-- from the currently deployed verify_jwt=true protocol.

DO $preflight$
DECLARE jwt_len int;
DECLARE shared_len int;
BEGIN
  IF to_regclass('cron.job') IS NULL OR
     to_regclass('vault.decrypted_secrets') IS NULL THEN
    RAISE EXCEPTION 'FleetLuma checker: missing trusted Cron/Vault setup';
  END IF;
  SELECT length(decrypted_secret) INTO jwt_len
    FROM vault.decrypted_secrets
    WHERE name='fleetluma_checker_gateway_jwt';
  SELECT length(decrypted_secret) INTO shared_len
    FROM vault.decrypted_secrets
    WHERE name='fleetluma_checker_cron_secret';
  IF coalesce(jwt_len,0) < 32 OR coalesce(shared_len,0) < 32 THEN
    RAISE EXCEPTION 'FleetLuma checker: required Vault credentials absent';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM fleetluma.services
    WHERE enabled=true
      AND url='https://fleetluma-api.vercel.app/health'
  ) THEN
    RAISE EXCEPTION 'FleetLuma checker: approved service not enabled';
  END IF;
END
$preflight$;

-- After a successful one-off authenticated HTTP test and DB persisted sample,
-- run this statement to create an ACTIVE once-per-minute Cron schedule.
-- The job should be removed/disabled immediately after final testing if
-- secrets, DNS, or egress policy is not secure.
--
-- SELECT cron.schedule(
--   'fleetluma-checker-1m',
--   '* * * * *',
--   $FL_JOB$
--     SELECT net.http_post(
--       url := 'https://mulsyhgdigonccziywet.supabase.co/functions/v1/fleetluma-checker',
--       headers := jsonb_build_object(
--         'Content-Type', 'application/json',
--         'Authorization', 'Bearer ' || (
--           SELECT decrypted_secret
--           FROM vault.decrypted_secrets
--           WHERE name='fleetluma_checker_gateway_jwt'
--         ),
--         'x-fleetluma-cron', (
--           SELECT decrypted_secret
--           FROM vault.decrypted_secrets
--           WHERE name='fleetluma_checker_cron_secret'
--         )
--       ),
--       body := '{"source":"fleetluma-cron"}'::jsonb,
--       timeout_milliseconds := 10000
--     );
--   $FL_JOB$
-- );
--
-- Roll back a job without deleting checks:
-- SELECT cron.unschedule('fleetluma-checker-1m');
