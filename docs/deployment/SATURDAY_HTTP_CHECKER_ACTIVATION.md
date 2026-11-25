# FL-29 / FL-31 — FleetLuma scheduled HTTP checker activation (completed)

**Status: ACTIVE for the one approved FleetLuma API target.** For current operational settings, evidence, stop/rollback SQL, and approved service boundaries, see [FL-29_ACTIVE_CHECKER_RUNBOOK.md](FL-29_ACTIVE_CHECKER_RUNBOOK.md).

## Actual deployment and security (2026-11-25)

- Supabase project `mulsyhgdigonccziywet`.
- Edge Function `fleetluma-checker` **version 12**, gateway `verify_jwt=false` coupled to `withSupabase({auth:'secret:fleetluma_checker'})`.
- API key `fleetluma_checker` saved privately in Supabase Vault as `fleetluma_checker_api_key`. **Never print its value or place it in the app/client, source, Jira, response bodies or log messages.**
- Function flags: `FLEETLUMA_CHECK_ALLOWED_HOSTS=fleetluma-api.vercel.app` and `FLEETLUMA_PUBLIC_PROBES_ENABLED=true`.
- Exactly one enabled `fleetluma.services` target: `https://fleetluma-api.vercel.app/health`.
- One-minute SQL-only trigger `fleetluma-checker-1m`, pg_cron job ID **2**; reads secret key from Vault at execution time and invokes the Edge Function using `pg_net`. HTTP responses/headers can be visible briefly to highly privileged DB roles in the pg_net request queue; protect database administrator access.
- Separate independent SQL-only FL-36 monitoring history retention job ID **1** runs every 15 minutes.

## Security proofs

1. Missing named key -> **401 MISSING_CREDENTIALS** before worker logic.
2. Valid named key with handler opt-in disabled -> **503 Checker is not configured**.
3. Valid named key with flag enabled and no active service -> `checked=0, skipped=0`, no network probe.
4. Approved target with initial dual-stack/Deno networking issues -> real `UNHEALTHY` outcomes preserved, no synthetic green check.
5. Fixed dual-stack validation to use **only public IPv4 A records** and ignore irrelevant AAAA answers. All A addresses are checked for private/special-use ranges.
6. Replaced unsupported Node HTTPS setup in the hosted Edge Runtime with **native Deno pinned TLS**: `Deno.connect({hostname: verifiedIp,port:443})`, then `Deno.startTls(tcp,{hostname: originalHost})` for SNI and CA hostname verification. No second DNS lookup, no private network target, no arbitrary port, redirects, proxies or credential forwarding.
7. One authorized actual HTTPS probe on the host: 2026-11-25 14:58:19 UTC, **HEALTHY / HTTP 200 / 335.51 ms** persisted to `fleetluma.service_checks`.
8. First automatically scheduled run: 2026-11-25 14:59:00 UTC, `cron.job_run_details.status=succeeded`; a fresh **HEALTHY / HTTP 200 / 276.61 ms** check was persisted at 14:59:01 UTC.

## Stopping safely

```sql
SELECT cron.unschedule('fleetluma-checker-1m');
UPDATE fleetluma.services
SET enabled=false
WHERE url='https://fleetluma-api.vercel.app/health';
```

You can additionally disable `FLEETLUMA_PUBLIC_PROBES_ENABLED` in Supabase Edge Function secrets, retaining the function and historical rows. Do **not** delete the FL-36 retention job or unrelated keys.

## Remaining release tasks

- Authenticated Web HTTP service status/latency chart should display **persisted real check rows** correctly.
- Verify exactly one workspace can access only its own services and history via the FastAPI JWT API.
- Merge/promotion and the same-user Web+Android full user-style acceptance remain separate gates; code compilation and Cron success are not proof that the client-release matching problem is solved.

Official Supabase references: https://supabase.com/docs/guides/functions/auth and https://supabase.com/docs/guides/functions/schedule-functions
