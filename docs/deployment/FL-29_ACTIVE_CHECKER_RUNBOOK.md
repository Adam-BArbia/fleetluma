# FleetLuma scheduled HTTP checker — activated configuration (FL-29/30/31)

**Scope:** FleetLuma Supabase project `mulsyhgdigonccziywet`, one administrator-approved public HTTPS target only. No arbitrary LAN, localhost, private-IP or user-provided URL probing.

## Verified on 2026-11-25

- Edge Function `fleetluma-checker` version **12**, `verify_jwt=false` paired with `withSupabase({auth:'secret:fleetluma_checker'})`.
- Named secret API key is stored exclusively in Supabase Vault under `fleetluma_checker_api_key`; the key value is not in GitHub, mobile, Web or this document.
- Function environment: `FLEETLUMA_CHECK_ALLOWED_HOSTS=fleetluma-api.vercel.app`, `FLEETLUMA_PUBLIC_PROBES_ENABLED=true`.
- Enabled service: `FleetLuma API (demo target)` => `https://fleetluma-api.vercel.app/health`. Other services remain disabled.
- Native Deno TLS transport: validated public A records, `Deno.connect` to the prevalidated IPv4, `Deno.startTls` with original hostname for SNI/CA validation. No second DNS lookup, no redirects, no arbitrary port, hard 4-second deadline. Dual-stack hostnames are safe: AAAA records cannot be dialed.
- Successful authorized **single live check** at 2026-11-25 14:58:19 UTC: persisted `HEALTHY`, HTTP `200`, `335.51 ms`, `failure_kind=none`. Earlier failed experimental checks remain honestly recorded as `UNHEALTHY`.
- Cron job ID **2**, name `fleetluma-checker-1m`, expression `* * * * *`; invokes Edge Function with a Vault-backed `apikey` header through `pg_net`. The separate FL-36 retention Cron job runs every 15 minutes.
- **Recurring execution independently verified:** `cron.job_run_details` reported job 2 **succeeded** at 2026-11-25 14:59:00 UTC. The function persisted a new row at 14:59:01 UTC: `HEALTHY`, HTTP `200`, `276.61 ms`, `failure_kind=none`. This confirms the one-minute schedule actually invokes the checker.
- Earlier IP-pinned Node `https.request` attempts could not initialize in the hosted Edge Runtime; after public IPv4 validation the safe Deno-native `Deno.connect` plus `Deno.startTls` implementation produced real HTTP 200 results. Dual-stack DNS is allowed because only pinned IPv4 is dialed.

## Three consecutive automatic HTTP 200 checks confirmed

The SQL Cron execution records show job 2 succeeded at **14:59, 15:00, and 15:01 UTC** on 2026-11-25, with corresponding persisted checks:

| UTC check timestamp | Status | HTTP | Measured latency |
|---|---|---:|---:|
| 14:59:01 | HEALTHY | 200 | 276.61 ms |
| 15:00:01 | HEALTHY | 200 | 356.01 ms |
| 15:01:00 | HEALTHY | 200 | 338.54 ms |

All three results are real database observations from the hosted Edge Runtime. The two previous experimental `UNHEALTHY` records remain available for accurate history. No other service is enabled; no production FastAPI/Web/Android promotion occurred.

## Authentication proof

- Missing `apikey` request returned HTTP `401 MISSING_CREDENTIALS`.
- Valid Vault key with probes disabled returned HTTP `503 Checker is not configured`.
- Valid Vault key with approved target and flags enabled returned HTTP `200` from worker and persisted actual HTTP `200` from owned Vercel target.
- Supabase's registered secret key is named `fleetluma_checker` (underscore); the Edge Function slug remains `fleetluma-checker` (hyphen). These names are intentionally different.

## Safe manual verification

Run these *read-only* queries in the correct FleetLuma project:

```sql
SELECT jobid, jobname, schedule, active
FROM cron.job WHERE jobname IN
  ('fleetluma-checker-1m', 'fleetluma-history-retention-15m');

SELECT jobid, status, start_time, end_time, return_message
FROM cron.job_run_details WHERE jobid=2
ORDER BY start_time DESC LIMIT 5;

SELECT s.name, c.checked_at, c.status, c.http_code, c.latency_ms, c.failure_kind
FROM fleetluma.service_checks c
JOIN fleetluma.services s ON s.id=c.service_id
ORDER BY c.checked_at DESC LIMIT 10;
```

## Stop/rollback

```sql
SELECT cron.unschedule('fleetluma-checker-1m');
UPDATE fleetluma.services SET enabled=false
WHERE url='https://fleetluma-api.vercel.app/health';
```

Disable `FLEETLUMA_PUBLIC_PROBES_ENABLED` in Edge Function secrets to stop *all* outbound probes at the handler, independently of Cron. Revoke the named Supabase key only if compromised. Do **not** revoke or edit the unrelated default secret key. Preserve existing history, agents, Android, and production Vercel aliases.

## Still required for release

- Confirm first automatically scheduled check appears, plus retention of recent check history.
- Validate workspace-scoped Web HTTP latency/status chart with actual persisted measurements, not synthetic demo data.
- Finish the same-account Web and Android user-style acceptance and review the API/Web release together.

Documentation represents deployment observations, not a guarantee that a remote service will always be healthy.
