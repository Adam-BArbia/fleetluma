# FleetLuma - Final integrated acceptance for Saturday 2026-11-28

**Workflow:** The operator performs one full user-style acceptance session only after automated checks and integration gates pass. Intermediate source changes are verified by CI, never by repeatedly asking the operator to test unfinished views.

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
