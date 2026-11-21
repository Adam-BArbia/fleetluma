# FleetLuma — Figma V1 UI mockups and prototype (FL-21)

> **Canonical editable source:** [Open the FleetLuma Figma design](https://www.figma.com/design/6ma0f4jjB4Rtxnt25zBAdr)
>
> **Jira:** [FL-21 — Produce FleetLuma Figma UI mockups and clickable prototype](https://adambenarbia.atlassian.net/browse/FL-21)
>
> **Status:** Design created; review and native backup outstanding. All screen data is **illustrative**, not a running monitoring session.

## What is in Figma

The linked Figma Design file, **FleetLuma — V1 UI Mockups + Clickable Prototype (FL-21)**, was created in Adam Ben Arbia's connected Figma team. It is built from native, individually editable Figma frames, text, component instances, rectangles, and variables — **not** an embedded screenshot. The initial structural inspection reported 11 top-level screens and 621 editable nodes (180 frames, 299 text nodes, 59 instances and 83 rectangles), with zero image-filled mockup screens.

### Mobile flows — 393 × 852

| Screen | Figma node | Purpose |
| --- | --- | --- |
| Fleet overview | `1:34` | Agent status and host utilization; distinguishes live and last-known data |
| Host details | `1:77` | CPU/RAM/disk, heartbeat, history range controls (15m, 1h, 24h) |
| Top processes | `1:143` | Read-only process CPU and memory snapshot |
| HTTP checks | `1:181` | HEALTHY/UNHEALTHY service-check examples and latency |
| Cloud operator login | `1:229` | Cloud-mode-only sign-in concept |
| Edge states | `1:263` | Loading, empty fleet, network error, and stale-not-live |

### Desktop web flows — 1380 × 870

| Screen | Figma node | Purpose |
| --- | --- | --- |
| Fleet overview | `2:50` | Summary tiles, agent list, CPU chart |
| Host details | `2:138` | History, host resources, process and service panels |
| Top processes | `2:218` | Read-only process table |
| HTTP checks | `2:291` | Status, latency, recent checks |
| Cloud operator login | `2:374` | Cloud-mode-only sign-in concept |

To open a specific frame, go to the Figma source URL and select that named frame in the Layers panel. For example, [mobile overview](https://www.figma.com/design/6ma0f4jjB4Rtxnt25zBAdr?node-id=1-34) and [desktop overview](https://www.figma.com/design/6ma0f4jjB4Rtxnt25zBAdr?node-id=2-50).

### Design system

Reusable main components include **Metric tile**, **Mobile nav link**, **Host list item**, and **Action button**. The file also contains FleetLuma semantic color and spacing variable collections. Prototype `ON_CLICK` navigation has been configured for cross-screen links, bottom tabs, and desktop sidebar controls. Same-frame self-navigation is intentionally omitted where Figma disallows it.

**Prototype verification caution:** after a first visual check of the mobile and desktop overviews, host details, and login, the Figma Starter team reached its connector tool-call limit. Some mobile component sizing was subsequently adjusted; final *post-fix* screenshot review and end-to-end Present-mode test are **not yet recorded**. Do not report the design as fully accepted until manual review.

## Product semantics to preserve during implementation

- Host status: `CONNECTED`, `PENDING`, `STALE`; **STALE does not imply a powered-off machine**.
- For stale hosts, historical measurements must be explicitly identified as **last known, NOT LIVE**.
- CPU, memory, and disk readings come from reporting host agents; HTTP service checks are separately evaluated.
- Processes are **read-only**; there is no remote process-kill or command-execution feature.
- Operator authentication is a **cloud-mode** flow; the local SQLite demo does not require login.
- Error/recovery screens must avoid displaying old data as if freshly collected.
- The figures, process names, URLs, and statuses in this design are fictitious examples.

## Versioning and native backup

The **Figma cloud file is currently the editable source of truth**. This GitHub directory is a discoverable, reviewable **design handoff**, but **it does not yet contain a native `.fig` backup**. The connected Figma API tools do not offer `.fig` binary export; a GitHub documentation link cannot be treated as a versioned binary.

To archive an actual editable backup:

1. Open the linked file in Figma with an account that has export access.
2. In Figma, use **File → Save local copy** to download the real `.fig` document (menu wording can vary).
3. Place the exported file at `docs/design/FleetLuma_V1_UI_Mockups.fig`.
4. Commit it on the FL-21 design branch and include it in the GitHub pull request; note the export date and source file key.
5. Open the local copy in Figma to verify the frames and interactive links survived the export/import process.
6. Add reviewed screenshots or PDF exports to this directory and link evidence in FL-21.

**Do not** create an empty or placeholder `.fig` file and claim it is a backup.

## Acceptance review

- [x] Native editable Figma source exists in Adam's Figma team
- [x] Six mobile screens and five desktop screens created
- [x] Reusable components and semantic variables created
- [x] Clickable cross-screen prototype interactions authored
- [ ] Manually verify Present-mode navigation and all frames after the latest UI polish
- [ ] Confirm/organize the design within Adam's intended FleetLuma project folder
- [ ] Export, upload, and round-trip verify a native `.fig` backup
- [ ] Add final reviewed screenshots/export evidence
- [ ] Review against the actual Flutter/FastAPI V1 scope and approve FL-21

This documentation is deliberately separate from app implementation; it does not change the running backend, agents, or Flutter mobile code.
