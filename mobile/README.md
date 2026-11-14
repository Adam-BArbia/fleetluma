# FleetLuma Flutter Android client

Planned: overview, host metrics/history, process list and HTTP services using read-only endpoints defined in `docs/api/openapi.json`; tracked by FL-9. No Flutter source has been generated yet.

The app must poll every five seconds while active and show loading/error/empty/stale states. Android emulator and physical devices need an address that reaches the coordinator; the emulator's loopback is NOT the backend host's loopback.
