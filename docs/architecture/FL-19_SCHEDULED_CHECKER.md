# FL-19 — Cloud HTTP checker and 24-hour cleanup (staged)

This module is **not deployed**. The existing local FastAPI in-process
checker remains used for LAN deployment, and the Vercel API entrypoint never
runs a background worker.

Cloud mode would deploy the `fleetluma-checker` Supabase Edge Function
to the FleetLuma project, with:
- `FLEETLUMA_DB_URL`: encrypted **server-side** PostgreSQL transaction
  pooler DSN for the private fleetluma schema.
- `FLEETLUMA_CRON_SECRET`: random high-entropy shared secret, stored in
  Supabase function secrets and Vault for the scheduler.
- `FLEETLUMA_CHECK_ALLOWED_HOSTS`: explicit comma-separated *public*
  DNS hostnames, never input from an end-user API.

The function runs on a 60-second cron schedule, checks at most ten enabled
services sequentially, allows HTTPS on default port with hostname allowlist,
never follows redirects or proxy settings, and stores independent HTTP health
results in PostgreSQL. Network/timeouts are persisted as UNHEALTHY.
It purges metric and service-check samples older than 24h.

**No cloud checker can contact a machine reachable only inside a private LAN.**
For private demo services, the existing local worker remains the correct choice.

Security: DNS rebinding must also be ruled out by operational egress controls
and trustworthy allowlisted endpoints; domain allowlisting alone does not
guarantee arbitrary hosts are safe. Do not enable this scheduled function
for internet exposure without reviewing the token boundary and Edge Function
gateway verification mode. The example Cron SQL is intentionally commented
out and must **not** be applied without deployment + secret checks.

Test `deno test` validates input checks, HTTP status handling, and network
errors without probing any public websites. FL-19 remains In Progress until
the actual scheduled invocation, Vault setup, retention and real checker run
are independently verified.
