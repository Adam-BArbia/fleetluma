# FleetLuma

FleetLuma is a mobile-first infrastructure monitoring system for small fleets of Linux and Windows machines. It is a two-person software engineering / architecture course project tracked using Jira, GitHub, UML, and Scrum.

## Components

| Component | Current implementation |
| --- | --- |
| Monitoring agents | Python + psutil on Linux and Windows; CPU, RAM, disk, heartbeat and top-process snapshots |
| Coordinator API | FastAPI REST endpoints, authenticated agent report ingestion, host/service views and history |
| Classroom LAN mode | SQLite-backed coordinator and Android Flutter monitoring UI |
| Cloud V1 target | Vercel FastAPI + private Supabase PostgreSQL + Supabase Auth operator JWTs |
| Clients | Flutter Android and Flutter Web |
| Availability checks | Separate scheduled Supabase Edge Function code, not deployed |

**Authoritative target:** [cloud deployment UML](docs/uml/plantuml/30_cloud_deployment.puml). The [LAN diagram](docs/uml/plantuml/09_deployment.puml) documents the classroom demonstration only.

## Implementation versus deployment

The repository contains working implementation and automated tests; the old Sprint 0 placeholder description is obsolete. **No hosted FleetLuma V1 has been verified end-to-end.** Vercel API/Web projects are provisioned but have no deployments, and cloud environment credentials, operator approval, actual hosted JWT tests, persistent agent ingestion and scheduled checker execution remain acceptance gates. Do not treat passing CI as a production release.

- FastAPI and PostgreSQL source: [backend/](backend/)
- Windows/Linux monitoring agent: [agent/](agent/)
- Flutter mobile/Web: [mobile/](mobile/)
- API contract: [docs/api/](docs/api/)
- UML diagrams: [docs/uml/plantuml/](docs/uml/plantuml/)
- Cloud release prerequisites: [FL-20 preview release gate](docs/deployment/FL-20_PREVIEW_RELEASE_GATE.md) and [Web preview pipeline](docs/deployment/FL-20_WEB_PREVIEW_PIPELINE.md)
- Operator onboarding: [FL-18](docs/architecture/FL-18_OPERATOR_ONBOARDING.md)

## Authentication boundaries

In cloud mode, dashboard users authenticate via Supabase Auth signed JWTs. FastAPI verifies the signature, issuer/audience/expiry, and a backend operator UUID allowlist before permitting monitoring GET routes. The Flutter dashboard also checks operator approval before starting polling. Each agent uses a separate unique per-host token to POST reports; the PostgreSQL server stores only its hash. Do not copy an agent credential to the browser.

The private monitoring tables are deliberately not exposed to browser Data API roles. Configure actual secrets only in protected server/provider settings. Do not commit credentials, process command lines, or personally sensitive monitoring content.

## Local verification

For backend tests (Python 3.12 recommended):

```bash
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest -q tests
```

For agent tests:

```bash
cd agent
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

For Flutter (SDK version from CI workflow):

```bash
cd mobile
flutter create --platforms=web,android --project-name fleetluma .
flutter pub get
flutter analyze
flutter test
```

See individual component READMEs for environment and LAN demo setup. **Do not deploy the cloud API until private DB connectivity, operator authorization, CORS and agent transport are explicitly configured and tested.**

Project workflow: [FleetLuma Jira](https://adambenarbia.atlassian.net/jira/software/projects/FL/boards/2/backlog).
