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
`FLEETLUMA_COORDINATOR_URL` (origin-only HTTPS URL reachable from the agent in cloud mode),
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

**V1 cloud networking (mandatory):** Agents authenticate directly to the FastAPI API, **not** to the Flutter dashboard. Each physical host gets a distinct, securely generated bearer token provisioned by an operator-controlled backend procedure; PostgreSQL keeps only the SHA-256 token hash. The client sends the token via `Authorization: Bearer` to the fixed `POST /api/v1/agent/reports` endpoint. A token is never included in the JSON report or a URL. The backend resolves the host identity from the matching token hash and refuses invalid credentials without refreshing the heartbeat.

For a cloud-connected agent, set:

```bash
FLEETLUMA_MODE=cloud
FLEETLUMA_COORDINATOR_URL=https://<real-verified-api>.vercel.app
FLEETLUMA_AGENT_TOKEN=<privately-provisioned-unique-secret>
```

Do **not** place those literal placeholders in a real configuration, publish agent tokens, or send them in a support transcript. In cloud mode, HTTP URLs are rejected before transmission. TLS certificate/hostname validation is provided by Python's standard HTTPS stack; redirects are not followed, so credentials cannot be forwarded to an alternate origin. System proxy environment variables are ignored for token-bearing agent requests.

**Local fallback only:** Loopback HTTP (`127.0.0.1` or `localhost`) remains available for development in local mode. Other HTTP targets are rejected unless the operator deliberately sets `FLEETLUMA_ALLOW_INSECURE_LAN=true`, and even then only numeric RFC1918 private IPv4 addresses can be targeted. This opt-in **sends credentials without encryption** and is never appropriate for campus/untrusted Wi-Fi, production or cloud deployments.

The URL must be an origin without embedded username, password, path, query or fragment. Supply only a host name and optional port (e.g. `https://api.example.org`). There is no remote command execution or agent-side process termination.

See `docs/architecture/FL-18_OPERATOR_ONBOARDING.md` for the separate dashboard authorization boundary and the V1 release gates.

See `docs/api/openapi.json` for the canonical payload.
