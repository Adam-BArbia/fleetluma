# FleetLuma monitoring agent — FL-7

Real system metric reporting for Linux and Windows using Python + psutil.

## Requirements

Python 3.12 recommended. Install from the `agent/` directory:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## Configuration

The agent reads **environment variables**, not the `.env.example` file automatically:
`FLEETLUMA_COORDINATOR_URL` (HTTP(S) base URL reachable from the agent),
`FLEETLUMA_AGENT_TOKEN` (one unique, already-provisioned token per host),
`FLEETLUMA_DISK_PATH` (optional filesystem root; default system root),
and `FLEETLUMA_INTERVAL_SECONDS` (optional, default 10).

Register the host's UUID, name, OS and secret with the coordinator using
`FLEETLUMA_HOSTS_JSON` **before** starting the agent. Do not commit
credentials, paste them into Jira, or print them to logs.

On Linux/macOS, export the variables into the shell; on PowerShell use
`$env:FLEETLUMA_AGENT_TOKEN = "<locally generated secret>"` and analogous
settings for URL. The agent starts using:

```bash
python -m fleetluma_agent.main
```

The agent posts a report every ~10 seconds with bounded retry/backoff.
The top 10 processes are sampled approximately every 30 seconds. It never
collects process command lines or environments, nor supports commands or
process termination. A psutil per-process CPU percentage may exceed 100%.

**Cloud V1 networking:** always configure `FLEETLUMA_AGENT_CLOUD_MODE=true`
and a real HTTPS `FLEETLUMA_COORDINATOR_URL`. Each agent has a unique
server-provisioned bearer token that is never logged or given to operators.
Remote HTTP is now rejected by default, and HTTP redirects are never followed
for authenticated report requests. URLs containing credentials, query strings
or non-root paths are rejected to prevent credential leakage.

**Exception for an isolated LAN classroom demonstration only:** set
`FLEETLUMA_ALLOW_INSECURE_LAN=true` when an HTTP coordinator is reachable
through a trusted local network. Do not enable this in cloud deployment.
Regular local loopback HTTP remains available when cloud mode is off.

Operators sign in separately with Supabase Auth; agent tokens never provide
permission to access dashboard GET endpoints. Read
`docs/architecture/FL-18_SIGNUP_AGENT_SECURITY.md` for the final deployment
security and onboarding design.

See `docs/api/openapi.json` for the canonical payload.
