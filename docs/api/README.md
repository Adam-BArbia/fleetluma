# FleetLuma API — v0.1.0 target contract

**Status:** Existing cloud monitoring endpoints are deployed; **pairing, workspace authorization, revocation and device management are contract-only until implemented.** [OpenAPI 3.1](./openapi.json) is the machine-readable source; [FL-31 architecture](../architecture/FL-31_PLUG_AND_PLAY_ENROLLMENT_V1.md) is the pairing decision record.

## Principal boundaries

| Principal | Proof | Scope |
| --- | --- | --- |
| Agent before enrollment | 256-bit private device polling secret; visible code is **not** authentication | Create, poll, cancel only its own pending pairing |
| Paired Windows/Linux agent | Per-host locally held reporting token | Submit metrics for its ACTIVE registered host only |
| Approved Supabase Auth operator | Valid RS256/ES256 JWT, role and workspace membership | Workspace-scoped monitoring reads |
| Workspace owner/admin | JWT plus owner/admin membership | Pairing approval, device rename/revoke, audit |
| Viewer | JWT plus viewer membership | Read-only workspace fleet; no approval or revocation |

`POST /api/v1/agent/reports` stays compatible at the wire level but must reject **REVOKED** credentials with 401 and never mutate heartbeat on auth failure. `GET /api/v1/hosts` and `GET /api/v1/services` require `workspace_id` in the **target** contract (the current running API does not yet accept that query). Host detail/history/process paths enforce workspace membership via the host record. Services independent of a host still belong to a workspace through a new `services.workspace_id` relationship in the future additive migration.

## Endpoint groups

**Existing monitoring routes (7):** `POST /api/v1/agent/reports`, `GET /api/v1/hosts`, `GET /api/v1/hosts/{id}`, `GET /api/v1/hosts/{id}/history`, `GET /api/v1/hosts/{id}/processes`, `GET /api/v1/services`, `GET /api/v1/services/{id}/checks`.

**Design-only pairing and device management (11):** `POST /api/v1/agent/pairings`, `POST /api/v1/agent/pairings/token`, `POST /api/v1/agent/pairings/cancel`, `POST /api/v1/operator/pairings/resolve`, `POST /api/v1/operator/pairings/{id}/approve`, `POST /api/v1/operator/pairings/{id}/deny`, `GET /api/v1/operator/workspaces`, `GET /api/v1/operator/hosts`, `PATCH /api/v1/operator/hosts/{id}`, `POST /api/v1/operator/hosts/{id}/revoke`, `GET /api/v1/operator/device-audit`.

Short code: server-generated 8 symbols (4-4) using the defined non-confusable alphabet, 10-minute TTL, single-use and rate-limited. Agent polling secret is separate from its future report token. Polling uses JSON body, never URI query, and enforces >=5s server-side. No durable reporting secret is returned in any pairing response.

On `/agent/pairings/token`, `200 { "status": "pending" }` signifies continued wait; after approval, `200 { "status": "paired", "host_id": "...", "workspace_id": "..." }` confirms approval. Attempts before the polling interval return 429; denied is 403; expired is 410. Operator approval is atomic and must check membership in the selected workspace. Redacted 401/403/404 errors never leak tokens or code existence to unauthorized callers.

The `Host` response **target** requires `workspace_id`, `lifecycle`, and a reporting status in `PENDING|CONNECTED|STALE|REVOKED`; old runtime payloads and examples were different. `REVOKED` supersedes heartbeat-derived states; `STALE` is never proof the machine is off.

## Validation

CI runs `python docs/api/validate_contract.py` to validate OpenAPI, the complete 18-operation method/path inventory, operator-route JWT schemes and 12 JSON examples. All new examples are synthetic, not live device identifiers. This is specification validation, **not proof of implemented pairing endpoints**.

## Scope

Windows and Ubuntu/Debian packages, background agents with local setup UIs and dashboard approval are mandatory before v0.1.0 is released. Existing TUFFEST host and metrics must survive the additive database migration. Original local-LAN unauthenticated behavior remains a development/demo-only path, never the cloud release model.

Service checking/retention is a separately gated FL-19 concern. Do not implement arbitrary user-defined URL probes without SSRF protections and scheduler review.
