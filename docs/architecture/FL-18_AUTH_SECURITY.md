# FL-18 — cloud operator authentication (draft)

This branch adds an explicit **cloud-only** FastAPI security boundary while leaving the existing trusted-LAN SQLite endpoint behavior unchanged.

- Backend validates Supabase Auth JWT signatures using the project's asymmetric JWKS, checks issuer, audience, expiration, `role=authenticated`, and explicit `FLEETLUMA_OPERATOR_IDS` UUID allowlist.
- All six read-only GET routes require operator JWT when `FLEETLUMA_MODE=cloud`.
- Agent POST continues using independent per-agent token mapping. **Operator JWTs are not agent tokens.**
- CORS accepts explicit HTTPS origin(s) from `FLEETLUMA_WEB_ORIGINS`; no wildcard. CORS is not authentication.
- JWT verifier accepts **RS256 and ES256 only**; verify the project's signing key type before deployment. Legacy symmetric Supabase signing keys require a separate, reviewed verification approach; do not silently accept HS256 with a public key.
- Environment variables: `FLEETLUMA_MODE`, `FLEETLUMA_SUPABASE_URL`, `FLEETLUMA_OPERATOR_IDS`, `FLEETLUMA_WEB_ORIGINS`. Configure in Vercel encrypted environment settings, **not** a committed .env.
- An actual Flutter Web sign-in flow that obtains and refreshes Supabase Auth tokens still needs implementation and live test. No new public deployment is authorized by this PR.
- Supabase's private monitoring schema remains inaccessible to `anon` / `authenticated` Data API roles. FastAPI is the server-side data gate.
- Cloud startup is intentionally not yet deployable: the existing FastAPI app still initializes SQLite. FL-15 and FL-16 will integrate the Postgres adapter and remove that startup behavior. Do not set cloud mode in a hosted deployment until those tasks pass.
