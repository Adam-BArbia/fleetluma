# FL-31 — OpenAPI / UML synchronization matrix (v0.1.0 DESIGN)

**Scope:** Synchronize **target design**, not deployed behavior. All new pairing and workspace routes are NOT YET IMPLEMENTED. No live PostgreSQL schema modifications, runtime Python/Flutter code modifications, installer builds, or Vercel releases are included in PR #31.

## Cross-artifact traceability

| Feature/invariant | OpenAPI operation/schema | UML diagrams | Data model |
| --- | --- | --- | --- |
| Agent initiates pairing and displays server-generated code | `POST /api/v1/agent/pairings`; `PairingCreated` | 02, 05, 11, 14, 17, 19, 31 | `pairing_sessions` |
| Session-secret-only polling, deny/expire/cancel | `POST /api/v1/agent/pairings/token`, `/cancel`; `PairingTokenResult` | 11, 14, 17, 19, 31 | `pairing_sessions` |
| Operator enters code and reviews metadata | `POST /api/v1/operator/pairings/resolve`; `PairingResolved` | 01, 06, 14, 18, 31 | Pairing row + membership check |
| Workspace discovery, owner/admin approval or denial | `GET /api/v1/operator/workspaces`; `POST /api/v1/operator/pairings/{id}/approve`, `/deny` | 01, 03, 04, 06, 14, 18, 31 | `workspaces`, `workspace_memberships`, `pairing_sessions`, `hosts`, audit |
| Workspace-scoped host list, detail/history/processes | `GET /api/v1/hosts`, `/hosts/{id}`, `/history`, `/processes`; `Host` | 03, 04, 06, 15, 19, 22, 23 | `hosts.workspace_id`; existing `samples`, `process_snapshots` |
| Owner/admin host management, immediate revocation | `GET /api/v1/operator/hosts`, `PATCH /api/v1/operator/hosts/{id}`, `POST .../revoke` | 01, 03, 04, 06, 15, 18, 19, 21 | Host lifecycle, audit, token hash |
| Per-host agent HTTPS ingestion | `POST /api/v1/agent/reports`; `AgentReport`, `Accepted` | 02, 04, 05, 07, 11, 15, 17, 19, 20, 21, 26, 27, 30 | Active host hash; atomic sample + process + heartbeat |
| Independent service checks and workspace scope | `GET /api/v1/services`, `/services/{id}/checks` | 03, 07, 12, 13, 16, 24, 25, 29, 30 | `services.workspace_id` needed; external FL-19 cron |
| Consent, service persistence and native installers | N/A (local UI/service interface) | 05, 08, 11, 17, 28, 30 | Local encrypted/restricted credential; no DB password |
| Enrollment and device event audit | `GET /api/v1/operator/device-audit`; `DeviceAuditPage` | 01, 03, 04, 06 | `device_audit_events` |
| Final cloud deployment and separated principals | Operator JWT vs `AgentToken` security schemes | 07, 08, 22, 29, **30**, 31 | Supabase Auth + private PostgreSQL |

## Deliberate historical exceptions

- `09_deployment.puml` remains the original LAN/SQLite class demonstration, explicitly **NOT** the final deployment blueprint. The final target is **`30_cloud_deployment.puml`**.
- Existing local SQLite tests and runtime FastAPI routes are not modified by this architectural pull request.
- `16_state_service.puml` remains unchanged: UNKNOWN / HEALTHY / UNHEALTHY depends on external HTTP checks, independent of device lifecycle.
- The first-release manual WSL provisioning guide remains historical/break-glass and is superseded for ordinary users by plug-and-play pairing.

## Contract synchronization rules

- 18 distinct method/path operations: 7 existing monitoring and 11 design-only pairing/device endpoints.
- 30 OpenAPI component schemas including pairing, workspace, audit and managed-host DTOs.
- 12 synthetic JSON examples validated by `docs/api/validate_contract.py`.
- `GET /api/v1/hosts` and `GET /api/v1/services` require `workspace_id` in the **target** contract. Runtime and Flutter clients must be migrated together.
- Host target includes `workspace_id`, `lifecycle`, status `PENDING|CONNECTED|STALE|REVOKED`. REVOKED takes precedence; STALE does not indicate power-off.
- Current code authenticates approved operators against a global UUID allowlist; v0.1 target additionally enforces workspace membership and admin/viewer roles.
- Public pairing endpoints must use durable rate limiting (stateless serverless), 10-minute TTL and 256-bit distinct device session/reporting secrets; no tokens or pairing secrets in URL, logs, browser or audit.
- Host identity must derive exclusively from an ACTIVE credential in private PostgreSQL. Revocation and bad-token reports cannot mutate heartbeat or samples.
- Keep TUFFEST existing host ID and historical samples during additive migration. Add workspace ownership for independent services; do not leak orphaned service records.
- No in-process checks on Vercel; FL-19 is a separate scheduled checker under independent review.

## Verification evidence and implementation handoff

The current PR's GitHub Actions `API contract validation` and `PlantUML validation` must pass before merging; changed diagrams must all render to SVG. This is syntactic and cross-reference validation, **not an end-to-end security test**.

**Next implementation gate:** implement and review workspace schema migration and backfill, test concurrent pairing state transitions/expiration/abuse control, implement FastAPI APIs, adapt Flutter, then build Windows and Linux service installers. Validate on clean machines and record Jira acceptance. Do not promote production until release tests pass.
