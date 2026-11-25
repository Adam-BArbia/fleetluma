-- FL-36: private 24-hour monitoring retention, independent of HTTP probes.
-- This migration only creates a least-privilege database function.
-- It does NOT delete records or install a Cron job when applied.
BEGIN;
CREATE OR REPLACE FUNCTION fleetluma.prune_expired_history()
RETURNS TABLE(samples_deleted bigint, checks_deleted bigint)
LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog
AS $retention$
BEGIN
  DELETE FROM fleetluma.samples
  WHERE received_at < now() - interval '24 hours';
  GET DIAGNOSTICS samples_deleted = ROW_COUNT;

  DELETE FROM fleetluma.service_checks
  WHERE checked_at < now() - interval '24 hours';
  GET DIAGNOSTICS checks_deleted = ROW_COUNT;

  RETURN NEXT;
END;
$retention$;
REVOKE ALL ON FUNCTION fleetluma.prune_expired_history()
  FROM PUBLIC, anon, authenticated;
COMMENT ON FUNCTION fleetluma.prune_expired_history()
  IS 'Trusted in-database 24h history cleanup; not exposed to operators or Data API.';
COMMIT;
