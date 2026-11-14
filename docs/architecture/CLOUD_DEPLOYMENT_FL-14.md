# FleetLuma — cloud architecture decision (FL-14)

**Date:** 2026-11-14 · **Status:** approved implementation baseline, **not deployed**.  
**Decision owner:** FleetLuma university project.  
**Jira epic-sized tasks:** [FL-14](https://adambenarbia.atlassian.net/browse/FL-14) through [FL-20](https://adambenarbia.atlassian.net/browse/FL-20).

## Goal and constraints

Extend the working, local-LAN design to a public HTTPS demonstration without replacing or breaking its local SQLite fallback. Preserve the seven FL-6 API paths and the Flutter Android app. Keep each change on a Jira-linked feature branch with CI and an independently reviewable PR. Only record cloud deployment as completed after actual HTTPS API and browser tests. The **physical two-machine** acceptance test is still [FL-13](https://adambenarbia.atlassian.net/browse/FL-13), not solved by deployment alone.

## Target diagram

- **Flutter Web** static build on one Vercel project, and the **Flutter Android** app share UI, models and state; both call the backend over HTTPS.
- **FastAPI coordinator** runs as short-lived Vercel Python Functions in a **separate** Vercel project.
- **Supabase PostgreSQL** (project `FleetLuma`, region `eu-central-1`) stores host registrations, time-series samples, latest process snapshot, HTTP service configurations and check results.
- **Python agents** remain on physical Windows/Linux hosts. Outbound, HTTPS-only authenticated push; never include host identity in a trusted field of the request body.
- **Scheduled HTTP checker** runs independently of FastAPI request handlers. Proposed first iteration: Supabase scheduled Edge Function every **60 seconds** for **approved public endpoints**. Keep the 20-second in-process checker only in local deployment mode.
- **Supabase Auth** signs in dashboard operators; FastAPI verifies JWT issuer, signature (via JWKS or supported verification), expiry and audience, then authorizes fleet access. A backend-only secret/DB role accesses private tables. The browser never receives privileged database credentials.

## Deployment modes

| Mode | Frontend | Backend | Data | HTTP checks |
| --- | --- | --- | --- | --- |
| `local` | Flutter Android / local Web | Uvicorn | SQLite | In-process worker, trusted LAN targets |
| `cloud` | Vercel static Web + Android | Vercel Python Function | Supabase PostgreSQL | External scheduled checker, explicitly configured public targets |

Local SQLite development remains available while cloud mode is built and tested; tests for existing endpoints must remain green in both modes.

## Required refactors

1. **FL-15 PostgreSQL:** Create migration-reviewed `fleetluma` private schema using `uuid`, `timestamptz`, `jsonb`, constraints, indexes, and a transactional persistence adapter. Do not run schema DDL from request handlers/startup. Implement UTC receipt-based freshness and 24-hour retention. Use Supabase's **transaction pooler** for short-lived serverless connections, with TLS and credentials exclusively in Vercel server-side environment variables. Verify with real DB transaction tests before changing production.
2. **FL-16 Vercel FastAPI:** Build a supported Python Function entry point, cloud configuration, readiness check and behavior tests. No Python daemon/thread scheduled by an API startup event in cloud mode. Avoid mutable filesystem state; don't confuse a successful Vercel build with a working database connection.
3. **FL-17 Flutter Web:** Eliminate `dart:io` imports from browser-compiled files, use platform-compatible networking (`package:http` or supported equivalent), generate a web platform target and run web-target compilation/CI, retaining Android support. API base URL is compiled into the browser build (not a secret).
4. **FL-18 public API security:** Add Supabase Auth operator access, backend JWT verification, origin allowlist for browser CORS and distinct agent bearer auth. Public GET routes must not remain unauthenticated in cloud mode. Supabase service-role/secret keys are **never** in web or Android bundles. Private data schema must not be exposed to Supabase Data API clients. Validate RLS/grants and denial cases.
5. **FL-19 checks/retention:** Move recurring service probes and 24-hour cleanup out of request-driven Vercel functions. No arbitrary URL input, redirects, proxy inheritance or internal target SSRF. An authenticated scheduler must be least-privileged; store its key in Supabase Vault/project secrets. Check maximum invocation, timeouts and free-tier limits before enabling.
6. **FL-20 deploy and verify:** Create Vercel web+API projects in Adam's `fleet-luma` team, connect GitHub `Adam-BArbia/fleetluma`, configure preview/prod environment settings with the user (never paste credentials into Jira or commits), verify auth, Postgres persistence, agent ingestion via public HTTPS and browser dashboard. Save actual URLs, build and smoke-test evidence in Jira.

## Trust boundaries / operational safety

- Browser users are authenticated **operators**, and agents have independent unique bearer tokens; never use the same credentials for both.
- `Authorization` headers for agent ingestion must not be logged.
- Backend-to-Postgres uses pooled encrypted connections, with least-privilege DB role. Supabase `public` is not a place to expose token hashes or raw process data.
- Cloud checks can reach **public internet endpoints** only. LAN-only HTTP services are not reachable from the cloud; use local checker or future opt-in agent reporting.
- Retention: keep only the required 24-hour samples/checks; perform cleanup on a schedule and explicitly document aggregation/capacity assumptions.
- CORS must allow the known Vercel Web origin(s), **not** `*` when credentials are used. CORS is not authentication.
- Avoid dashboard endpoints exposed publicly prior to implementing FL-18. Enable preview protection or no deployment until authentication passes.
- Free-plan quotas and background execution change; validate deployment limits at implementation time. The cloud target is a *demo*, not an uptime guarantee.

## Order, verification and rollback gates

1. [FL-14](https://adambenarbia.atlassian.net/browse/FL-14): architecture committed with UML; CI validates syntax. **No runtime change.**
2. [FL-15](https://adambenarbia.atlassian.net/browse/FL-15): schema and adapter, tests on real Postgres; local SQLite remains green.
3. [FL-17](https://adambenarbia.atlassian.net/browse/FL-17) can proceed independently: browser-compatible Flutter network client, Web build and tests.
4. [FL-18](https://adambenarbia.atlassian.net/browse/FL-18) before exposing live cloud API reads to the Internet.
5. [FL-16](https://adambenarbia.atlassian.net/browse/FL-16), [FL-19](https://adambenarbia.atlassian.net/browse/FL-19): runtime and scheduler integration only after required persistence/security boundaries.
6. [FL-20](https://adambenarbia.atlassian.net/browse/FL-20): provision/deploy in preview first, verify, then enable public if authorized.

**Rollback:** Existing `main` local runtime, SQLite schema, Android build and per-agent local configuration remain usable; revert independent cloud PRs or switch back to local mode if the hosted path fails. Keep actual migrations reversible where possible. Database backups and secret rotation should be tested separately.

## Known current state (verified, 2026-11-14)

- Vercel Adam account `adam-barbia`; team `fleet-luma` is accessible and contains **zero projects**.
- Supabase FleetLuma project `mulsyhgdigonccziywet` is healthy, PostgreSQL 17 in `eu-central-1`; **no public application tables** or migration records.
- GitHub current local implementation uses `sqlite3` direct SQL, `on_event(startup)` for provisioning and background worker, `dart:io` for mobile network transport; needs the above changes.
- FL-13 physical test remains outstanding; this cloud decision is not evidence of it.
