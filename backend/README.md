# FleetLuma FastAPI coordinator — FL-8

Implemented: authenticated agent ingestion, SQLite host registry, latest samples,
24-hour query window, top-process snapshot and heartbeat state.

## Install and run

Python 3.12 recommended. From `backend/`:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q tests
python -m uvicorn fleetluma_backend.app:app --host 127.0.0.1 --port 8000
```

## Provision demo hosts (mandatory)

Set `FLEETLUMA_HOSTS_JSON` in your shell before starting Uvicorn.
It is a JSON array of objects with `id` (UUID), `name`, `os` (linux/windows),
and a **unique random token of at least 16 characters**. Use a secure token
generator such as `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
This mapping is **server-side**; the agent report body contains no host ID.
Use `FLEETLUMA_DATABASE_PATH` to choose the SQLite path.

Do not commit or screenshot real tokens. Do not pass tokens through GitHub
Actions logs. Existing host token changes are rejected to avoid silent
identity replacement. `.env.example` is illustrative and is **not** auto-loaded.

For a phone or second computer on a *trusted lab LAN only*, bind Uvicorn to
`0.0.0.0` after allowing the firewall port and identifying the host's LAN IP.
The prototype uses cleartext HTTP with bearer credentials: never expose it
to untrusted networks; TLS + operator auth are mandatory outside the lab.

Service checker routes are deferred to FL-10. No agent installation, cloud
deployment, or remote commands are implemented here.
