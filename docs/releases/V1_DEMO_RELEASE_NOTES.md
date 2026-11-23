# FleetLuma V1 — classroom demo release candidate

**Release class:** `v1-demo-2026-11-23` — **private, unsigned classroom candidate**, not a production-grade signed software release.

## Deployment

- Dashboard: https://fleetluma-web.vercel.app
- Cloud coordinator: https://fleetluma-api.vercel.app
- Source: https://github.com/Adam-BArbia/fleetluma
- Operator access: invite-only Supabase Auth; no public signups.
- Current Web/API hostnames are explicitly assigned to pairing-enabled **preview-configured** Vercel deployments. Do not confuse this with an audited production promotion.

## What works in tested builds

- FastAPI + Supabase PostgreSQL Cloud, HTTPS agent metrics ingestion
- Operator login and scoped workspace/host access
- CPU/RAM/disk, connectivity/staleness, retained history and read-only process snapshots
- A dark Flutter Web dashboard with device approval/revocation UI
- Agent-generated one-time code, expiry, polling, scoped approval, revocation and protected agent credentials
- Windows background SCM service and elevated Tk setup companion, installed with unsigned Inno Setup candidate
- Linux background systemd service and Debian candidate with interactive `sudo fleetluma-setup`
- Android Cloud APK, debug-signed, with mobile device-management UI enabled

## Verified on 2026-11-23

- Existing TUFFEST identity and 85 historical samples preserved during staged activation.
- Vercel Web/API aliases verified against known READY deployments.
- Cloud API /health 200 ready/cloud, anonymous operator workspace 401, anonymous host listing 401/403.
- Pairing endpoint registered; generated/cancelled synthetic sessions in deployed Supabase; no synthetic host enrolled.
- Exact browser Origin CORS and authorization header preflight passed.
- Flutter Web analysis, unit/widget tests and build passed; paired Web preview built after the operator 401 gate.
- Windows signed? **NO**. Unsigned candidate build/install/service/pipe/ACL/uninstall tests passed in isolated Windows CI.
- A live cloud pairing initiation and cancellation was run from an **actually installed Windows SCM service** on a Windows GitHub runner (PR #64, isolated acceptance passed). No synthetic machine was approved.
- Linux signed? **NO**. Debian package install/systemd/socket/purge CI checks passed; interactive setup helper included.
- Android Cloud APK built and tests passed with operator authentication preflight.

## Download tested candidate artifacts

- Windows unsigned installer: https://github.com/Adam-BArbia/fleetluma/actions/runs/45141323996
- Linux unsigned .deb with setup helper: https://github.com/Adam-BArbia/fleetluma/actions/runs/45143131797
- Android Cloud pairing-enabled debug APK: https://github.com/Adam-BArbia/fleetluma/actions/runs/45144051084

GitHub Actions artifact links may require the user to sign in to GitHub to download.

## Onboard a Windows computer

1. On a Windows 11 x64 computer, obtain the reviewed unsigned installer artifact. Verify the build provenance; do not install artifacts from untrusted third parties.
2. Launch the installer with administrator approval; it registers FleetLumaAgent as an automatic background Windows service.
3. The installer opens FleetLuma Agent Setup. Click **Start pairing**. A short one-time code appears; no API token needs to be copied.
4. Click **Open FleetLuma dashboard**, sign in with an approved operator account, choose **Manage devices**, enter the code, verify this computer, approve.
5. Wait for the agent's next report and check the machine appears CONNECTED. Restart the service and confirm connectivity recovers; never describe stale readings as live.

## Onboard Linux

Install the Debian candidate through the system package manager as administrator. Run `sudo fleetluma-setup`, answer `y`, then approve the code at https://fleetluma-web.vercel.app. Native Linux graphical setup is not included.

## Outstanding before a general signed V1

- Physical Windows 11 and physical Linux user acceptance: full install, approval, reporting, reboot, revoke, upgrade/reinstall and cleanup.
- Independently verified restorable database backup / restore rehearsal and deployment rollback rehearsal.
- Windows installer code signing and package provenance checksums; signed Linux package policy.
- Final design review against the native Figma file (live Figma read quota was exhausted during the sprint).
- Live accepted operator end-to-end session on the presentation devices and Android hardware UX acceptance.
- Verify optional scheduled service checks/retention behavior before claiming those subsystems.

**Do not label an unsigned preview-configured candidate as a fully secure general-availability release.**

## Rollback

Known pre-pairing deployments:
- Web `dpl_6MucKNg6eWTcP6vES1eigPAR8jmj`
- API `dpl_C2LGLsEFZb1YuZ3m65iABz4HAPzy`

Restore both stable aliases to these deployments in Vercel if you need to suspend active pairing. Schema is additive: leave existing Supabase host/sample tables intact. Do not delete TUFFEST or issue new legacy credentials to bypass enrollment.
