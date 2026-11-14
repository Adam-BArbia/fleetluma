# FL-10 — administrator-configured HTTP service checks

The coordinator can check configured HTTP(S) URLs without relying on host agents.

Set `FLEETLUMA_SERVICES_JSON` **locally** before starting FastAPI:

```json
[
  {
    "id": "6c103204-fcad-41ce-b218-65a0362b2aa5",
    "name": "Local Demo Service",
    "url": "http://127.0.0.1:8099/health",
    "host_id": null,
    "enabled": true
  }
]
```

This example is not automatically loaded; configure the variable in your shell.
The service checker runs every 20 seconds by default; change with
`FLEETLUMA_CHECK_INTERVAL_SECONDS` (5–3600). Probes have a 4-second timeout.

- Service check results and latencies are stored in SQLite.
- 2xx and 3xx HTTP responses count as HEALTHY; 4xx/5xx and connection errors
  count as UNHEALTHY; no result yet is UNKNOWN.
- A redirect is **not followed**. The latest result belongs to the approved URL.
- Independent HTTP services may have `host_id: null`.
- HTTP checks do not modify agent heartbeats or infer that a host is offline.
- Read-only routes: `GET /api/v1/services` and
  `GET /api/v1/services/{id}/checks?window=1h` (15m, 1h, 24h).
- No POST endpoint accepts arbitrary target URLs. Admin-supplied URLs are
  a **trusted configuration boundary**; protect the environment, and do not
  provision attacker-controlled endpoints. No redirects, proxy inheritance,
  URL credentials, query strings, or fragments are allowed. Production deployments
  also require operator access control and network egress restrictions.

To demo recovery, run an approved local HTTP server, stop it, allow at least
one check interval, then restart it. Verify transitions using the service
GET routes. CI uses an ephemeral localhost HTTP server rather than an
external third-party website.
