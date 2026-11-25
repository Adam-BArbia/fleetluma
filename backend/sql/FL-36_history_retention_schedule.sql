-- FL-36: trusted SQL-only 24-hour retention, no network/HTTP requests.
-- Apply AFTER FL-36_history_retention_function.sql passed CI.
-- Runs at most 4 times/hour. Newer samples and host/process metadata remain.
-- Unlike the optional HTTP checker, this schedule requires NO secret API key.
SELECT cron.schedule(
  'fleetluma-history-retention-15m',
  '*/15 * * * *',
  $retention_job$SELECT * FROM fleetluma.prune_expired_history();$retention_job$
);
-- Rollback the JOB (without restoring/deleting any rows):
-- SELECT cron.unschedule('fleetluma-history-retention-15m');
