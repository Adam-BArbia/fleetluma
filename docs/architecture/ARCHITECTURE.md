# FleetLuma — Architecture Baseline

**Version 1.1 | 14 November 2026 | Design, not yet implementation.**

## Runtime components

- **Agent (Python + psutil)** on Linux/Windows: CPU, RAM, disk and bounded top-process collection; outgoing authenticated reports with per-agent token.
- **Coordinator (FastAPI + SQLite)**: report validation, host last-seen, 24-hour metric history, process snapshots, approved HTTP checks, REST query endpoints.
- **Mobile (Flutter Android)**: fleet, host metrics/history, process and service screens; polls API every five seconds.

Agents **push** metrics to coordinator. Coordinator independently **pulls** HTTP health of approved endpoints. A MonitoredService may be associated with zero or one Host; Host may have zero or many services. Host CONNECTED/STALE and service HEALTHY/UNHEALTHY are independent; no data begins UNKNOWN/PENDING.

## Proposed routes

- `POST /api/v1/agent/reports` authenticated metric reports
- `GET /api/v1/hosts`, `GET /api/v1/hosts/{id}`
- `GET /api/v1/hosts/{id}/history`, `GET /api/v1/hosts/{id}/processes`
- `GET /api/v1/services`, `GET /api/v1/services/{id}/checks`

Authentication failures never refresh heartbeat. Store only safe process metadata; no sensitive command-line details. No remote command execution. The deployment for class demo uses two computers over local LAN and an Android client.

Architectural assumptions require implementation and validation. UML sources in `docs/uml/plantuml/` are an editable design baseline.
