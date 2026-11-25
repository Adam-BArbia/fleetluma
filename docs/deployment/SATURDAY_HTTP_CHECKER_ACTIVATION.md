# FL-29 / FL-31 — FleetLuma Scheduled HTTP Checker: Activation Gate

**Status on November 25, 2026: FUNCTION STAGED, NOT PROBING.** The checked-in checker is protected by Supabase's named secret-key authentication, but scheduled execution, approved egress and credential provisioning are **not** complete.

## Current confirmed deployment

- Supabase project: `mulsyhgdigonccziywet` (FleetLuma only).
- Edge Function: `fleetluma-checker`, **version 3**, deployed with `verify_jwt=false` because the function itself uses `withSupabase({auth:'secret:fleetluma-checker'})`. This is **not** an anonymous API: the named secret key must be accepted by the Supabase wrapper before the handler executes.
- `fleetluma.services`: one operator-owned approved target `https://fleetluma-api.vercel.app/health`, with **enabled=false**.
- `fleetluma.service_checks`: zero recorded checks at the last verified inspection.
- No scheduled job, Cron credentials, named secret API key or outbound-probe activation has been confirmed. `pg_cron`, `pg_net`, and Vault were absent at the previous extension inspection.
- `FLEETLUMA_PUBLIC_PROBES_ENABLED` must be the literal `true` and `FLEETLUMA_CHECK_ALLOWED_HOSTS` must contain a precise hostname. Both are intentionally unconfigured.
- `supabase/config.toml` explicitly records `[functions.fleetluma-checker] verify_jwt=false`; never remove the named secret-key guard while retaining this gateway setting.

## Authentication and credentials

Supabase's documented worker-to-worker integration accepts a **named secret API key** on the `apikey` header. The checker requires a specifically named key `fleetluma-checker` using `auth:'secret:fleetluma-checker'`, not a user JWT and not a publishable key.

An administrator must provision the dedicated secret key in **FleetLuma Supabase Settings → API Keys**, save its exact value privately as a Vault secret named `fleetluma_checker_api_key`, and verify it can invoke only the intended worker. Keep credentials out of the repository, logs, Flutter, screenshots and support messages. The old `FLEETLUMA_CRON_SECRET` and `x-fleetluma-cron` headers are **no longer used by version 3**.

With `verify_jwt=false`, the gateway alone does *not* authenticate calls. The wrapper is mandatory and its named-key enforcement must be verified against missing, malformed, publishable and unauthorized credentials before scheduling.

## Network security blocker

The source enforces exact approved HTTPS hostnames, no URL credentials/ports/query parameters, no redirect following, a 4-second timeout, and a public IPv4-only DNS precheck. **Pre-resolving DNS and subsequently calling `fetch(url)` does not pin the connection to that address.** Without an outbound-network policy that prevents DNS rebinding to internal, local or metadata addresses, the checker must **not** be activated as a general URL monitoring feature. Do not turn off DNS checks to fix a deployment failure.

The approved demo target is an endpoint controlled by the project, not an arbitrary user-submitted URL. A production-grade general-purpose checker still requires egress restrictions or an equivalent address-pinning transport and separate review.

## Activation plan (not yet executed)

1. Verify production Edge deployment is v3 with named secret-key authorization. Confirm that missing/bad API keys cannot reach the handler, without exposing credentials in logs.
2. Establish the outbound egress policy and DNS-to-connect protection. Verify the approved health endpoint's public DNS in the Edge runtime; do not rely on desktop DNS alone.
3. Provision a named FleetLuma checker secret key in the project and store it in Vault. Review potential `pg_net` storage of decrypted request headers and limit privileged DB access.
4. Review and enable extensions `pg_cron`, `pg_net` and Vault in the existing project only after appropriate backup and access checks. Do not install unrelated extensions.
5. Run the preflight portion of `backend/sql/FL-29_checker_cron_REVIEW_ONLY.sql` after dependencies are configured. This reference file intentionally leaves `cron.schedule` commented out.
6. Configure the exact hostname `fleetluma-api.vercel.app` and an approved Edge outbound network policy. Then deliberately enable `FLEETLUMA_PUBLIC_PROBES_ENABLED`.
7. Enable **only** the registered FleetLuma API test target, run a single authenticated request, and confirm its actual persisted `service_checks` row with latency, status, HTTP result and server timestamp.
8. Only after the single check passes, install a narrow one-minute job with the named key in the `apikey` header, audit query retention (24h), workspace separation, and revoked-key behavior.
9. Inspect Web HTTP health charts against actual database samples and mark Jira FL-29/30/31 complete **only** after final end-to-end acceptance.

## Rollback and fallback

- Disable `FLEETLUMA_PUBLIC_PROBES_ENABLED`, disable the service row, and `cron.unschedule('fleetluma-checker-1m')` if scheduling was ever enabled.
- Rotate/revoke the dedicated named secret key if any credential might have leaked.
- Preserve metric history, the stable FastAPI/Web release, the installed Android APK, and the existing agent pairing identities.
- Until real HTTP rows exist, display **DISABLED / UNKNOWN** and **No recorded HTTP checks**, never synthetic green health data.

Official references: https://supabase.com/docs/guides/functions/auth · https://supabase.com/docs/guides/functions/schedule-functions · https://supabase.com/docs/guides/functions/secrets.
