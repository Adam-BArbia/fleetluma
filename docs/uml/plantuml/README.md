# FleetLuma PlantUML architecture atlas

This folder retains the original teaching/demo models and extends them with **v0.1.0 plug-and-play pairing target design**.

- **Final deployment target:** `30_cloud_deployment.puml` — Flutter Web/Android + cloud FastAPI on Vercel + private Supabase PostgreSQL/Auth + Windows service and Ubuntu/Debian systemd agent installers.
- **Pairing sequence:** `31_seq_device_pairing.puml` — agent requests server-generated short code, operator approves in dashboard, separate agent credential reports after approval.
- **Cloud model updates:** `01`, `02`, `03`, `04`, `05`, `06`, `07`, `11`, `14`, `15`, `17`, `18`, `19`, `20`, `21`, `22`, `23`, `28`, `29`, `30`, `31`. These describe **design targets**, not deployed implementations.
- **Historical local-classroom demonstration:** `09_deployment.puml` still illustrates 2 PCs, LAN HTTP and SQLite. It is **not** the production cloud deployment architecture. Other unchanged historical diagrams may retain local/demo context; their individual titles and notes do not override the final cloud diagram.

## Authoritative companion artifacts

- `docs/architecture/FL-31_PLUG_AND_PLAY_ENROLLMENT_V1.md`: protocol, workspace authorization, schema delta, API paths, packaging, and threat mitigations.
- `docs/api/openapi.json`: future v0.1.0 API contract, including **design-only** enrollment and device management endpoints.
- `docs/deployment/V0_1_PRIVATE_PILOT_RELEASE.md`: original manual bootstrap field-test runbook, now superseded for **normal users** by the agent pairing proposal. Manual provisioning remains administrator-only break-glass until decommissioned.
- PostgreSQL schema migration and background-service installers **have not been applied or built**.

## Render and validation

```bash
plantuml -tsvg docs/uml/plantuml/*.puml
python -m json.tool docs/api/openapi.json > /dev/null
```

Use the existing GitHub diagram render check and inspect all modified models. Verify path names, request/response attributes and lifecycle states in OpenAPI/UML against the architecture spec before runtime implementation. Rendering is syntax verification, **not** a test of pairing security or service installation.

## Invariants

1. Operator Supabase JWT is distinct from the per-host reporting secret.
2. Only workspace owner/admin can approve/revoke; viewer access is read-only, all host reads workspace-scoped.
3. Displayed pairing code is short-lived, one-time and not the agent reporting token.
4. Agent credentials stay on the device; database stores only hashes.
5. CONNECTED/STALE are heartbeat-derived and **REVOKED** supersedes either.
6. Cloud reporting is HTTPS; no agent redirects or remote process commands.
7. Vercel FastAPI is stateless; no in-process cron; the FL-19 service checker is an independent scheduled function.
8. Local/demo models cannot be substituted for `30_cloud_deployment.puml`.
