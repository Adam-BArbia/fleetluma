-- FleetLuma HTTP checker: REVIEW-ONLY reference, NOT an automatic migration.
-- No Cron job is scheduled by this file. Only the preflight DO block runs if
-- manually executed. Never paste secret values into SQL or GitHub.
--
-- Designed for Supabase Edge Function source with
-- withSupabase({auth:'secret:fleetluma-checker'}) and verify_jwt=false,
-- NOT the older JWT + x-fleetluma-cron protocol still deployed as v2.
--
-- 1. In FleetLuma Supabase Settings > API Keys, create a NAMED secret API key
--    named 'fleetluma-checker'. The secret MUST stay server-side.
-- 2. Store this one key using the Supabase Vault UI under the name
--    'fleetluma_checker_api_key'. The Cron caller sends it in 'apikey'.
-- 3. The function must deploy with the named-key guard and gateway
--    verify_jwt=false. Without the guard the endpoint would be public.
-- 4. Set FLEETLUMA_CHECK_ALLOWED_HOSTS to the exact approved hostname
--    fleetluma-api.vercel.app and FLEETLUMA_PUBLIC_PROBES_ENABLED=true
--    only after egress/DNS preflight and a successful one-off check.
-- 5. Independently verify the named key using one authorized request.
--
-- IMPORTANT: pg_net stores outgoing HTTP headers in an internal queue,
-- potentially visible to privileged database roles. Protect those roles.
-- The DNS-to-connect race needs a reviewed egress policy before activation.

-- Guarded readiness check. Does NOT create a Cron job.
DO $preflight$
DECLARE configured_key text;
BEGIN
  IF to_regclass('cron.job') IS NULL OR
     to_regclass('vault.decrypted_secrets') IS NULL THEN
    RAISE EXCEPTION 'FleetLuma checker: Cron or Vault is not configured';
  END IF;
  SELECT decrypted_secret INTO configured_key
    FROM vault.decrypted_secrets
    WHERE name='fleetluma_checker_api_key';
  IF configured_key IS NULL OR
     left(configured_key,10) <> 'sb_secret_' OR
     length(configured_key) < 32 THEN
    RAISE EXCEPTION 'FleetLuma checker: named API key absent in Vault';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM fleetluma.services
    WHERE enabled=true
      AND url='https://fleetluma-api.vercel.app/health'
  ) THEN
    RAISE EXCEPTION 'FleetLuma checker: approved service is disabled';
  END IF;
END
$preflight$;

-- REVIEW-ONLY: after one verified check row, uncomment and execute.
-- SELECT cron.schedule(
--   'fleetluma-checker-1m',
--   '* * * * *',
--   $FL_JOB$
--     SELECT net.http_post(
--       url := 'https://mulsyhgdigonccziywet.supabase.co/functions/v1/fleetluma-checker',
--       headers := jsonb_build_object(
--         'Content-Type', 'application/json',
--         'apikey', (
--           SELECT decrypted_secret
--           FROM vault.decrypted_secrets
--           WHERE name='fleetluma_checker_api_key'
--         )
--       ),
--       body := '{"source":"fleetluma-cron"}'::jsonb,
--       timeout_milliseconds := 10000
--     );
--   $FL_JOB$
-- );
--
-- Roll back this job without removing recorded measurements:
-- SELECT cron.unschedule('fleetluma-checker-1m');
