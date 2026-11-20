# FL-20 — Protected FastAPI + Supabase cloud API rollout

Target: **FleetLuma Vercel team** / `fleetluma-api` (FastAPI, root directory `backend/`), **preview only**. Canonical architecture: `docs/uml/plantuml/30_cloud_deployment.puml`. Never use the unprotected classroom SQLite app as the hosted entrypoint.

## Pre-deployment verified state (2026-11-20)

- Supabase project `mulsyhgdigonccziywet` is healthy and migration `20261114115547_fleetluma_private_monitoring_schema` is applied.
- Tables: `fleetluma.hosts`, `samples`, `process_snapshots`, `services`, `service_checks` — private, RLS-enabled, no public Data API grants.
- Vercel `fleetluma-api` project exists, protected previews enabled and `backend/` root/fastapi selected, but no deployment yet.
- Existing Vercel preview configuration: `FLEETLUMA_MODE=cloud` and public `FLEETLUMA_SUPABASE_URL`. **Do not mistake an active Supabase database for Vercel connectivity.**

## Supply the missing protected Vercel Preview environment values

In **Vercel → FleetLuma team → fleetluma-api → Settings → Environment Variables**, configure on **Preview** only:

| Variable | Type / requirement |
| --- | --- |
| `FLEETLUMA_DATABASE_URL` | **Encrypted/sensitive**, real **transaction-pooler** PostgreSQL URI from **Supabase → Connect → Transaction pooler** (IPv4, normally port 6543), for the existing project. Enter directly in Vercel. Never commit or paste in chat. |
| `FLEETLUMA_OPERATOR_IDS` | Exact comma-separated UUIDs of explicitly approved Supabase Auth operators. No wildcard or invented placeholder identity. |
| `FLEETLUMA_SUPABASE_URL` | Project's public `https://...supabase.co` URL (already configured). |
| `FLEETLUMA_MODE` | `cloud` (already configured). |
| `FLEETLUMA_WEB_ORIGINS` | **Leave unset** during API-only protected preview so cross-origin browser requests are disabled. After Flutter Web preview is deployed, set only its real exact HTTPS origin, without path, query, user info or wildcard. Redeploy API afterwards. |

Select the **transaction mode** URI from the project's Connect panel; **do not invent the pooler region/host**. The code disables psycopg prepared statements and requires TLS. Vercel may not support Supabase free-tier direct IPv6 endpoints, so the direct `db.<ref>.supabase.co:5432` DSN is not a reliable replacement. The database credentials remain server-only. Use a dedicated scoped SQL user with appropriate private schema permissions/policies when provisioned and tested; otherwise protect the existing database user's URI as a sensitive secret and rotate if exposed.

**Supabase Auth prerequisite:** the backend supports **RS256 or ES256** project JWKS signatures only. Confirm the actual project's Auth signing-key algorithm before deploying real operators. Do not silently accept HS256 or turn off backend UUID allowlisting. Operator signups are not automatic approval.

## Preview deployment and acceptance

1. Verify the GitHub branch, passing backend tests, Vercel project ID and reviewer-approved configuration. Do not link to/create another account or team.
2. Deploy **preview** from the reviewed `main` commit with Vercel's FastAPI `backend/api/index.py` handler. Keep Vercel SSO/Deployment Protection enabled.
3. Test through an authenticated/protected Vercel session or approved automation bypass (never publish bypass token):
   - `GET /health` returns **200** only with the actual database reachable and access to the FleetLuma private schema; otherwise **503** and a generic unavailable response.
   - `GET /api/v1/hosts` without an operator token returns **401**; a fake/expired JWT also returns **401**.
   - No CORS allow-origin header when `FLEETLUMA_WEB_ORIGINS` is unset. Later, check that only the real Web preview origin is permitted.
   - Approved real operator JWT returns the fleet list (initially empty); an unapproved JWT is **403**.
   - Provision an actual unique agent token securely, POST a real HTTPS report, and confirm it is stored/read back in PostgreSQL.
4. Capture the preview URL, commit, protected test evidence and results in Jira FL-20. Do not mark production complete until real Web + Android + agents + checker acceptance passes.

## Troubleshooting

- **Vercel function fails during import:** inspect missing operator UUID allowlist, valid Supabase Auth origin, `FLEETLUMA_DATABASE_URL`, and current environment target. Never log environment values.
- **Health 503:** the DB URI is missing/incorrect, pooler networking or TLS fails, the `fleetluma` migration is missing, or SQL user has insufficient private table access. `SELECT 1` alone does not prove readiness.
- **401 on a valid login:** check Supabase project's actual JWT signing algorithm, JWKS, issuer and audience.
- **403 on a valid signed JWT:** its `sub` UUID has not been explicitly added to the server-side operator allowlist.

Never publish SQL credentials, personal tokens, or a bypass secret in GitHub/Jira/screenshots. Production deployment remains separately gated.
