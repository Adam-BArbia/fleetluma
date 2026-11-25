# FleetLuma - Final integrated acceptance for Saturday 2026-11-28

**Workflow:** The operator performs one full user-style acceptance session only after automated checks and integration gates pass. Intermediate source changes are verified by CI, never by repeatedly asking the operator to test unfinished views.

## 2026-11-25 production rollout and remaining physical acceptance

**Deployment completed:** merged PR #69 into main at `c10c10429e6858d1147806d6a1bb80ed7ea3dfdc`, with exactly the same Git tree (`2cda690caa3c66d40124f88b8a2e1b645343539c`) as passing integrated source `107e3d525b306ec90ec8e10142ca86a6472f4091`. All 9 integrated source checks passed. All 7 push-to-main workflow checks passed.

- **API live:** `https://fleetluma-api.vercel.app` now aliases verified READY deployment `dpl_G4tYdg4LXfEVFpxyXgfNjup1pGHK`. GET `/health` returned HTTP 200, `{"status":"ready","mode":"cloud"}`. API runtime error/fatal scan for deployment over 30 minutes returned zero matching logs. Backend still enforces Supabase JWT, explicit operator access, workspace-scoped monitoring. **Previous API alias**: `dpl_47nWXoujANGbTdsHU5jhTaGi7Gs3`.
- **Web live:** `https://fleetluma-web.vercel.app` now aliases Vercel READY Flutter static preview `dpl_5gUPwPLd5VBUAuiHr1bMxKz8xHMD` built from squash commit `c10c104` with cloud-API origin, Supabase publishable key and pairing UI. HTTP GET returned 200 for both `/` and `/flutter_bootstrap.js`. **Previous Web alias**: `dpl_2Q5Uxyi9MWSym7x5U2kNf1X1nQee`.
- **Android:** main push CI `45642608489` PASS, produced `fleetluma-android-debug-apk` but that regular workflow's default is emulator `10.0.2.2` (NOT the phone acceptance build). Install **cloud-configured APK** `fleetluma-integrated-cloud-android-debug-apk` from workflow run `45640481543`, artifact `15036165190`. Source `107e3d5` and merged main share the same verified Git tree. Artifact is a debug/demo build, not a signed Play Store release.
- **Real monitoring:** owned service `FleetLuma API (demo target)`, workspace-scoped in database, checked every minute by Vault-authenticated Supabase Edge worker. Live query observed 22 checks in the hour, 20 HEALTHY 200, with experimental failed results honestly preserved. The latest observed 15:17 UTC record was `HEALTHY 200`, `354.79 ms`. Independent 15-minute retention job continues running.
- **Final status:** physical Web + Android user acceptance remains **NOT PERFORMED** by ChatGPT. This chat runtime cannot control the operator's Android phone or browser session, and cannot verify signed-in rendered service graphs remotely. Execute the one final manual scenario below with real account and both devices. Do not mark those checks Done until observed.
- **Rollback**: reassign `fleetluma-api.vercel.app` to prior API deployment ID and `fleetluma-web.vercel.app` to prior Web deployment ID using the Vercel account. Retention and independent checker need no rollback unless unexpected failures occur.

## Release identity

- Source branch: `feat/saturday-cascade-integrated` / draft PR #69
- Preserve last-known working Vercel Web/API aliases and Android APK for rollback
- Cloud API is stateless Vercel FastAPI; monitoring agents are background Windows/Linux services
- Sign-in is Supabase Auth; server enforces workspace membership and separate agent credentials
- UI is Flutter Web rich dashboard, Flutter Android simple dashboard

## Release blocker gates (automated / maintainer)

- [ ] Flutter analyze, mobile tests, Web build, backend pytest, PostgreSQL integration, cloud preview contract CI PASS at the exact release commit
- [ ] FL-22 white-screen cause: browser console/network reviewed in Firefox and Chrome
- [ ] No public sign-up, privileged client keys, injected fake telemetry or unrestricted cross-origin access
- [ ] Agent reports and historical samples persist to real private Supabase
- [ ] Service monitoring: at least one approved public HTTPS service, 1 real scheduled check persisted, authenticated Web query shows status and time, service latency graph derives from persisted rows
- [ ] HTTP SSRF checks: exact hostname allowlist, HTTPS, no redirect following, deny private/special-use DNS results, outbound egress constraints, cron secret protection
- [ ] Private alert migration reviewed/backed up before applying; API and Web flags remain off unless complete stack works
- [ ] Font can render Inter when online; confirm useful fallback without network
- [ ] No errors in Flutter Web and Android artifact build, no fatal CI or unreviewed dependency changes
- [ ] Preview rollback metadata and exact deployment IDs captured before promotions

## ONE final user-style scenario (operator, Web + Android)

1. Open Web in Firefox from a new session; login. Reopen with cache and reload. Confirm no white screen. Repeat on Chrome.
2. Sign in to the *same account* on Android debug APK. Both remain independently usable.
3. Observe both Windows and Linux host cards with real CPU/RAM/disk metrics; verify stale/connected transitions accurately.
4. Inspect each host's 15m / 1h / 24h history (real data); export CSV and open in spreadsheet software.
5. Expand **Top 10 Processes** for a live host; check PID, name, CPU, memory and freshness. No Kill button should be present.
6. Open **Manage devices**: pair a separate disposable agent, approve it, rename it, then revoke it; observe revoked reports being rejected. Do not revoke TUFFEST.
7. Inspect HTTP service health and last check timestamps and latency history. Simulate outage only against a *test endpoint you own*, not an unrelated public provider.
8. If alert feature enabled, add a CPU threshold for a safe test host, generate real load, acknowledge incident, return to normal and verify automatic resolution; edit and archive rule. Otherwise mark alerts explicitly unavailable.
9. Confirm all read and write operations are scoped to the current authorized workspace.
10. Sign out on Web, verify protected API data disappears; Android session remains independently valid.
11. Verify ready/signed-off release artifacts match tested commit and no extra production changes were introduced.

## Safe fallback

If cloud checker, alert migration or Web startup cannot pass final validation, disable optional feature flags and use the last working dashboard. Never claim a feature works when only source code exists.

## Suggested grading narrative

Start with FleetLuma's problem (multi-host monitoring), then distributed architecture, pairing/security, time-series telemetry, authenticated CRUD, historical analysis, HTTP probing if truly active, tests, and GitHub/Jira/Scrum traceability. Show real measurements only.
