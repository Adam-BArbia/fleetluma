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

**Lab networking:** HTTP sends bearer credentials in plaintext. Use it only
on an isolated/trusted LAN with controlled firewall access. Use HTTPS on an
untrusted network; this project does not implement production deployment.

See `docs/api/openapi.json` for the canonical payload.
