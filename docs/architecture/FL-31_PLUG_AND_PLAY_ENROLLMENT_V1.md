# FleetLuma v0.1.0 — Approved Plug-and-Play Enrollment Architecture

**Status:** design approved, **implementation not started**. Replaces the manual host-provisioning requirements of the earlier private-pilot release guide. **Release remains blocked** until Windows and Linux installers and end-to-end pairing pass.

**Architecture source of truth:** `docs/uml/plantuml/30_cloud_deployment.puml`, expanded by the enrollment sequence and state model below. Existing FastAPI monitoring ingestion, PostgreSQL private schema, Supabase Auth JWT verification and Flutter dashboard remain.

## 1. Binding product decisions

- Agent displays a short enrollment code; operator enters it in Flutter dashboard and expressly approves after seeing device details.
- Monitoring runs as a durable OS background service. A distinct native configuration companion can open/close without stopping monitoring.
- Both Windows and Ubuntu/Debian-based Linux installation packages are in v0.1.0 release scope. Windows packaging and acceptance first, Linux before v0.1.0 final sign-off.
- No Python/Git/WSL, PostgreSQL password, manual environment variables, or agent token copy/paste for a normal installation.
- Single account may enroll multiple computers. A host belongs to a **fleet workspace**, not merely to a display name. Membership governs who can see it.

## 2. Logical components and trust boundaries

1. **FleetLuma Agent Service (Python + psutil)**: starts on OS boot, records metrics, maintains locally protected per-device reporting token, communicates outbound via HTTPS only, and never accepts remote system commands.
2. **FleetLuma Setup UI (Flutter desktop)**: Windows and Linux companion for initial pairing, consent, connect/disconnect status, reconnect, and uninstall instructions; communicates with its local service through ACL-protected named pipe (Windows) or UNIX domain socket (Linux), not a public localhost port. GUI closure leaves the agent service running.
3. **Flutter Web Dashboard (Vercel static)**: authenticates operator with Supabase, shows Devices / Add Device / pending pairing approval / revoke, history and last-known readings. Dashboard never receives or displays the agent's long-lived credential.
4. **FastAPI Cloud API (Vercel functions)**: short-lived pairing workflow, authenticated operator actions, agent reporting, revocation, and audit; stateless across requests.
5. **Supabase PostgreSQL private `fleetluma` schema**: transactions and durable pairing state (no FastAPI memory sessions), owner/membership controls, token hashes, samples and audit.
6. **Supabase Auth**: verifies human operator JWT via existing asymmetric JWKS issuer, audience, expiry; agents **never sign in as Supabase users**.

Vercel SSO is allowed on the dashboard for private pilots, **not** on the public-to-agents API domain. Public network reachability of agent endpoints is not permission to report: server rejects all requests without valid enrollment/session or reporting credentials. Separate production API/Web domains are established before general release.

## 3. Enrollment: exact protocol

**Choice:** Server **generates** and returns the *display code* in response to the agent's enrollment request. The agent **displays** it. This preserves the chosen agent-initiated user experience while preventing an agent from choosing a weak or colliding code.

1. On pressing **Connect this device**, the local agent generates a random **256-bit device report credential** and stores it under OS-specific restricted service identity; never expose the raw value in GUI or logs. Agent also starts a fresh enrollment request. The server returns a 256-bit **private enrollment session secret** and a short human-readable user code. Both are distinct from the reporting credential.
2. Agent sends `platform`, `hostname`, `agent_version`, `report_token_sha256` (only a digest), and supported capabilities. It does **not** send raw report token. Server creates a PENDING pairing session with a random, unique human code, random private enrollment secret hash, and a 10-minute expiration. Persist only hashes of secrets and display codes, normalizing ambiguous characters; do not return or log secrets from DB. Enrollment request returns `device_code` (private session secret), `user_code`, `verification_uri`, `expires_in=600`, `interval=5`.
3. GUI displays `user_code` (8 characters from a 32-symbol uppercase non-ambiguous alphabet, grouped 4-4: 40 bits of entropy), `https://fleetluma-web.vercel.app/devices/pair` and a QR code optionally containing the short verification URL/code. No raw secret in QR.
4. Authorized operator signs into dashboard, chooses **Add device**, enters code, sees claimed name/OS/version/capabilities, and compares the code with the physical machine. Approval requires an explicit action, accepted monitoring scope, and choosing a workspace; no auto-approval.
5. Server validates operator JWT **and** fleet membership/permission, validates pending session, cooldown, attempts and expiry, and in one database transaction creates or authorizes the host, binds the precommitted `report_token_sha256`, sets owner/workspace, writes an immutable audit event, and marks pairing APPROVED/CONSUMED. Require a valid UUID workspace and do not infer membership from user-controlled Supabase `user_metadata`.
6. While waiting, the agent polls `POST /api/v1/agent/pairings/token` with its **private session secret** over TLS at >=5-second spacing; on approval response is `200 {status: "paired",host_id,workspace_id}` without sending the reporting token. On pending, return explicit `authorization_pending`; on denial, expiry or throttling, return typed error. Because the device already holds the reporting credential, the exchange is retry-safe without ever returning a durable secret from the server.
7. Agent switches to normal `POST /api/v1/agent/reports` with its locally held reporting bearer token; backend locates an ACTIVE non-revoked host by token hash and commits reports and heartbeat atomically. Dashboard sees PENDING host until first valid sample, then CONNECTED.
8. After OS reboot/restart, agent loads the locally protected token; no interactive login or pairing. If token missing, corrupt, or revoked, service stops reporting and GUI offers **Pair again**; never silently generate a new server identity.

A user-code alone cannot fetch agent credentials or finalize a claim. Secret-enrollment-session polling is restricted to the same requesting agent. Bind the claim to the precommitted report-token digest and consume the session exactly once.

## 4. Pairing and device states

`pairing_sessions.status`: `PENDING -> APPROVED -> CONSUMED`; terminal alternatives `DENIED`, `EXPIRED`, `CANCELLED`. APPROVED is short-lived until agent acknowledgement; consumption is idempotent, never creates duplicate hosts. A new pairing request from the same installing agent explicitly cancels its old pending session.

`hosts.lifecycle`: `ACTIVE | REVOKED`. Host reporting state is **separate** and derived from heartbeat: `PENDING` (registered, no sample), `CONNECTED` (last server receive <=35 seconds), `STALE` (older). A revoked device is rendered **REVOKED**, regardless of historical samples; never shown as CONNECTED. A disconnected machine remains owned by its workspace; do not automatically revoke it.

Approval is non-transferable across workspaces. Hostname, OS and agent version are **self-reported hints**, never hardware attestation.

## 5. PostgreSQL conceptual changes (migration design, no DDL executed)

Existing private tables: `hosts(id,name,os,token_hash,last_seen_at)`, `samples`, `process_snapshots`, `services`, `service_checks`. Keep their core metrics relationships.

**New table `workspaces`**
- `id uuid PK`, `name text`, `created_by uuid` (Supabase Auth user), `created_at timestamptz`.

**New table `workspace_memberships`**
- `workspace_id uuid FK`, `user_id uuid`, `role enum('owner','admin','viewer')`, `created_at timestamptz`, unique(workspace_id,user_id).
- Owner/admin can approve, revoke and rename devices. Viewer can read permitted fleet only. Bootstrap first workspace/member from existing approved operator UUID using a reviewed one-time migration; never silently grant all authenticated users.

**New table `pairing_sessions`**
- `id uuid PK`, `user_code_hash text UNIQUE`, `device_code_hash text UNIQUE`, `report_token_hash text`, `display_name text`, `platform text`, `agent_version text`, `capabilities jsonb`, `status text CHECK`, `expires_at timestamptz`, `attempts int`, `next_poll_at timestamptz`, `approved_by uuid NULL`, `workspace_id uuid NULL`, `host_id uuid NULL`, `created_at/approved_at/consumed_at timestamptz`.
- No plaintext code or secret stored. Apply `SELECT ... FOR UPDATE` and unique constraints to handle races. Expired pairings and sensitive client metadata purged by scheduled policy, not by request-local memory.

**New table `device_audit_events`**
- `id uuid PK`, `host_id uuid NULL`, `pairing_id uuid NULL`, `workspace_id uuid NULL`, `actor_user_id uuid NULL`, `action text`, `created_at timestamptz`, `details jsonb` (allowlisted, redacted; never tokens/user codes).
- Actions: requested, approved, denied, consumed, revoked, re-paired, installation/recovery failure. Keep structured audit retention policy independent of 24h metric retention.

**Extend `hosts`**
- `workspace_id uuid NOT NULL FK`, `lifecycle text NOT NULL DEFAULT 'ACTIVE'`, `enrolled_at timestamptz`, `revoked_at timestamptz NULL`, `agent_version text NULL`, `credential_version integer NOT NULL DEFAULT 1`, `name` remains editable alias distinct from raw hostname.
- Preserve existing `TUFFEST` UUID, samples and process snapshot: assign it to the first operator's workspace and retain its existing hashed token until deliberately re-paired or revoked. No destructive migration or unapproved host exposure.
- For v0.1.0 prefer a single active digest per host, and revocation as a transactional state change that is checked on **every** report; explicit rotation via re-pairing. Avoid dual-active credentials.

Every table stays in the **private `fleetluma` schema**, with no `anon`/`authenticated` schema usage grant or browser SELECT. Server applies verified JWT membership checks in its API, using a private database connection. Keep RLS enabled as defense in depth; no broad policies to bypass private-schema restrictions.

## 6. API contract delta (versioned `/api/v1`; detailed OpenAPI must match before implementing)

| Method | Path | Principal | Success | Contract |
|---|---|---|---|---|
| POST | `/agent/pairings` | Unenrolled device | 201 | Create pairing with hashed future token; returns private `device_code`, display `user_code`, verification URL, 600 seconds, poll interval |
| POST | `/agent/pairings/token` | Device session secret | 200/202 | Query approval; after approval yield host UUID/workspace ID once, idempotent `paired` confirmation; pending/denied/expired errors |
| POST | `/agent/pairings/cancel` | Device session secret | 204 | Cancel only its own pending pairing |
| POST | `/operator/pairings/resolve` | Approved operator JWT | 200 | Resolve normalized code to *safe public metadata* and session ID; does not approve |
| POST | `/operator/pairings/{id}/approve` | Workspace owner/admin JWT | 200 | Atomic explicit approval, workspace ownership and idempotent host registration |
| POST | `/operator/pairings/{id}/deny` | Workspace owner/admin JWT | 204 | Deny pending pairing |
| GET | `/operator/hosts` | Workspace member JWT | 200 | List devices, lifecycle, status, version, editable name; workspace-scoped |
| PATCH | `/operator/hosts/{id}` | Workspace owner/admin JWT | 200 | Rename device only; no arbitrary ownership reassignment |
| POST | `/operator/hosts/{id}/revoke` | Workspace owner/admin JWT | 200 | Idempotent revoke, invalidate reporting credential |
| GET | `/operator/device-audit` | Workspace owner/admin JWT | 200 | Paginated audit events, redacted |
| POST | `/agent/reports` | Active agent bearer token | 202 | Existing route retained; require ACTIVE and workspace binding |
| GET | `/hosts`, `/hosts/{id}`, history, processes | Workspace member JWT | 200 | Existing endpoints retained with explicit workspace authorization |

All paths above are appended to `/api/v1` (except the existing health path). Use consistent JSON `error.code` values, request IDs, and `Cache-Control: no-store` for pairing responses. Never put short codes, device session secrets or reporting tokens in URLs, error bodies, logs, analytics or audit fields. Rate-limit even unknown codes with uniform responses; unauthorized lookup must not enumerate pending devices.

**HTTP semantics:** unknown/invalid agent token `401`; expired pairing `410`; denied pairing `403`; premature polling `429` + Retry-After; already consumed request `409` unless idempotent same-device acknowledgement; unauthorized operator `401/403`. Use no shared browser credentials on device endpoints. Return client safe errors. Use HTTP 200 plus \`status: pending\` for ordinary permitted polls, not HTTP 202.

## 7. Security and anti-abuse controls

- Human code: 8 characters from 32-character non-confusable alphabet, random server-side; 10-minute TTL; 5 wrong attempts per operator/IP over rolling window with per-account/global throttling. The visible code is only a lookup capability, not a report credential.
- Device session and per-device report credential: independent cryptographic 256-bit values. Store only SHA-256 hashes server-side. Network TLS verified; no HTTP downgrade, redirects, or forwarding authorization headers.
- Poll <=1 request per 5 seconds per pending session; enforce server-side persistently (database or distributed rate limiter) because Vercel functions are stateless. Follow retry/backoff rules and enforce global rate limits. User explicitly initiates new pairing; no infinite background session creation. These recommendations reflect RFC 8628's device-grant protections, without claiming protocol compliance.
- Operator approval: signed Supabase JWT, active membership, workspace binding, explicit confirmation; only owner/admin can enroll/revoke. Do not authorize using editable `user_metadata`. Block CSRF wherever cookies might be used; JWT bearer requests require exact CORS allowlist.
- Recovery: losing local reporting credential requires **new physical pairing with operator approval**, not unauthenticated reset based on hostname, OS ID or serial.
- Pairing prevents device-code swapping: session secret belongs to session + one precommitted report token hash; host creation and session consumption under one transaction.
- Revocation: every report verifies active host lifecycle; no cache bypass. Denied attempts cannot modify `last_seen_at` or insert sample. Deleting a device should be separated from revocation and require higher authorization.
- Build and installation artifacts are signed where supported and published with checksums; installation prompts only for actual required OS permissions. Avoid running monitoring agent as full admin/root when possible. No remote commands, screenshots, keystrokes, process environments or command lines.
- Cloud environment secrets stay only in Vercel/server/secure local agent store. No runtime use of PostgreSQL URI in consumer installation.
- Privacy/consent: GUI clearly states CPU, memory, disk, process names/PIDs and polling interval; offers stop, revoke and uninstall. `STALE` never implies host powered off.

## 8. Packaging and lifecycle

**Windows:** signed `FleetLuma-Setup.exe` (Inno Setup or WiX, choose the installer tool before coding); package frozen Python 3.12+ monitoring service plus Flutter Windows configuration UI, no system Python. Start service on boot; named-pipe ACL restricts UI control to local authorized OS user/admin. Encrypt credential with Windows DPAPI for the service identity; no plaintext registry or environment variable persistence. Stop/uninstall remove service; offer explicit revoke pairing as a separate action requiring operator auth.

**Linux v0.1.0 scope:** Ubuntu/Debian `.deb` package containing the frozen/pinned Python monitoring service, Flutter Linux configuration UI, `systemd` service, desktop entry, and restricted service-owned credential store (`0600` files with private directory/optional systemd encrypted credentials). UNIX socket permissions control local UI access. Other distros are **not promised** for v0.1.0. Linux headless installations may present code via a supported terminal status command without requiring full desktop.

**Service lifecycle:** NOT_PAIRED -> PAIRING -> PAIRED/STARTING -> MONITORING; recoverable states OFFLINE_BACKOFF, REVOKED, NEEDS_REPAIR. Service restarts with exponential network backoff, preserves token locally across normal restarts, and never re-pairs silently. GUI status is driven by local service IPC. Updating binaries must preserve secure credentials and host UUID.

## 9. Compatibility, migration and scope

Existing `TUFFEST` remains online through a staged migration. New enrollment API and schema are added additively, dual system use only in protected staging, then the old manual enrollment CLI becomes **administrator-only break-glass**, not a normal installation path. Existing raw token never copied into a public app. Validate migration on a DB copy first.

Release boundary: **Windows and Ubuntu/Debian packaging + pairing + background monitoring + dashboard enrollment/revoke + existing CPU/RAM/disk/process reporting** are mandatory. External HTTP checks (FL-19) and novel alerting remain deferred unless separately accepted. Android dashboard support remains on the overall architecture, but a signed Android release is not a dependency for the initial device-pairing feature.

## 10. Mandatory verification matrix

1. Install on clean Windows and Ubuntu/Debian machines with no Python/Git, obtain pairing code, approve through authorized dashboard; restart service and reboot host; keep reporting with no interaction.
2. Parallel agent pairings and double-approval race: no duplicate devices, tokens or cross-workspace links; expired/denied/cancelled codes never enroll.
3. Viewer/unknown operator cannot approve or revoke; owner/admin from another workspace cannot see the request's linked records; no code enumeration.
4. Rejected invalid/revoked agent token returns 401 without heartbeat/sample update; authorized agent reports return 202 and persist a real snapshot.
5. Revocation stops new data immediately; re-pairing requires operator confirmation and invalidates old credential.
6. Network outage and server restart during pairing do not lose pairing state; malformed, replayed, rate-limited, and too-frequent requests are safely rejected.
7. CORS, TLS, request limits, no logged/displayed secrets, no DB credentials in browser/installers; install/uninstall service privilege audit.
8. Existing TUFFEST host/samples survive schema migration and legacy compatibility period without duplicate registration.
9. Codes and short-lived sessions purge after TTL, audit retention defined; workspace membership and ownership are enforced on all existing host routes.
10. Windows and Linux signed/reproducible packaging pipeline verified, release rollback exercised, version compatibility checked.

## 11. Architecture change checklist before any implementation

- Update UML domain classes: Workspace, Membership, PairingSession, Host.lifecycle, DeviceAuditEvent; preserve Host/Sample/ProcessSnapshot relations.
- Update FastAPI and Agent class diagrams, activity enrollment, pairing sequence, agent state, Flutter flow, component and final deployment diagram. Keep the existing 30-diagram numbering consistent rather than replacing the final deployment topology with the local demo.
- Update `docs/api/openapi.json` to describe new pairing/admin routes and correct obsolete local-LAN unauthenticated read descriptions; validate against runtime contract tests.
- Add reviewed additive migration with one-time TUFFEST workspace backfill and exact FK/unique/rate-limit indexes; perform rollback and permission analysis.
- Update v0.1 release notes, install/uninstall/privacy documentation and Jira tasks to distinguish documented design from implementation.

**Current checkpoint:** Architecture decisions captured here; NO code, database migration, installer build, token rotation or production promotion has been performed under this design.
