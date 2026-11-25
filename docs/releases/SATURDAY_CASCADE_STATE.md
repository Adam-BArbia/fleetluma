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

## Remaining implementation cascade
1. Fix all CI failures on integrated branch. Revisit first-frame shell behavior, caching, Flutter analyzer and auth.
2. Match Figma Inter typography (source shows Inter, actual native font files not bundled yet); use consistent semantic typography, not guess exact token measurements.
3. Add downloadable authenticated CSV of real samples, 15m/1h/24h, with formula-injection defense and no credentials.
4. Activate/configure the approved cloud HTTP checker only after FL-29 / FL-31 security and secrets checks; real scheduled values are mandatory before marking HTTP done.
5. Validate agent pairing, rename, revoke, host/process/history workspace isolation and cloud/APK compatibility.
6. Add scoped alert rules and incidents only if core is stable. Design: evaluator on authenticated incoming metric reports; no new cron for CPU threshold. Prevent duplicate incidents and enforce ownership.
7. Refresh UML/API architecture and Jira based on implementation. Rehearse the single final manual journey.

## Explicit deferrals
- General process termination/kill and remote command execution are NOT in Saturday release. A safe proof of concept would need a separate narrowly authorized command architecture and agent changes.
- Native PDF exports and public signup are NOT in Saturday release.

## Completion gate
CI must pass, cloud Web must load repeatedly in Firefox + Chrome, backend must connect to real Supabase, HTTP checker must persist real checks, metrics/processes must come from actual paired agents, and user must complete final Web + Android acceptance. Do not mark project ready or merge to the released branch before these gates are met.
