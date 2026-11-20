# FL-18 — Operator onboarding and secure agent identity

**Architecture:** [Final cloud deployment diagram](../uml/plantuml/30_cloud_deployment.puml). Do not use the separate LAN demo topology as a production target.

## Separate trust boundaries

| Principal | Credential | Authorization | Route |
| --- | --- | --- | --- |
| Dashboard operator (Flutter Web/Android) | Supabase Auth email/password and signed JWT | FastAPI validates RS256/ES256 JWKS, issuer, audience, expiry, authenticated role, explicit operator UUID allowlist | Six read-only `/api/v1/...` GET routes |
| Monitoring agent (Windows/Linux) | Unique per-host random bearer token over HTTPS | FastAPI matches SHA-256 token hash in private PostgreSQL and derives the host ID from DB | `POST /api/v1/agent/reports` |
| External HTTP checker | Independently managed scheduler credential | Approved public URLs and least privilege; FL-19 gate | Scheduled checks/retention |

**Agents never authenticate to the dashboard; operators never hold agent tokens.** The browser cannot access the private database directly or obtain any backend DB/service-role secrets.

## Flutter pages and onboarding

- `SignInScreen` retains Supabase password sign-in; it now links to the registration/request page.
- `SignUpScreen` provides responsive email, password, confirmation, validation, generic errors, confirmation instructions and a return-to-sign-in action.
- `FLEETLUMA_ALLOW_SIGN_UP` is a compile-time **UI flag defaulting to false**. With it disabled the registration page explains the invite-only policy and provides no submission form. Enabling the UI flag alone does not configure Supabase security or grant access.
- A newly signed-up identity **is not an authorized FleetLuma operator**. The FastAPI server still requires the exact Auth user UUID in server-side `FLEETLUMA_OPERATOR_IDS`; valid but unapproved tokens receive 403.
- Prefer admin-created/invited accounts with email confirmation enabled for private V1; leave public Supabase registration disabled unless explicitly reviewing a narrow onboarding window.
- If Supabase briefly issues a session on signup, the signup UI remains mounted and signs it out. This prevents registration from being mistaken for an approved dashboard login.

### Safe deployment configuration

At Vercel API runtime, privately configure `FLEETLUMA_DATABASE_URL` (pooled TLS DSN), `FLEETLUMA_OPERATOR_IDS` (approved UUIDs), `FLEETLUMA_WEB_ORIGINS` (exact HTTPS Web origins), and public `FLEETLUMA_SUPABASE_URL`. The browser build can receive `FLEETLUMA_API_BASE_URL` (HTTPS), `FLEETLUMA_CLOUD_MODE=true`, `FLEETLUMA_ALLOW_SIGN_UP=false`, public Supabase URL and **publishable** key. Never expose service-role keys, token hashes, agent credentials or DB passwords.

Before a live sign-in, verify that the project's Supabase Auth signing key is asymmetric RS256/ES256 to match the API JWKS verifier. Do not silently weaken signature verification for HS256. Configure redirect domains and email confirmation appropriately.

## Agent identity and transport

- Provision one strong unique token per host using a trusted administrative procedure, not a dashboard public endpoint. `PostgresStore.provision_host` stores a SHA-256 hash and the approved host identity.
- The agent sets `FLEETLUMA_MODE=cloud`, the actual HTTPS Vercel API origin in `FLEETLUMA_COORDINATOR_URL`, and the private unique `FLEETLUMA_AGENT_TOKEN` on its machine.
- In cloud mode, HTTP is rejected before a request. The client rejects URL credentials, query, fragment and non-root path, follows **no HTTP redirects**, and ignores inherited `HTTP_PROXY`/`HTTPS_PROXY` variables. Python verifies the HTTPS server certificate and hostname.
- A report's host identity is derived from the matched token in the DB, not trusted from request JSON. Failed authentication must not update heartbeat.
- Local SQLite fallback permits HTTP on loopback. An explicitly insecure local LAN exception requires `FLEETLUMA_ALLOW_INSECURE_LAN=true` and a numeric RFC1918 IPv4 address; never use this on campus Wi-Fi or for cloud release evidence.
- Rotate compromised tokens through a reviewed privileged backend operation and reject old credentials. No process execution or remote kill API.

## Release verification: mandatory, not yet complete

- [ ] Anonymous GET 401; invalid/expired/wrong-issuer JWT 401; unapproved operator 403; approved operator GET 200.
- [ ] Real operator signs in on hosted Flutter Web; session refresh and logout work without leaking tokens.
- [ ] Real Windows and Linux agents send authenticated **HTTPS** POSTs; valid reports persist and invalid tokens cannot refresh the host heartbeat.
- [ ] Agent no-redirect and TLS configuration tested; HTTP blocked for cloud.
- [ ] PostgreSQL storage, `/health` readiness, private schema, origin-specific CORS and Vercel preview protection verified.
- [ ] FL-19 scheduled service checker and retention operate securely; FL-20 real two-client hosted end-to-end smoke tests recorded.

Unit/widget tests and source review alone do not prove deployed authentication. Keep FL-18 and FL-20 In Progress until those acceptance checks pass.
