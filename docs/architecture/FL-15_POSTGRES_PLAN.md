# FL-15 — PostgreSQL persistence adapter

The local SQLite-based FastAPI code remains unchanged. The new
`fleetluma_backend.postgres_store.PostgresStore` is a **separate backend
persistence adapter** for the proposed Vercel runtime; use it only after
FL-16 wires it to authenticated cloud routes.

## Database schema

The reviewed schema is in `backend/sql/FL-15_cloud_schema.sql`.
It creates the private `fleetluma` schema (hosts, samples, process_snapshots,
services, service_checks), enforces referential integrity, grants no public
Data API access, and enables RLS defensively. SQL is not executed automatically.

Before applying to the connected Supabase project, review migrations/roles,
then execute with an authorized database connection. Verify that the `public`
schema has no exposed copies of these tables and that `anon`/
`authenticated` have no schema/table permissions.

The connection string `FLEETLUMA_DATABASE_URL` must be stored server-side
(never in Flutter, GitHub, Jira, or URLs). Use Supabase transaction pooler with
TLS; adjust pooler mode/port only from the authenticated project's dashboard.
The PostgresStore opens a fresh connection per operation and commits/rolls
back transactions through psycopg context management.

## Verification

The unit tests check state/timestamp conventions without database secrets.
Cloud migration requires an **actual authenticated Postgres integration test**
for host provisioning, agent ingestion, invalid tokens, live reads, HTTP checks,
purging, database grants and a real FastAPI cloud entry point. Until those tests
pass, FL-15 remains in progress and the existing SQLite path remains the
trusted local fallback.
