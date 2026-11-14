# FL-13 — two-computer / Android LAN demonstration

**Status:** Preparation; not yet executed on the team’s physical hardware. Record results only after actual testing.

## Requirements

Two separate Windows/Linux computers connected to an isolated, trusted LAN, one computer hosting the FastAPI backend, and Android phone/emulator. **Use test credentials only.** Plain HTTP sends tokens unencrypted; never use an untrusted network or expose TCP 8000 to the Internet.

## Backend PC (computer A)

1. Clone `main`, install Python 3.12, run `python -m pip install -r backend/requirements-dev.txt`.
2. Generate **two random tokens** (never paste into Jira, screenshots, or GitHub): `python -c "import secrets; print(secrets.token_urlsafe(32))"` twice. Generate two UUIDs with `python -c "import uuid; print(uuid.uuid4())"`.
3. Set `FLEETLUMA_DATABASE_PATH` to a writable `.db` location, and set `FLEETLUMA_HOSTS_JSON` *in your local shell* to an array: `[{"id":"<UUID_A>","name":"pc-a","os":"windows","token":"<TOKEN_A>"},{"id":"<UUID_B>","name":"pc-b","os":"linux","token":"<TOKEN_B>"}]`. Choose each machine's actual OS. Do **not** commit the populated JSON.
4. Start: `python -m uvicorn fleetluma_backend.app:app --app-dir backend --host 0.0.0.0 --port 8000` from repo root.
5. Determine computer A's LAN IPv4 address (`ipconfig` on Windows or `ip -4 addr` on Linux); allow incoming TCP 8000 **only** on your private trusted network.
6. Open `http://<PC_A_LAN_IP>:8000/api/v1/hosts` from computer B. Before agents run, both registered hosts must read **PENDING**.

## Agent on each actual computer

From the repository root, install `python -m pip install -r agent/requirements.txt`. Start separately from `agent/` with environment variables **set in the active shell**, not by merely saving an `.env` file:

- `FLEETLUMA_COORDINATOR_URL=http://<PC_A_LAN_IP>:8000`
- `FLEETLUMA_AGENT_TOKEN=<correct token for THIS machine>`
- `FLEETLUMA_DISK_PATH`: an actual mounted path, e.g. `C:\\` or `/`
- `FLEETLUMA_INTERVAL_SECONDS=10` (optional)

Run `python -m fleetluma_agent.main` from `agent/`. After ~10 seconds check `/api/v1/hosts` again: **two different** UUIDs and host names must both become CONNECTED with real sample measurements. Do not run two fake agents on one computer and label them as physical two-machine evidence.

## Android device

**Emulator on the backend PC:** `cd mobile`; `flutter create --platforms=android --project-name fleetluma .`; `flutter pub get`; `flutter run --dart-define=FLEETLUMA_API_BASE_URL=http://10.0.2.2:8000`.

**Physical Android phone:** enable USB debugging, connect to the same private LAN and use `flutter run --dart-define=FLEETLUMA_API_BASE_URL=http://<PC_A_LAN_IP>:8000`. If you install the CI-built APK directly, it is configured for the emulator URL and **will not automatically reach a physical PC**; rebuild with the LAN IP for physical device testing.

## Evidence checklist (fill only after execution)

| Check | Actual evidence (device, local time, observed result) | Result |
| --- | --- | --- |
| Two different physical PCs with OS details | NOT TESTED | Pending |
| Backend reachable from PC B | NOT TESTED | Pending |
| Both real agents show distinct CONNECTED hosts | NOT TESTED | Pending |
| Android lists both real hosts and CPU/RAM/disk | NOT TESTED | Pending |
| Stop PC B agent, wait >35 s, verify STALE (not powered-off claim) | NOT TESTED | Pending |
| Restart PC B agent; verify CONNECTED again | NOT TESTED | Pending |
| POST with invalid token returns 401 and heartbeat unchanged | NOT TESTED on LAN | Pending |
| Stop/restart approved demo HTTP service; unhealthy -> healthy | Depends on FL-10, NOT TESTED | Pending |

## Troubleshooting

- Phone cannot reach API: `127.0.0.1` on the phone/emulator is **not** the coordinator PC; use real LAN IP or Android emulator `10.0.2.2`. Ensure same Wi-Fi, firewall rules and bind address.
- Agent stuck PENDING: host JSON not loaded into the backend process; wrong per-host token; wrong LAN IP; wrong configured disk path.
- Agent STALE: confirm clock-independent server last_seen_at; token auth failures must never update last_seen_at.
- Device can connect but shows empty: hosts must be provisioned before starting agents.
- All demo secrets must be rotated/deleted after the demo.

**Safety:** This guide is a test plan, **not** proof that physical LAN integration succeeded.
