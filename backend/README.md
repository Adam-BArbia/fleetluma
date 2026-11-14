# FleetLuma FastAPI coordinator

Planned: authenticated ingestion, SQLite persistence, latest host/query routes and scheduled HTTP health probes; tracked by FL-8 and FL-10. No executable backend implementation yet.

Each agent must be manually provisioned with a unique token and mapped to a server-side host record. Do not log raw tokens or accept identity from report bodies. See `docs/api/openapi.json`.
