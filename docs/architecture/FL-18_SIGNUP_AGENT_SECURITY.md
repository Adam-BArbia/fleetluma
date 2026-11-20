# FL-18 — FleetLuma authentication and secure agent transport

**Authoritative deployment diagram:** `docs/uml/plantuml/30_cloud_deployment.puml` (**not** classroom demo `09_deployment.puml`).

## Two separate trust boundaries

| Actor | Identity and authentication | Permission |
| --- | --- | --- |
| Dashboard operator (Flutter Web / Android) | Email/password with Supabase Auth; short-lived signed JWT verified server-side using JWKS and required issuer, audience, expiry and role; explicit `FLEETLUMA_OPERATOR_IDS` UUID allowlist | Read-only `GET /api/v1/hosts...` and service reads |
| Monitoring agent (Windows/Linux Python) | Unique random per-host bearer token sent over HTTPS to FastAPI; PostgreSQL stores **SHA-256 hash** of the token only, mapped to trusted host ID server-side | `POST /api/v1/agent/reports` only |

**Never** use a dashboard JWT as an agent token. **Never** send an agent token to Flutter, browser, Figma, code, GitHub, Jira, or a preview build. All cloud HTTP traffic must use HTTPS. Cloud metrics remain private and must not be exposed through the Supabase browser Data API.

## Operator account UX

- `SignInScreen`: email/password form, generic error message, button for account creation/access information.
- `SignUpScreen`: an actual `supabase_flutter.auth.signUp(email:, password:)` registration flow, **only compiled when** `FLEETLUMA_ALLOW_SELF_SIGNUP=true`. The default is **false**, so the page explains how to request an admin invitation instead of submitting registration.
- **Even if sign-up is enabled and succeeds, it does not grant monitoring permission.** The FastAPI gateway enforces `FLEETLUMA_OPERATOR_IDS`, independently of Supabase account creation. A logged-in user who is not on that list sees **Waiting for operator approval** and a sign-out control instead of the fleet.
- Flutter explicitly checks an authenticated fleet read before mounting `FleetScreen`; 401 prompts reauthentication/retry and 403 indicates missing operator approval. Network failures do not pretend the user is authorized.
- A new operator must verify their email where confirmation is enabled, and a project admin must add the operator UUID to the backend allowlist. **Never authorize a user based on editable Supabase `user_metadata`**.
- Do not create an unauthenticated admin invitation endpoint or automatically add newly registered accounts to the backend allowlist.

### Secure launch requirements

1. Keep Supabase Auth **Allow new users to sign up** disabled for invitation-only V1. Create/invite an account through the authorized Supabase admin interface. Allow a verified and explicitly approved UUID only. If enabling the optional registration UI, deliberately enable Supabase signups, require email confirmation, configure approved redirect URLs and anti-abuse/rate limits, and leave backend approval enforced.
2. For Web/Android cloud builds set `FLEETLUMA_CLOUD_MODE=true` and actual HTTPS API/Supabase URLs. A publishable `sb_publishable_...` key may be bundled publicly. **Never** bundle the service-role key, DB credentials, agent tokens or signing secrets.
3. Backend environment variables belong in the protected Vercel API project: `FLEETLUMA_MODE=cloud`, `FLEETLUMA_SUPABASE_URL`, `FLEETLUMA_WEB_ORIGINS` (exact HTTPS origins; not `*`), `FLEETLUMA_OPERATOR_IDS` and encrypted `FLEETLUMA_DATABASE_URL`.
4. Supabase Auth JWT signing must be RS256 or ES256 and have a valid JWKS endpoint. Legacy HS256 tokens are **rejected** by this API; migrate signing method before deployment rather than disabling verification.
5. Keep browser read access through FastAPI only; secure the private `fleetluma` PostgreSQL schema so `anon` and `authenticated` have no direct table privileges. Existing RLS-without-policies INFO notices on that intentionally private schema should not be silenced with broad policies.

## Agent setup for actual V1 cloud deployment

Agent environment (each physical host):

```text
FLEETLUMA_COORDINATOR_URL=https://<protected-api-origin>
FLEETLUMA_AGENT_CLOUD_MODE=true
FLEETLUMA_AGENT_TOKEN=<unique-random-per-host-secret>
FLEETLUMA_INTERVAL_SECONDS=10
FLEETLUMA_DISK_PATH=/
```

Use the appropriate disk path per operating system. Provision the agent's host UUID, name, OS and unique token through a trusted backend administration process **before** starting; only the hash is stored in PostgreSQL. Protect local secret storage using OS permissions and do not log, share or commit raw tokens.

The agent now validates that its coordinator URL is a base HTTP(S) origin **without embedded credentials, query, fragment or path** and disallows remote HTTP by default. Cloud mode additionally requires HTTPS even for localhost. It uses a no-redirect HTTP opener: a 301/302/307/308 response is treated as a failure, not a reason to replay the `Authorization` header to a redirect location.

**Temporary local demo exception only:** `FLEETLUMA_ALLOW_INSECURE_LAN=true` explicitly permits remote HTTP for an isolated classroom LAN. This must **never** be set for public/cloud V1. Plain HTTP on loopback is otherwise permitted only outside cloud mode.

### Trust model / threats covered

- JWT verification rejects tampered, expired, wrong-issuer, wrong-audience and non-allowlisted operator claims.
- Agent ingestion trusts the token-to-host database mapping, **not** host identity from a request body.
- Bearer tokens never travel over public cleartext HTTP; agent reports reject redirects.
- Operator clients cannot submit agent reports using their JWT; agents cannot query the dashboard using only their per-host token.
- Independent credentials can be revoked by removing an operator ID or rotating a host token. Rotation and emergency revocation procedures still require live acceptance tests.
- The current system is a private single-fleet project. Multi-tenant authorization and self-service host registration are **out of scope**.

## Acceptance gates (still unverified live)

- [x] Auth UI and agent/HTTP security boundaries implemented on FL-18 PR branch
- [x] Add unit/widget test coverage for 401/403, invite-only signup and TLS/redirect validation
- [ ] Run all GitHub Actions Flutter Web, mobile and Python agent tests on PR
- [ ] Confirm real Supabase email sign-in, email confirmation and backend JWT JWKS verification
- [ ] Confirm approved operator receives dashboard data, unapproved user gets 403, and agent token cannot access reads
- [ ] Confirm agent reports over publicly reachable protected HTTPS Vercel API with persisted Supabase metric samples
- [ ] Verify Web and Android UI manually; confirm logout, refresh, error/expired-session state
- [ ] Record endpoints (not secrets), app versions, test evidence and release SHA under Jira FL-18 and FL-20

**No public deployment or functioning hosted agent-to-dashboard integration is claimed.**
