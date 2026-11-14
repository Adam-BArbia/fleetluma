# FleetLuma — Product Requirements Document (PRD)

**Version:** 1.1 · **Date:** 14 November 2026 · **Status:** Agreed product scope / planned implementation  
**Product:** FleetLuma — Distributed Infrastructure Monitoring

## 1. Problem and audience

Developers, VPS owners, self-hosters and small hosting operators administer several computers and HTTP applications, often without a single place to see operating-system resource pressure and service availability. FleetLuma provides a lightweight, mobile-first view of host metrics and remote HTTP health checks.

**Primary actor:** Operator who views the fleet, inspects a host, checks HTTP service status, explores history, and reads top processes. **Secondary technical actors:** installed monitoring agents, recurring HTTP check scheduler, and monitored endpoints.

**Prerequisite:** To monitor OS metrics, the operator must be able to install and run an agent on each host. A separately monitored HTTP endpoint does not require a host agent.

## 2. Seven approved functional capabilities

| ID | Feature | Acceptance criteria | Priority |
| --- | --- | --- | --- |
| FL-F01 | CPU utilization | Each configured host reports a recent CPU utilization percentage; sample freshness is visible. | P0 |
| FL-F02 | RAM utilization | The mobile app shows percentage and used/total memory for each reporting host. | P0 |
| FL-F03 | Disk utilization | The app shows usage of a designated filesystem, with used/total and percentage. | P0 |
| FL-F04 | Agent heartbeat | The backend records last successful report and derives **CONNECTED** or **STALE**. Stale means unknown host health, not confirmed server outage. | P0 |
| FL-F05 | HTTP service check | Central backend checks approved URLs, records HTTP code / failure and latency, and derives **HEALTHY** or **UNHEALTHY** separately from host status. | P0 |
| FL-F06 | Historical graphs | Show persisted CPU, RAM, disk and HTTP response measurements, with up to 24 hours of history. | P1 |
| FL-F07 | Per-process monitoring | Show up to ten highest CPU or memory consumers on a selected host: PID, name, CPU%, memory usage. View is read-only. | P1 |

All seven capabilities are part of the accepted design. P0/P1 means implementation order, not removal from scope.

## 3. Product behavior and information architecture

**Mobile screens:** (1) Fleet Overview, (2) Host Detail with history, (3) Top Processes, and (4) HTTP Services with check history. The operator can inspect monitored information but cannot remotely kill processes or execute commands.

**Entity rules:** A `Host` has zero or more `MonitoredService` records; a `MonitoredService` can have no associated host. Host metrics and HTTP health results are independent sources of truth. A healthy website does not prove the host agent is connected, and a connected host does not prove its hosted website works.

**Status rules:** `Host` = CONNECTED when a recent authenticated agent report exists; otherwise STALE. `Service` = HEALTHY when its latest check satisfies the expected response policy, otherwise UNHEALTHY. Initial/no-data state must be represented separately from an actual negative check.

## 4. Boundaries and security

- **Included:** Linux and Windows monitoring agents; manual provisioning with per-agent unique tokens; central approved HTTP checks; latest host metrics; top 10 processes (read-only); 24-hour sample history; charts; local-network demo with two computers and Android phone/emulator.
- **Excluded:** remote shell, remote process termination, multi-user auth system, user sign-up, cloud deployment, arbitrary URL scanning, AI diagnosis, push notifications, distributed tracing and deep profiling.
- **Security:** per-agent credentials are provisioned out of band and never committed; HTTP checker uses explicitly permitted targets and bounded timeouts; avoid storing process command-line arguments/environment variables; do not use raw tokens in logs. Production use outside the controlled LAN requires TLS and hardened access control.

## 5. Nonfunctional requirements

- Modular boundaries: `agent`, `coordinator`, `mobile`; REST/JSON interfaces; persistence through SQLite for MVP.
- Failure safety: an agent should retry transient failures; rejected reports must not update heartbeat; missing or delayed data must not be portrayed as live.
- Compatibility: Python monitoring agents on Linux and Windows, Android mobile client with backend reachable over local network.
- Testability: fake monitoring endpoints are allowed for checks, but real system samples must be identified honestly; integration and API tests verify behavior.
- Public repository: exclude secrets from version control and document configuration via placeholders.

## 6. Proposed engineering defaults (not separately approved)

| Default | Proposed value / behavior |
| --- | --- |
| Agent sample/report period | About 10 seconds |
| Process snapshot period | About 30 seconds |
| HTTP check interval | About 20 seconds |
| Mobile API polling | Every 5 seconds (approved) |
| Heartbeat stale threshold | About 35 seconds |
| Graph windows | 15 minutes / 1 hour / 24 hours |
| HTTP healthy response policy | 2xx / 3xx responses; distinguish network errors |
| Process history | Latest snapshot only; no historical process chart |
| Persistent monitoring history | 24 hours (approved) |

The exact thresholds, API payload shape and HTTP success policy remain open to adjustment during implementation. The seven product features remain unchanged.

## 7. Demonstration acceptance scenarios

1. Two distinct Linux/Windows host agents on **two physical computers** report real CPU, RAM and disk usage to one coordinator.
2. Mobile dashboard displays both host records, recent measurements and heartbeat freshness.
3. Host detail shows recorded metrics in historical graphs.
4. Processes screen shows real top process names/PIDs and usage percentages.
5. Controlled HTTP service is stopped; monitoring records an unhealthy check; service is restarted and the backend records recovery.
6. An agent is stopped; its host becomes STALE after configured timeout, while HTTP service health remains independently checkable.
7. API accepts valid agent credentials and rejects invalid token/report payload without recording a fresh heartbeat.

## 8. Acceptance and traceability

This PRD is tracked by **[FL-2](https://adambenarbia.atlassian.net/browse/FL-2)**. UML sources are tracked by **FL-3**. Future implementation issues should reference FL-F01..FL-F07. Sprint 0 documents design work; it does **not** certify that implementation or the professor's earlier sprint reviews occurred.
