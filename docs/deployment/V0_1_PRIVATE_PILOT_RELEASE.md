# FleetLuma v0.1.0 — private pilot release gate (Windows first)

**Status:** RELEASE CANDIDATE — NOT YET ACCEPTED. Do not tag, publicly announce, or promote an unverified production release.

**Scope:** one real Windows machine reporting CPU, memory, disk, and top-process metrics via HTTPS to FastAPI on Vercel, persisted in the private Supabase PostgreSQL `fleetluma` schema and visible to an approved operator in Flutter Web. Linux agent support is implemented but a real Linux-agent acceptance test is still required.

**Canonical deployment design:** `docs/uml/plantuml/30_cloud_deployment.puml`.

## Already verified (2026-11-21)

- Vercel FastAPI preview deployed with `/health` returning HTTP 200 / `{"status":"ready","mode":"cloud"}` against PostgreSQL.
- Flutter Web can authenticate the invited operator with Supabase Auth, the API accepts the operator JWT, and the real empty fleet view loads.
- GitHub Flutter Web CI passed; `fleetluma-web.vercel.app` was explicitly assigned to the latest successful build.
- No host has been enrolled and no agent report has been observed. Therefore the end-to-end monitoring release has **not** passed.

## Deployment security requirements

- `FLEETLUMA_DATABASE_URL` is a private, server-only pooled PostgreSQL URI. It must not go to GitHub, the browser, Jira or chat.
- Each agent gets its own strong token; only its SHA-256 digest is stored in PostgreSQL.
- Supabase operator JWTs and per-agent bearer tokens are **distinct**. Operators never receive the agent token in the browser.
- Only `https://` origins are permitted for cloud agent transmission. A redirect is not followed; proxy environment variables are ignored by the agent.
- API deployment-level Vercel SSO is **not compatible** with an unaffiliated Python agent; keep the API accessible through HTTPS but secured at its application endpoints. The *Web* project may retain Vercel SSO.
- `FLEETLUMA_WEB_ORIGINS` must list exact deployed web origins, not `*`.
- Lock production promotion behind separate authorization and rollout/rollback evidence. A successful preview CI is not a production acceptance test.

## Release gate 1 — Provision first host (administrator's WSL/Linux shell)

Use a local **trusted** WSL Ubuntu shell. The existing privileged CLI deliberately does not run in native Windows PowerShell because it requires POSIX file permissions.

```bash
git clone https://github.com/Adam-BArbia/fleetluma.git
cd fleetluma/backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export FLEETLUMA_MODE=cloud
mkdir -p "$HOME/.config/fleetluma"
chmod 700 "$HOME/.config/fleetluma"
# Read the secret silently. Paste the complete real Supabase transaction-pooler URI,
# with the actual encoded database password, at this prompt. Do NOT put it in shell history.
read -r -s -p "PostgreSQL pooler URI: " FLEETLUMA_DATABASE_URL
printf '\n'
export FLEETLUMA_DATABASE_URL
python -m fleetluma_backend.provision_agent \
  --name workstation-01 --os windows \
  --token-file "$HOME/.config/fleetluma/workstation-01.json"
unset FLEETLUMA_DATABASE_URL
```

The tool writes a `0600` secret file; **never print, screenshot, upload or commit** it. The command will report the host UUID and file location. Re-running with the same destination refuses overwrite. This task is performed locally by the administrator, not by ChatGPT or CI.

## Release gate 2 — Start Windows agent (native PowerShell, on the provisioned host)

Install Python 3.12 and Git if missing. From a new PowerShell window:

```powershell
git clone https://github.com/Adam-BArbia/fleetluma.git
cd fleetluma/agent
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Obtain the secret **on this same trusted machine** without displaying it or typing it into shell history. If the host is the administrator's Windows machine with WSL:

```powershell
$credential = (wsl.exe sh -c 'cat "$HOME/.config/fleetluma/workstation-01.json"') | ConvertFrom-Json
$env:FLEETLUMA_MODE = "cloud"
$env:FLEETLUMA_COORDINATOR_URL = "https://fleetluma-6n0ogdlgr-fleet-luma.vercel.app"
$env:FLEETLUMA_AGENT_TOKEN = $credential.agent_token
Remove-Variable credential
.\.venv\Scripts\python.exe -m fleetluma_agent.main
```

For another machine, transfer the private credential file via a trusted secure channel, restrict OS permissions to the intended user, parse it locally and delete the source copy. Never paste the raw token into Slack/chat/issue text. The agent logs only `Agent report accepted` and retry categories, never its bearer token.

> The coordinator URL is the current known working cloud API build, **not** a permanent production domain. Confirm `/health` before running, and update this documented example if the Vercel project changes.

## Release gate 3 — Real data acceptance

1. Confirm the agent logs `Agent report accepted` for at least 3 reporting intervals.
2. Confirm the UI at `https://fleetluma-web.vercel.app` shows **workstation-01**, state CONNECTED and real CPU/RAM/disk readings.
3. Verify PostgreSQL persistence with read-only administrator query (do not print tokens or token hashes):

```sql
select h.name, h.os, h.last_seen_at, count(s.id) as samples
from fleetluma.hosts h
left join fleetluma.samples s on s.host_id = h.id
group by h.id, h.name, h.os, h.last_seen_at;
```

4. Stop the agent. After at least 35 seconds verify the host transitions to STALE, retaining last-known readings rather than claiming they are live.
5. Check that GET fleet routes require a valid approved operator JWT; an invalid agent token cannot insert a sample or refresh a heartbeat. Do not log bearer credentials.
6. Exercise logout and session renewal; refresh does not leak authorization headers to another origin.

## Release gate 4 — Scope and sign-off

- [ ] Windows real-host ingestion, PostgreSQL samples and dashboard observed
- [ ] Unauthenticated/invalid operator tokens rejected; approved operator granted access
- [ ] Invalid agent credential rejected without changing last_seen_at
- [ ] Linux real-host smoke test completed or explicitly documented as non-shipping
- [ ] Web origin-specific CORS and HTTPS verified
- [ ] Retention and scheduled service-checker feature either passed independently under FL-19 or **excluded explicitly** from v0.1.0
- [ ] Production domain, source commit, environment configuration, access protection and rollback reviewed
- [ ] Release notes accurately list supported/unsupported functions
- [ ] All approval evidence recorded in Jira FL-18 / FL-20

**Release policy:** until all in-scope gates pass, use the label `v0.1.0-rc.1` (private pilot candidate), not a production `v0.1.0` announcement. Do not enable public signup, unreviewed HTTP checker URLs, or broad Supabase grants to make the demo work.
