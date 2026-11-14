# FL-16 — Vercel FastAPI runtime (staged implementation)

This branch builds a **separate serverless FastAPI entry point**. It deliberately
does not replace the local `fleetluma_backend.app:app` SQLite/LAN coordinator.

For the Vercel API project, set **Root Directory** to `backend`.
Vercel's Python/FastAPI runtime discovers the ASGI instance in
`backend/api/index.py` automatically (relative to this root: `api/index.py`).

Cloud function behavior:
- Fail closed unless `FLEETLUMA_MODE=cloud`, an explicit Supabase issuer,
  operator UUID allowlist, HTTPS Web CORS origins and
  `FLEETLUMA_DATABASE_URL` are configured.
- Use the PostgreSQL persistence adapter for seven existing API routes.
- Validate agent tokens separately from operator access JWTs.
- Never import/use local SQLite startup provisioning or an in-process checker
  in the hosted app.
- Provide a harmless `GET /health` route.
- No runtime creation of SQL schema; database migrations are separately managed.

**No deployment has been made.** Hosted integration remains gated on:
1. FL-18 real operator sign-in and JWT acceptance tests, including signing-key
   verification and user allowlist.
2. The private Supabase database connection/transaction-pooler DSN being set
   as a **secret environment variable** inside the correct Vercel API project.
3. FL-19 external service-check scheduler and retention policy.
4. FL-20 end-to-end HTTPS tests and explicit production enablement.

Run tests locally with `python -m pytest -q backend/tests/` from `backend/`
after installing `backend/requirements-dev.txt`. The unit tests inject a
fake store: they do not claim a live Vercel-to-Supabase connection.

Do not put DATABASE_URL, operator credentials, or tokens in GitHub or Jira.
