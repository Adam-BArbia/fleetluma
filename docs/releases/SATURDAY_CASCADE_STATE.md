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

## Explicit deferrals
- General process termination/kill and remote command execution are NOT in Saturday release. A safe proof of concept would need a separate narrowly authorized command architecture and agent changes.
- Native PDF exports and public signup are NOT in Saturday release.

## Completion gate
CI must pass, cloud Web must load repeatedly in Firefox + Chrome, backend must connect to real Supabase, HTTP checker must persist real checks, metrics/processes must come from actual paired agents, and user must complete final Web + Android acceptance. Do not mark project ready or merge to the released branch before these gates are met.
