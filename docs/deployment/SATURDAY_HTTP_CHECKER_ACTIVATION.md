# FL-29 / FL-31 - Safe deployment gate for cloud HTTP checking

**State: PREPARED, NOT ACTIVE.** Do not call HTTP monitoring live based solely on compiled Flutter UI. The checked-in `supabase/functions/fleetluma-checker` source is the intended worker.

## Actual cloud observation (2026-11-25)

Read-only inspection of FleetLuma Supabase project `mulsyhgdigonccziywet`:
- `fleetluma.services`: **1 row**, the owned FleetLuma API /health target, **disabled**
- `fleetluma.service_checks`: **0 rows** (no monitoring data yet)
- Edge Function: **`fleetluma-checker` v2 deployed**, gateway `verify_jwt=true`, internal probe switch remains unset/off
- `pg_cron`, `pg_net`, `vault`: not yet installed. No scheduled job exists

The Web monitoring view shows a **disabled** service without a health sample until secure activation.

## Boundaries and prerequisites

- Use the existing **FleetLuma Supabase project only**. Do not reuse KTOB project's keys or URLs.
- Select **one HTTPS health endpoint that you own** and that is publicly reachable. Do not probe internal or special-use network addresses.
- Configure `FLEETLUMA_CHECK_ALLOWED_HOSTS` as a small exact approved-hostname list. The checker rejects credentials, query strings, ports, redirects and direct IP targets.
- Validate DNS and egress behavior against DNS rebinding. The current source intentionally rejects IPv6 answers and requires public IPv4; unsuitable dual-stack targets are skipped. **DNS prescreening is not a full solution to DNS rebinding.** Do not expose general arbitrary-URL checking.
- Provision encrypted private database access only to the Edge Function, never to Flutter. Do not publish credentials, service-role keys or Cron HMAC values in a chat, repository, or CI artifacts.
- Set a high-entropy `FLEETLUMA_CRON_SECRET` in function secrets and private scheduler configuration, with independent access checks. Source currently compares a separate `x-fleetluma-cron` **shared secret** (not an HMAC) before any database operations. Its gateway also uses `verify_jwt=true`: **new Supabase publishable/secret API keys are not JWTs and cannot simply be passed as `Authorization: Bearer ...` to this gateway.** Choose a documented, compatible service-to-service authentication strategy before writing the Cron request. Never disable gateway JWT verification without independently reviewing and implementing the Supabase `auth:'secret'` server-side authentication wrapper.
- Confirm pooled TLS connection works for the Edge runtime and that the restricted database role has only necessary read/check-insert/retention privileges.
- Review extension availability and ongoing plan limits before any Cron deployment.

## Activation sequence (do not skip)

1. Review `supabase/functions/fleetluma-checker/index.ts`, `checker.ts`, unit tests, DB schema and security review.
2. Verify trusted endpoint ownership and a stable IPv4-only public DNS response in the target environment. Verify no outbound access to private hosts is possible.
3. Prepare secret values **directly inside trusted Supabase controls**. Never paste them into generated source, SQL literals, console output or shared files.
4. **Already deployed:** verify gateway JWT checks and an unconfigured safe/disabled response (note that gateway rejects non-JWT callers before the handler). Do not test with production secrets in logs.
5. Enable required extensions as a reviewed independent migration; set a narrow job (at most 10 approved services every 60 seconds as currently designed). Confirm job runner and function authentication match.
6. Register a single authorized service linked to an existing workspace; keep all other services disabled.
7. Trigger one authorized check and verify an actual persisted `service_checks` row with status, HTTP code/failure kind, server time and latency.
8. Verify 24-hour metric/check retention and DB role boundaries; verify unauthorized tenant cannot read the service or its history.
9. Only then enable continuous scheduled checks and mark FL-29/FL-30/FL-31 ready for acceptance.


## 2026 Supabase service-to-service compatibility

Supabase's November 2026 documentation recommends **secret API keys** for server-to-server functions, via `withSupabase` and `auth: 'secret'` while setting `verify_jwt=false` in the function's gateway configuration. The current FleetLuma worker deliberately uses `verify_jwt=true` **plus** an independent 32+ character shared secret. These are **different** authentication protocols. Do not create a `pg_net` Cron job assuming that a new publishable key or secret API key is automatically a JWT. The existing handler's `x-fleetluma-cron` header by itself cannot bypass the gateway.

Two possible implementations, **neither active yet**:
- Keep the current gateway JWT requirement: provision an appropriate server-only **JWT-compatible** Authorization credential and a second independent shared secret; configure both through trusted, least-privilege secrets controls, and test the precise gateway compatibility before scheduling.
- Move to the current documented service-to-service model in a **separately reviewed change**: use `withSupabase(..., {auth:'secret'})` and `verify_jwt=false`; preserve explicit authorization for this specific checker and its database scope, and remove the obsolete shared-secret logic only once the replacement is verified.

**Security:** Supabase warns that `pg_net` stores decrypted request credentials temporarily in `net.http_request_queue`. Restrict database access, enforce least privilege and account for credential handling before accepting this design. Also, pre-resolving DNS before `fetch` has a DNS-to-connect race; outbound-network policy or an equivalent address-pinning transport must be reviewed before enabling an internet-facing URL monitor.

References: https://supabase.com/docs/guides/functions/schedule-functions and https://supabase.com/docs/guides/functions/auth

## Abort / rollback

- If any auth, DNS, egress or schema check fails, disable scheduler and `FLEETLUMA_PUBLIC_PROBES_ENABLED`, keep existing Web and API aliases untouched, and preserve monitoring data.
- Do not lower Edge Function authentication, add wildcard CORS, or expose private DB URLs to bypass an operational blocker.
- No hard-coded green sample. An unavailable checker must be represented as UNKNOWN and `No recorded HTTP checks`.

## Final user-style acceptance

After automation and configuration pass, the operator's one final walkthrough can inspect real HTTP success/error transitions and compare timestamps with genuine persisted rows. Until that point, this module remains a staged implementation dependency.
