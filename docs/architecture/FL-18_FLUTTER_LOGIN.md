# FL-18 — Flutter Supabase Auth client

This implementation introduces an operator sign-in screen in cloud mode.
Local Android/LAN mode remains unchanged by default.

Cloud build defines (all public/non-secret):
- `FLEETLUMA_CLOUD_MODE=true`
- `FLEETLUMA_API_BASE_URL=https://<vercel-api-domain>`
- `FLEETLUMA_SUPABASE_URL=https://<project>.supabase.co`
- `FLEETLUMA_SUPABASE_PUBLISHABLE_KEY=<publishable-key>`

The browser does not receive DB passwords, JWT signing secrets, or backend
service-role credentials. The Supabase Flutter SDK manages user session token
refresh. A signed-in operator's current access token is passed as a bearer
header with each dashboard API request. Dashboard polling is not mounted until
the user is signed in. Missing sessions stop requests before networking.

An operator must also have their UUID listed in the FastAPI server-side
`FLEETLUMA_OPERATOR_IDS` allowlist; a valid Supabase Auth account alone is
not sufficient. Disable user self-signup in Supabase Auth settings or otherwise
restrict invitation/provisioning. Do not put real passwords/tokens in repo.

**Blocked acceptance:** real Supabase sign-in on a browser and backend
allowlist/issuer validation have not been tested against a hosted API. The
serverless cloud API remains a separate draft PR (FL-16), and hosted deployment
is FL-20. Android CI and Flutter Web builds validate compilation, not live auth.
