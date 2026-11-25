# FL-29 / FL-31 - Safe deployment gate for cloud HTTP checking

**State: PREPARED, NOT ACTIVE.** Do not call HTTP monitoring live based solely on compiled Flutter UI. The checked-in `supabase/functions/fleetluma-checker` source is the intended worker.

## Actual cloud observation (2026-11-25)

Read-only inspection of FleetLuma Supabase project `mulsyhgdigonccziywet`:
- `fleetluma.services`: 0 rows
- `fleetluma.service_checks`: 0 rows
- Edge Functions: 0 deployed
- `pg_cron`, `pg_net`, `vault` not installed

Hence the Web monitoring view correctly displays the empty state until configuration.

## Boundaries and prerequisites

- Use the existing **FleetLuma Supabase project only**. Do not reuse KTOB project's keys or URLs.
- Select **one HTTPS health endpoint that you own** and that is publicly reachable. Do not probe internal or special-use network addresses.
- Configure `FLEETLUMA_CHECK_ALLOWED_HOSTS` as a small exact approved-hostname list. The checker rejects credentials, query strings, ports, redirects and direct IP targets.
- Validate DNS and egress behavior against DNS rebinding. The current source intentionally rejects IPv6 answers and requires public IPv4; unsuitable dual-stack targets are skipped. **DNS prescreening is not a full solution to DNS rebinding.** Do not expose general arbitrary-URL checking.
- Provision encrypted private database access only to the Edge Function, never to Flutter. Do not publish credentials, service-role keys or Cron HMAC values in a chat, repository, or CI artifacts.
- Set a high-entropy `FLEETLUMA_CRON_SECRET` in function secrets and private scheduler configuration, with independent access checks. Source currently checks an `x-fleetluma-cron` HMAC-style shared secret; confirm the chosen `verify_jwt` gateway mode and corresponding authorized request headers are compatible with the Cron invoker.
- Confirm pooled TLS connection works for the Edge runtime and that the restricted database role has only necessary read/check-insert/retention privileges.
- Review extension availability and ongoing plan limits before any Cron deployment.

## Activation sequence (do not skip)

1. Review `supabase/functions/fleetluma-checker/index.ts`, `checker.ts`, unit tests, DB schema and security review.
2. Verify trusted endpoint ownership and a stable IPv4-only public DNS response in the target environment. Verify no outbound access to private hosts is possible.
3. Prepare secret values **directly inside trusted Supabase controls**. Never paste them into generated source, SQL literals, console output or shared files.
4. Deploy the Edge Function in disabled mode first; validate that anonymous/missing-token requests fail and absent config produces a sanitized 503.
5. Enable required extensions as a reviewed independent migration; set a narrow job (at most 10 approved services every 60 seconds as currently designed). Confirm job runner and function authentication match.
6. Register a single authorized service linked to an existing workspace; keep all other services disabled.
7. Trigger one authorized check and verify an actual persisted `service_checks` row with status, HTTP code/failure kind, server time and latency.
8. Verify 24-hour metric/check retention and DB role boundaries; verify unauthorized tenant cannot read the service or its history.
9. Only then enable continuous scheduled checks and mark FL-29/FL-30/FL-31 ready for acceptance.

## Abort / rollback

- If any auth, DNS, egress or schema check fails, disable scheduler and `FLEETLUMA_PUBLIC_PROBES_ENABLED`, keep existing Web and API aliases untouched, and preserve monitoring data.
- Do not lower Edge Function authentication, add wildcard CORS, or expose private DB URLs to bypass an operational blocker.
- No hard-coded green sample. An unavailable checker must be represented as UNKNOWN and `No recorded HTTP checks`.

## Final user-style acceptance

After automation and configuration pass, the operator's one final walkthrough can inspect real HTTP success/error transitions and compare timestamps with genuine persisted rows. Until that point, this module remains a staged implementation dependency.
