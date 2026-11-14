# FL-20 — Secure preview release gate

**Date:** 2026-11-14
**Jira:** https://adambenarbia.atlassian.net/browse/FL-20
**Status:** Work in progress. No Vercel deployments or URLs are live.

## Verified connected projects

- Vercel team `fleet-luma`, account Adam: project `fleetluma-api`
  (ID `prj_79KJMB2276tvo7lTd553lhfMWNt4`) configured for FastAPI
  from `backend/`.
- Vercel project `fleetluma-web`
  (ID `prj_HJbg7XUp7GRVPATZpgvbB4HeXTU7`) configured for static
  Flutter Web output; use `mobile/build/web/`.
- Both projects currently have zero environment variables, **no Git
  auto-deployment link**, no deployed URL and no production traffic.
- Supabase FleetLuma: project `mulsyhgdigonccziywet` in Frankfurt,
  private `fleetluma` schema migration applied.
- Supabase security advisor shows five informational RLS-without-policy
  notices for the private monitoring tables. This is **intentional deny
  for browser-facing roles**: anon/authenticated have neither schema
  USAGE nor SELECT privileges. Do not create permissive policies to
  silence informational checks.

## Required environment configuration (no secrets in repository)

API Vercel project, configured directly in encrypted environment settings:
- `FLEETLUMA_MODE=cloud` (plain, nonsecret)
- `FLEETLUMA_SUPABASE_URL=https://mulsyhgdigonccziywet.supabase.co` (plain)
- `FLEETLUMA_OPERATOR_IDS`: authorized Supabase Auth operator UUIDs
  (server-only allowlist; do not confuse with credentials)
- `FLEETLUMA_WEB_ORIGINS`: explicit final HTTPS Vercel Web origin
  (not wildcard)
- `FLEETLUMA_DATABASE_URL`: **secret** pooled PostgreSQL DSN from
  Supabase *Connect* dialog, including valid TLS settings. Must never
  be sent in chat, logs, or a GitHub commit.

Flutter Web build (only public values, in CI build environment):
- `FLEETLUMA_CLOUD_MODE=true`
- `FLEETLUMA_API_BASE_URL`: actual verified HTTPS API origin
- `FLEETLUMA_SUPABASE_URL`: public project origin
- `FLEETLUMA_SUPABASE_PUBLISHABLE_KEY`: public publishable key only,
  never a secret/service-role API key or DB password.

## Git integration and build strategy

Do **not** connect the two Vercel projects to the repository with
automatic production deployments until environment settings and access
protections are reviewed. The Flutter SDK is **not installed by default**
in Vercel's generic static builder. Build Flutter Web in GitHub Actions
(`flutter build web --release`) and deploy the verified static output
with a review-gated Vercel CLI `--prebuilt` pipeline or upload mechanism.
Do not point Vercel at `mobile/` and assume a static build appears
automatically. The API can use the reviewed Python FastAPI entry point
`backend/api/index.py`, but it will fail closed until variables exist.

## Release test protocol

1. Recheck GitHub main SHA and both Vercel project IDs.
2. Configure Vercel preview environment and Supabase project. Never
   reveal secret values in CI artifact, logs, PR comments or Jira.
3. Confirm Supabase Auth signing keys: cloud verifier currently
   accepts asymmetric RS256/ES256 with JWKS. If tokens are issued using
   a legacy symmetric key, stop and migrate signing keys safely first.
4. Provision an operator in Supabase Auth through the admin console.
   Turn off public self-registration for this private class demo.
5. Create **preview** builds only, with Vercel deployment protection.
6. Run `python scripts/verify_cloud_preview.py https://<API>.vercel.app`
   to verify `/health` returns 200 and unauthed fleet reads return 401.
   If deployment protection responds 401/403, run through an authorized
   secure bypass workflow rather than disabling protection.
7. Sign in with the real operator via Flutter Web. Verify authorized
   `GET /api/v1/hosts` and rejected invalid/expired/wrong-user tokens.
8. Provision test agent credentials only through a privileged backend
   admin operation, push a genuine report from an agent over HTTPS,
   verify host heartbeat + metrics persist in Supabase.
9. Enable safe approved public service checks and scheduled 24h
   retention only after FL-19 gateway/egress/Vault review.
10. Save actual URLs, build SHA, authenticated and unauthenticated
    smoke-test evidence in Jira FL-18/FL-19/FL-20. Close each issue
    **only after** acceptance tests actually pass.

## Blocking observations

- There are **no configured Vercel variables**, and the backend
  cannot start in cloud mode without DB credentials and an operator allowlist.
- No public cloud deployment exists and no operator account was verified.
- This runbook does not authorize making an unprotected production
  deployment.
- Keep local SQLite/LAN and Android builds available as fallback for
  the November 16 university presentation.
