# FleetLuma v0.1.0 — private pilot release gate

**Status (2026-11-21): RELEASE BLOCKED; only `v0.1.0-rc.1` private candidate is allowed.**

The canonical architecture is `docs/uml/plantuml/30_cloud_deployment.puml`; the actively maintained end-to-end onboarding and rollback plan is **[PAIRING_ACTIVATION_RUNBOOK.md](PAIRING_ACTIVATION_RUNBOOK.md)**.

## Verified

- TUFFEST Windows agent previously reported via the legacy token pilot, including CONNECTED/STALE transition, with metrics in the deployed Flutter Web.
- Live Supabase `fleetluma` schema contains one TUFFEST host and 85 preserved samples (verified immediately after the pairing migration).
- Reviewed additive migration `fleetluma_workspace_pairing_v01` version `20261121224711` has been applied. One private workspace and its owner were backfilled; no pairing sessions were present.
- After migration, the existing API health endpoint still returned `200 {"status":"ready","mode":"cloud"}`.
- Windows installer and service acceptance on an isolated GitHub Windows runner: PR #46.
- Debian agent and systemd package acceptance on an isolated GitHub Ubuntu runner: PR #45.
- Real agent HTTP pairing and revocation through FastAPI and PostgreSQL in isolated CI: PR #47.
- Workspace-scoped host detail/history/process protection: PR #48.
- Pairing Web UI is feature-gated. `/devices/pair` deep-link and gated preview build: PR #49, subject to CI/merge.

## Not yet verified

- Pairing through a real installed agent + the deployed cloud API + the deployed Flutter Web on a physical Windows 11 and Linux machine.
- Secure upgrade/reinstall, real reboot retention, approved operator UX, restore-from-backup procedures and final signed end-user packages.
- Exact production deployment/alias/configuration review and rollback rehearsal.
- Independent validation for optional HTTP service checks and retention jobs.

## Release decision

**Do not tag or announce `v0.1.0`** until the detailed controls in [PAIRING_ACTIVATION_RUNBOOK.md](PAIRING_ACTIVATION_RUNBOOK.md) pass and the results are recorded in Jira FL-20.

The old manual WSL token-provisioning method was a **legacy private pilot exercise** and is not the approved onboarding experience for this release. Device pairing must be initiated locally by the background service, approved by an authenticated operator in the dashboard, and persisted in OS-protected storage. Never instruct ordinary users to copy reporting tokens or database URLs between machines.
