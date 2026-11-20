# FL-18 — Flutter Supabase Auth client

This implementation provides operator sign-in, an invitation-gated sign-up screen,
and backend approval checks in cloud mode. Local Android/LAN mode remains unchanged.

Cloud build defines (all public/non-secret):
- `FLEETLUMA_CLOUD_MODE=true`
- `FLEETLUMA_API_BASE_URL=https://<vercel-api-domain>`
- `FLEETLUMA_SUPABASE_URL=https://<project>.supabase.co`
- `FLEETLUMA_SUPABASE_PUBLISHABLE_KEY=<publishable-key>`
- `FLEETLUMA_ALLOW_SELF_SIGNUP=false` (default; only set true for deliberately approved registration deployments)

The browser does not receive DB passwords, JWT signing secrets, or backend
service-role credentials. The Supabase Flutter SDK manages user session token
refresh. A signed-in operator's current access token is passed as a bearer
header with each dashboard API request. Dashboard polling is not mounted until the user has signed in **and**
the protected API confirms operator approval. Missing sessions stop requests before networking;
HTTP 403 displays an operator-approval screen. HTTP 401 prompts retry or sign-out.

An operator must also have their UUID listed in the FastAPI server-side
`FLEETLUMA_OPERATOR_IDS` allowlist; a valid Supabase Auth account alone is
not sufficient. Keep Supabase user self-signup disabled for the private V1 by default;
admin-provision accounts by invitation. Optional self-registration still requires
separate server-side UUID approval and email confirmation; see the comprehensive
`FL-18_SIGNUP_AGENT_SECURITY.md` instructions. Do not put real passwords/tokens in repo.

**Blocked acceptance:** hosted browser/Android login, email confirmation,
operator approval, JWT issuance, agent ingress and PostgreSQL persistence have
not yet been verified together through a real HTTPS preview deployment.
Flutter/agent/backend CI proves only code and fixture behavior, not live auth.
See Jira FL-18 and FL-20.
