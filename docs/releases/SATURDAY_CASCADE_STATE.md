# FleetLuma Saturday 2026-11-28 - Cascade Implementation State

> This is the handoff ledger for the integrated feature branch, **not** a claim of production release or on-device acceptance. Update it whenever the implementation state changes. Avoid storing secrets or test credentials.

## Baseline and safety
- Baseline main commit: `89e43f220912f93a27168af45c6e22b64dd17020`.
- Integration branch: `feat/saturday-cascade-integrated` (branched from FL-22 PR head `93c804dac94c1bb6535210612b1a2adaf099ae59`).
- Preserve the approved Android APK and existing paired Vercel Web/API aliases until release gates pass. Do not modify Android layout or agent enrollment contracts casually.
- Demo accounts are restricted; no public signup, fake metrics, arbitrary URL probing, remote shell, or unrestricted process termination.
- User wants **one final manual end-to-end experience test**, not repeated manual tests after every feature. Automated compiler, unit, security and CI checks still run during integration.

## Carried into integrated branch
- FL-22 PR #66: recoverable Flutter cloud startup widget, committed Web boot shell and preview caching constraints.
- FL-26 PR #67: authenticated read-only Web process explorer and its tests; explicitly NO process killing.
- FL-30 PR #68: authenticated Web HTTP health/check history panel and its tests; cloud scheduled checker NOT yet active.

## Implementation update - 2026-11-25 cascade pass
- Created the single integration PR #69 (draft): https://github.com/Adam-BArbia/fleetluma/pull/69.
- Combined FL-22, FL-26, FL-30 modules into this branch; standalone PRs #66-68 remain unmerged for traceability.
- Added Web real-history CSV export with spreadsheet-formula sanitization and conditional Web downloader. This is export, not a PDF generator.
- Selected Figma Inter through `google_fonts` 8.2.1; actual Inter font files are not bundled and first-use network fetching/offline resilience remains a final acceptance gate.
- Added `backend/sql/FL-40_alert_rules.sql` **STAGED ONLY**, `backend/fleetluma_backend/alerts.py`, feature-gated cloud routes + report-time evaluator, pure threshold transition tests, and an optional Web incident/rule UI. Both `FLEETLUMA_ALERTS_ENABLED` (API) and `FLEETLUMA_ALERTS_UI_ENABLED` (Web compile-time) default OFF.
- **Live Supabase read-only inspection**: the FleetLuma database has 4 host rows, 0 monitored services, 0 HTTP check rows, 0 Edge Functions, and no `pg_cron`/`pg_net`/`vault` extensions currently installed. Do not represent HTTP monitoring as operational.
- Device management Update gap closed: `HttpFleetDeviceApi.rename()` calls the existing protected PATCH /api/v1/operator/hosts/{id}; Manage Devices now exposes a rename dialog and widget coverage. No agent/auth/DB contract changes.
- Added PlantUML deployment and alert-lifecycle diagrams, plus `docs/releases/SATURDAY_FINAL_ACCEPTANCE.md` for the operator's one final manual user-style test.
- Existing Android package and stable Web/API preview aliases have not been changed.
- Pending: integrated Flutter/backend CI, narrow correction passes, HTTP function security/deployment, real paired-device checks, review/apply alert migration to non-production only before enabling the optional alerts subsystem, and final user-style test.

## Remaining implementation cascade (current status)

1. **Done in source**: FL-22 safe cloud-startup fallback and Web boot shell; diagnose actual intermittent white screen in the final browser acceptance.
2. **Done in source**: Figma Inter font selection through Google Fonts 8.2.1; verify offline/fallback visual behavior in final browser acceptance.
3. **Done in source**: authenticated Web-only Top 10 process explorer, genuine CPU/RAM/disk history and CSV export.
4. **Done in source**: device rename via protected PATCH, alongside existing pair/approve/revoke screens; final physical device/tenant authorization test still needed.
5. **Done in source, default OFF**: alert rule CRUD, transactional sample thresholds, OPEN/ACKNOWLEDGED/RESOLVED incident lifecycle, backend and Web tests, private additive FL-40 schema. Migration NOT applied; flags NOT enabled.
6. **Pending infrastructure**: cloud HTTP checker authorization and secrets, strict public-host allowlist and DNS/egress control, Supabase cron/pg_net/Vault activation, one real persisted check and retention verification. Source now supports default `SUPABASE_DB_URL` in Edge Functions; see `docs/deployment/SATURDAY_HTTP_CHECKER_ACTIVATION.md`.
7. **Pending release**: exact integrated CI status, merge/release approval gates, stable Web and Android artifact, final single user-style Web+Android acceptance. No live production deployment claimed.
8. **Traceability**: Jira FL-33 (CSV), FL-34 (alerts), FL-35 (rename) created, plus FL-22/26/29/30 updated. UML 33/34 and final acceptance script added.

## Implementation update - 2026-11-25 cloud staging
- **Supabase FleetLuma project** `mulsyhgdigonccziywet`: `fleetluma-checker` Edge Function deployed as **version 2** with `verify_jwt=true`. The function requires a separate high-entropy `x-fleetluma-cron` secret, explicit hostname allowlist and `FLEETLUMA_PUBLIC_PROBES_ENABLED=true`. None have been configured through this change. **Active deployment does NOT mean active probing.**
- **One owned API health destination registered, disabled**: `FleetLuma API (demo target)` at `https://fleetluma-api.vercel.app/health`, `enabled=false`. Vercel project `fleetluma-api` owns this domain and has no SSO/password protection. HTTP reachability from the Edge runtime still requires proof.
- **No HTTP samples yet**: `service_checks=0`; no Cron configured or executed; the Web UI correctly shows the disabled/never-checked state. `pg_cron`/`pg_net`/`vault` extensions remain absent.
- Checker hardening: 3xx redirects are now `UNHEALTHY` rather than successful, with a regression test; manual redirects are not followed. The Edge Function version 2 includes this code.
- Web freshness: the latency-history tile refreshes when the parent observes a newly persisted check timestamp.
- Full integrated CI at source revision `ee9a970172a7a888bdd3f9556ec8a41da5c2b653` passed all seven GitHub Actions workflows, including mobile APK artifact and backend tests; later revisions require their own final CI pass.
- Safe deployment gates still pending: verify public IPv4-only DNS from Edge and enforce network egress against rebinding, configure function secret/allowlist and approved Cron invoker without revealing credentials, then observe real persisted checks before enabling service and marking the feature complete.
- Existing Vercel release aliases, Android installed build and `main` have not been modified.

## Implementation update - hardened authenticated UI
- On failed authenticated refresh, Web host process snapshots, historical chart samples, HTTP service lists/check history, and alert-rule/incident collections now clear previously cached values rather than leaving them visible as current. Retry messages remain sanitized. This is especially important across session expiry and authorization changes.
- One deliberately disabled API health target and Edge checker v2 are provisioned; no scheduled traffic or fabricated HTTP health samples.
- Latest integrated source before this checkpoint: `87de016ff1feb97a907e3f98e047ba3ce09c910d`. Automated checks must pass for the next final source commit before production promotion.

## Implementation update - real alert lifecycle verification and scheduler handoff
- Added `backend/tests/test_alerts_postgres_integration.py` to exercise optional alert-rule CRUD and incident lifecycle against a **disposable PostgreSQL 17** server seeded with synthetic auth/workspace/agent identities.
- Updated `.github/workflows/postgres-integration.yml` to apply `FL-40_alert_rules.sql` in CI **only**, then verify live Postgres alert creation, acknowledgement, automatic resolution, event audit, duplicate prevention, viewer/outsider boundaries and revoked-agent rejection.
- Fixed the integration test's outsider case to demand privacy-preserving **404/KeyError** rather than revealing the existence of a different workspace's rule with 403.
- GitHub Actions `PostgreSQL integration (FL-15)` **passed** on commit `192f997934a4e38ddfb55d79447445302236351a`, including the new optional alert migration and scenario. The alert migration is **not** applied to the live FleetLuma Supabase database.
- Prepared `backend/sql/FL-29_checker_cron_REVIEW_ONLY.sql`: a commented-out Cron invocation template plus fail-closed Vault/extension preflight. **NOT executed.** Cloud checker remains intentionally disabled and target `enabled=false`.
- Updated `docs/deployment/SATURDAY_HTTP_CHECKER_ACTIVATION.md` to reflect Edge Function v2 and current Supabase JWT-vs-secret-key authentication differences. Do not schedule `pg_net` until gateway/secret compatibility and DNS-to-connect egress controls are verified.
- Latest branch as of this record: `2eb447a9a453a8e244a9ddfaa087d6d426f5fe2d`; automated CI still running for this exact commit.

## Preview API verification
- **Vercel API preview** build is READY for source `0b940496324d251b24f89bf590e39765b9155d18`.
- Preview deployment ID: `dpl_9XcWTHGqQH1iz7W4EANjASXuLzyg`; URL: `https://fleetluma-i1vec3xem-fleet-luma.vercel.app`.
- This is a non-production preview (`target=null`), with the previous production alias left intact.
- A successful Vercel build confirms packaging but not end-to-end runtime health, backend secret availability or database privileges. An unauthenticated web fetch of its `/health` endpoint was unavailable from the current environment; verify with trusted authenticated deployment inspection and the final user acceptance.
- The last validated PostgreSQL alert lifecycle regression passed in GitHub Actions at `192f997934a4e38ddfb55d79447445302236351a`. After the latest docs-only and review-only SQL changes, rerun all CI gates on the exact final head commit.

## Implementation update - named checker auth and automated regression guard
- Supabase Edge Function `fleetluma-checker` updated from v2 to **v3**, deployed with `verify_jwt=false` and an explicit `withSupabase({auth:'secret:fleetluma-checker'})` guard. The gateway no longer expects a user/JWT credential; the handler requires the specifically named Supabase secret API key on `apikey`. A gateway flag set to false **without** the wrapper would be unsafe, so they are versioned together.
- `supabase/config.toml` captures the required per-function gateway setting. This is a **service-to-service** endpoint, never a public monitoring API.
- The Cron preflight and REVIEW-ONLY SQL use a single Vault-backed named key `fleetluma_checker_api_key`; actual scheduling remains commented out. Latest authoritative guide: `docs/deployment/SATURDAY_HTTP_CHECKER_ACTIVATION.md`.
- Added `backend/tests/test_checker_release_guards.py` so Python CI detects removal of the named-key guard, the explicit probe opt-in switch, approved host validation, and accidental uncommenting of Cron schedule SQL.
- **Still disabled**: no named key/secret provisioned, no Cron, no egress approval, no service enable, and no persisted check. Do not treat deployed `ACTIVE` Edge function status as active probing. Live `main` API/Web aliases and existing Android remain unchanged.
- Security status: DNS prevalidation followed by `fetch(hostname)` is subject to a DNS-to-connect race. Do not activate general URL probing without outbound egress control, independent of CI status.
- GitHub Actions for commit `f1a7129a63a0fe980795f7d9691f55b224b12994` started; full CI acceptance remains pending on this exact revision.

## Implementation update - scheduler extension prerequisites
- **Live Supabase migration applied successfully:** `fleetluma_fl29_scheduler_extensions_only` installed `pg_cron` 1.6.4 and `pg_net` 0.20.4 in the **FleetLuma** project. Vault was already installed under actual extension name `supabase_vault` 0.3.2 (previous searches mistakenly looked for extension `vault`).
- No Cron job was created. Read-back verified **0** job names beginning `fleetluma`. No real HTTP probe was triggered, and the known FleetLuma API service row remains disabled.
- The exact additive SQL is versioned in `backend/sql/FL-29_scheduler_extensions.sql`, and the activation runbook is updated. This unblocks the infrastructure prerequisite **only**; the named secret key, Vault secret value, outbound egress/DNS-to-connect policy, single successful check and scheduling approval remain outstanding.
- Final source revision before this ledger update: `6aaaee7b443adaef2a7a569b442222537a29587f`; inspect exact-head CI before final build sign-off.

## Implementation update - private live alert schema applied
- The **additive migration** `fleetluma_fl40_alert_rules_private` was applied successfully to the actual FleetLuma Supabase database after the equivalent migration passed isolated PostgreSQL CI. No existing monitoring rows or host identities were edited.
- Verified new private tables: `fleetluma.alert_rules`, `alert_rule_state`, `incidents`, `incident_events`. All four have row-level security **enabled**; direct `anon` and `authenticated` read privileges remain **false**.
- At verification: `alert_rules=0`, `incidents=0`, and existing metrics still show `3034` received samples in the queried 24-hour window. `FLEETLUMA_ALERTS_ENABLED` and `FLEETLUMA_ALERTS_UI_ENABLED` remain **OFF**; there is no live incident evaluator or user-visible alert UI until explicitly enabled on a staged deployment.
- Supabase security advisor now reports additional informational `rls_enabled_no_policy` notices for these four tables. This is expected for the deliberately private, server-only FleetLuma schema with no public Data API grants; do not create broad authenticated RLS policies merely to silence the warning.
- Schema migration is recorded in Supabase migrations, distinct from the no-job scheduler extension migration; preserve both records for traceability.

## Explicit deferrals
- General process termination/kill and remote command execution are NOT in Saturday release. A safe proof of concept would need a separate narrowly authorized command architecture and agent changes.
- Native PDF exports and public signup are NOT in Saturday release.

## Completion gate
CI must pass, cloud Web must load repeatedly in Firefox + Chrome, backend must connect to real Supabase, HTTP checker must persist real checks, metrics/processes must come from actual paired agents, and user must complete final Web + Android acceptance. Do not mark project ready or merge to the released branch before these gates are met.
