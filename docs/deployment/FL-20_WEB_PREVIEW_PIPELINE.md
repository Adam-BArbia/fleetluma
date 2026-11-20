# FL-20 — Flutter Web protected preview release workflow

**Source of truth:** `docs/uml/plantuml/30_cloud_deployment.puml`. This is the **final cloud deployment architecture**, not the `09_deployment.puml` local two-machine classroom demo.

**Jira:** https://adambenarbia.atlassian.net/browse/FL-20

## What the workflow does

`.github/workflows/cloud-web-preview.yml` is a **manual, main-branch, preview-only** pipeline. It is intentionally never triggered automatically on a production deployment.

1. Always runs repository cloud-preview safety contract tests and checks that the final cloud deployment diagram is committed.
2. On **manual dispatch from main only**, proceeds to the protected `fleetluma-preview` GitHub Actions environment, where a required reviewer should approve the job.
3. Fails early unless all required PUBLIC Flutter configuration values and the private Vercel deploy token have been configured.
4. Generates the Flutter Web platform files, installs Flutter dependencies, runs static analysis and tests, then builds a **release** `mobile/build/web` bundle with `FLEETLUMA_CLOUD_MODE=true` and the requested real HTTPS Vercel API preview origin.
5. Packages the static Flutter bundle in Vercel **Build Output API v3** format: `.vercel/output/config.json` and `.vercel/output/static/` with a history fallback to `index.html`.
6. Pins the existing Adam-team Web project by ID and deploys with `vercel deploy --prebuilt --yes` (**no `--prod`**).
7. Reports the HTTPS preview URL and commit SHA to the GitHub Actions job summary.

Pull requests to this workflow run the nonsecret contract test job only. No Vercel API or Supabase database is deployed by this workflow.

## GitHub Actions environment setup (one-time, directly in Settings)

Create a GitHub Actions environment named `fleetluma-preview` and enable a **required reviewer**. Limit permitted deployment branches to `main`. Configure:

| Location | Name | Value classification | Purpose |
| --- | --- | --- | --- |
| Environment Secret | `VERCEL_TOKEN` | **Secret** | Least-privilege Vercel API token authorized for Adam's `fleet-luma` team |
| Environment Variable | `FLEETLUMA_SUPABASE_URL` | Public | `https://mulsyhgdigonccziywet.supabase.co` |
| Environment Variable | `FLEETLUMA_SUPABASE_PUBLISHABLE_KEY` | Public | Supabase **publishable** `sb_publishable_` key; **never** service-role or secret key |
| Environment Variable | `VERCEL_CLI_VERSION` | Public | Reviewed, exact Vercel CLI version in `MAJOR.MINOR.PATCH` form |

The workflow sets its Vercel org/project IDs from the already-provisioned Adam-team `fleetluma-web` project. It will **not** silently create/deploy to a different project.

Enter the token in GitHub Settings — **do not paste it into ChatGPT, Jira, repository, build logs, or screenshots**. A publishable key is designed for clients; agent secrets, DB passwords, Vercel tokens, and Supabase secret/service-role keys are not.

## Required real cloud prerequisites **before** manually dispatching

The Vercel API project `fleetluma-api` must be separately deployed to an HTTPS **protected preview** with:

- An authenticated FastAPI function and private PostgreSQL persistence in the Supabase `fleetluma` schema
- A server-side pooled TLS DSN and pre-applied reviewed migrations; no schema creation in request handlers
- Operator JWT issuer/JWKS verification, audience and UUID allowlisting; agent tokens stay separate
- Exact Web preview origin CORS allowlist (not `*`)
- A successful `GET /health` readiness probe and `401` on unauthenticated `GET /api/v1/hosts`
- Protection or secure bypass available for automated smoke tests, not disabled on a public endpoint

These tasks remain in **FL-18/FL-20**. The cloud HTTP service checker is an *external* Supabase scheduled Edge Function (FL-19) and must pass its independent egress/secret/cron review before enabling.

**Current provider check, 2026-11-20:** Vercel has `fleetluma-api` and `fleetluma-web` but **zero deployments**; PostgreSQL project is `ACTIVE_HEALTHY`; no Edge Functions deployed. Both Vercel projects have only nonsecret preview starter settings. No full release can be claimed.

## How to run once the gates pass

On GitHub: **Actions → FleetLuma cloud Web preview → Run workflow → select `main`**, then enter **the validated HTTPS origin-only API preview URL** (for example, a specific `https://...vercel.app` URL). Approve via the `fleetluma-preview` environment reviewer; inspect the resulting summary.

The input is a public **origin**, not a credential, and not `localhost`. Flutter Web embeds the API URL and publishable key into compiled assets. Both the API and Web previews should remain access-protected.

## Actual acceptance: not just a green CI job

Verify on real deployed URLs and document evidence in FL-20:

- [ ] API preview `/health` returns 200 **only when PostgreSQL is reachable**
- [ ] Unauthenticated reads denied (401), invalid/expired JWT denied
- [ ] Authorized operator can sign in and read the fleet through Flutter Web
- [ ] Distinct real Windows/Linux psutil agents POST HTTPS with tokens and see persisted metrics
- [ ] Persistent samples and process lists available; history gaps and STALE correctly represented
- [ ] Approved public HTTP checker scheduled independently, with state and latency, safe egress and 24-hour retention
- [ ] Flutter Android release builds and targets the same real HTTPS API endpoint
- [ ] No tokens leaked in logs, bundles or client storage; rollback demonstrated
- [ ] Preview deployment protection, CI source SHA, URLs, and test proof recorded in Jira
- [ ] Only promote reviewed/verified release to production through a separate, authorized gate

This workflow **does not** build a native Android APK, set up Supabase Auth, migrate the DB, install an Edge Function, deploy the API, or promote to production. It represents a single necessary delivery link in the final cloud deployment plan.

## Production handling

Do not switch from preview to production by adding a `--prod` flag to this workflow. Introduce a distinct reviewed production gate after the complete integration checklist passes, with separate production environment variables, staging and rollback evidence.
