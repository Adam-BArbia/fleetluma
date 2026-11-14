# FleetLuma API contract — FL-6

**Status:** Versioned contract proposal for Sprint 1, implementation not yet started. **Canonical machine-readable source:** [openapi.json](./openapi.json).

## Responsibilities

- **Agent** uses Python/psutil on Linux and Windows and **pushes** a single JSON report to the coordinator. Agent identity is derived from its provisioned bearer token; never accept a host id from the request body.
- **FastAPI coordinator** validates and persists report + heartbeat as one logical transaction, computes host freshness, checks allowlisted HTTP services on an independent scheduler, exposes read-only routes to Flutter.
- **Flutter Android** consumes JSON with 5-second polling. Null metrics, no samples, and stale state are legitimate. Do not fabricate data when disconnected.

## Endpoint summary

| Verb | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/agent/reports` | Authenticated agent CPU/RAM/disk with optional top-process list; returns **202** |
| GET | `/api/v1/hosts` | List hosts with most recent resource metrics and status |
| GET | `/api/v1/hosts/{id}` | Host detail with latest metrics |
| GET | `/api/v1/hosts/{id}/history?window=15m\|1h\|24h` | Historical resource series |
| GET | `/api/v1/hosts/{id}/processes` | Latest top ten processes, read-only |
| GET | `/api/v1/services` | Allowlisted monitored HTTP services (possibly independent of host) |
| GET | `/api/v1/services/{id}/checks?window=15m\|1h\|24h` | Recent HTTP health results |

Full object fields, types, required properties, error responses and REST security are defined in OpenAPI 3.1 and illustrated under [examples](./examples).

## State and timestamp invariants

- `PENDING`: provisioned agent has never successfully reported.
- `CONNECTED`: valid report received within the configured freshness window.
- `STALE`: last accepted report is older than the freshness threshold; **not** proof a physical host is powered off.
- `UNKNOWN`: HTTP service has no completed check yet.
- `HEALTHY` / `UNHEALTHY`: independent central HTTP check result.
- Backend `received_at` and `last_seen_at` are server-clock UTC instants. Agent `sampled_at` records sample time; client must not use it to infer heartbeat freshness.
- Metrics are bounded 0–100%, except process CPU percentage may exceed 100 on multicore systems. RAM/disk bytes are nonnegative and `used <= total`.
- Processes are read-only and capped at ten; their command lines and environment are never collected.
- Latest process snapshot may be absent (null time + empty list).
- History queries return ascending time series; store at most 24 hours for MVP.
- Retried agent reports may cause duplicate samples; implementation should document retry behavior rather than claiming deduplication.

## Validation and error rules

- Agent sends `Authorization: Bearer <provisioned token>`; invalid/missing token → **401**; malformed schema → **422**; all failures must leave `last_seen_at` unchanged.
- Unknown host/service ID → **404**; invalid window/time filter → **422**.
- Error body: `{"error":{"code":"SOME_CODE","message":"Human-readable text"}}`.
- Monitoring routes are **unauthenticated in the controlled LAN prototype**. This is an explicit MVP limitation, not a recommendation for production. Use HTTPS and operator authentication before exposing a coordinator to an untrusted network.
- HTTP service target registration is administrator-configured/out-of-band; do not provide an unrestricted user-supplied URL fetch endpoint (SSRF risk).

## Open questions / defaults

Provisional: 10 s agent reports, 20 s service probes, 30 s process snapshots, 35 s stale threshold and 2xx–3xx health policy. Five-second Flutter polling, 24-hour history, two physical hosts and no cloud deployment are approved. HTTP probe policy, payload evolution, retention maintenance and agent provisioning format may be refined in implementation with synchronized contract updates.

## Build order and entrypoints

1. Update the OpenAPI document and all JSON examples first (FL-6).
2. Agent owner (FL-7) implements `AgentReport` against `POST /api/v1/agent/reports`.
3. Backend owner (FL-8) implements token validation, transactions and GET routes.
4. Flutter owner (FL-9) reads `HostList` and other response schemas; Android emulator must use a reachable coordinator endpoint rather than blindly using its own `127.0.0.1`.
5. Integration owners validate local LAN connectivity and failure behavior (FL-13).

## Non-implementation scaffold

`agent/`, `backend/`, `mobile/` are separate planned deployable roots. No runnable app skeleton, package files, or secrets are introduced by FL-6. See each directory README and example config. This does **not** indicate features are implemented.

**Acceptance evidence:** OpenAPI JSON parse + reference check + sample shape check in this task, reviewable Jira-linked GitHub PR. Real FastAPI/Flutter/psutil integration tests belong to subsequent issues.
