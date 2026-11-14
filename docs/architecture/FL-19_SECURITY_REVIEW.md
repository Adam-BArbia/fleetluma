# FL-19 checker defense-in-depth review

**Status: pre-deployment only — keep Jira FL-19 In Progress.**

This branch adds: explicit `FLEETLUMA_PUBLIC_PROBES_ENABLED=true` opt-in,
minimum 32-character scheduler secret, DNS A/AAAA preflight and private/special
IPv4 range rejection (IPv6 conservatively denied). The hostname must still
be approved via `FLEETLUMA_CHECK_ALLOWED_HOSTS`. All failures skip the
misconfigured target rather than sending a probe to it.

**Residual risk:** DNS preflight and hostname allowlisting alone cannot
eliminate DNS rebinding / resolution time-of-check-to-time-of-use behavior.
Before deploying the scheduled function, choose only trusted, administratively
owned public endpoints and enforce outbound egress restrictions where
supported. Never allow arbitrary user-supplied URLs or internal services.

These checks are unit-tested in CI with an injected DNS resolver. There is
still no live Edge Function, pg_cron schedule, Vault secret, or production
HTTP availability guarantee.
