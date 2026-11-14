# FleetLuma — Sprint 0 Review and Retrospective

**Review date:** 2026-11-14  
**Project:** [FleetLuma](https://github.com/Adam-BArbia/fleetluma)  
**Jira:** [FL board](https://adambenarbia.atlassian.net/jira/software/projects/FL/boards/2/backlog)  
**Sprint:** FL Sprint 0 — project initiation and architecture documentation  
**Status:** Internal, retrospective documentation review. **Not** a professor evaluation or evidence of prior attendance.

## Sprint goal

Publish a versioned and reviewable FleetLuma product definition and editable UML design, with accurate Jira–GitHub links and a reproducible UML rendering check.

## Deliverables and evidence

| Issue | Result | Evidence |
|---|---|---|
| [FL-1](https://adambenarbia.atlassian.net/browse/FL-1) | Public repository, README and security-focused .gitignore | Initial commit `a04700c` and repository main |
| [FL-2](https://adambenarbia.atlassian.net/browse/FL-2) | PRD in Markdown and a PDF export | [PR #1](https://github.com/Adam-BArbia/fleetluma/pull/1), merged |
| [FL-3](https://adambenarbia.atlassian.net/browse/FL-3) | 29 editable PlantUML sources and architecture notes | [PR #2](https://github.com/Adam-BArbia/fleetluma/pull/2), merged |
| [FL-4](https://adambenarbia.atlassian.net/browse/FL-4) | Render/syntax QA, three syntax defects fixed, timing diagram improved, GitHub Actions validation | [PR #3](https://github.com/Adam-BArbia/fleetluma/pull/3), [green render run](https://github.com/Adam-BArbia/fleetluma/actions/runs/43583729787) and [QA report](../uml/QA_REPORT_FL-4.md) |
| [FL-5](https://adambenarbia.atlassian.net/browse/FL-5) | This retrospective review and handoff | Review documentation on this issue's branch |

All delivered items were created and recorded on their actual dates. No Scrum events, approvals, sprint demonstrations, or implementation have been backdated.

## Technical decisions confirmed

- Mobile-first **Flutter** client; **FastAPI/SQLite** coordinator; **Python psutil** agents on Linux/Windows.
- Agents push authenticated CPU/RAM/disk and bounded read-only top-process snapshots.
- Coordinator independently checks allowlisted HTTP services and stores 24-hour history.
- Host reporting freshness (CONNECTED / STALE) and HTTP endpoint health (HEALTHY / UNHEALTHY) are independent.
- Local-network demonstration with two physical computers and Android device/emulator.
- Mobile REST polling every five seconds; no cloud hosting, remote command execution, process termination or arbitrary external scanning.

## What went well

- Jira issues were connected to separate GitHub documentation branches and merged PRs.
- Editable UML source makes future architecture changes reviewable.
- Automated PlantUML checks found real syntax errors, which were corrected before completion.
- Project name, feature scope and architectural boundaries were frozen before coding.

## What did not go well / risks

- Work was reconstructed at the end of the academic term; previous professor sprint assessments were not performed or recoverable through this record.
- Many diagrams were designed before a working vertical slice existed; they remain proposals and may need updates after implementation.
- No implemented backend, monitoring agent or mobile app has been demonstrated at the review date.
- No confirmed second collaborator account/role in Jira yet. Do not assign work to them without adding them.
- Business Model Canvas, detailed prioritized product backlog, and commercial presentation are still outstanding relative to the provided course description.
- A local network demo may fail without IP/firewall/API reachability verification; test connectivity early.

## Sprint 1 recommendation

First deliver one end-to-end vertical slice: **one real agent → authenticated FastAPI report → persisted metric → Flutter host list**. Then extend to two machines, status freshness, HTTP service checks, history graphs and top processes. Publish the API contract early to unblock parallel work.

## Proposed Definition of Done for implementation issues

1. Implementation on an issue-linked feature branch with a PR to `main`.
2. Acceptance criteria demonstrated with real results, not mock data presented as real.
3. Relevant tests pass and security boundaries remain intact.
4. New behavior is documented; UML updated if architecture changes.
5. Review evidence added to Jira before transition to Done.

**Sprint 0 completion means the design artifacts are prepared and reviewed internally. It does not mean FleetLuma is implemented or that the professor approved the sprint.**
