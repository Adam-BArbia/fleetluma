# FleetLuma — editable UML models

This directory contains the **29 original plain-text PlantUML (.puml) source files** for the FleetLuma architecture atlas (FL-3), plus a **30th cloud deployment proposal** added under FL-14.

Every model is a planned design, **not a generated implementation**. Models cover the user/operator scope, automation, domain and service classes, component and package boundaries, deployment, object snapshot, activities, state machines, REST contract, reporting and health-check sequences, communication, heartbeat timing, interaction overview and coordinator internal structure.

## Render

Use an installed PlantUML CLI, PlantUML IDE extension, or approved local PlantUML renderer. Example: `plantuml -tsvg docs/uml/plantuml/*.puml`. PlantUML syntax and rendering must be checked as part of design review; source files are authored diagrams, not evidence that tests were run.

## Key architecture constraints

- Agents push authenticated OS metrics; backend separately checks approved HTTP endpoints.
- Host **STALE** is not the same as a verified machine outage.
- Services are linked to zero or one host, and an independent HTTP service may have no host.
- Process snapshots are read-only; no remote shell or process termination.
- Flutter polls REST every five seconds; local mode uses SQLite, while the proposed cloud mode uses PostgreSQL.
- Two physical computers plus Android emulator/phone are planned for the final demo.

See `docs/requirements/PROJECT_DEFINITION.md` for requirements and `docs/architecture/CLOUD_DEPLOYMENT_FL-14.md` for the proposed cloud architecture. The original PDF architecture atlas may remain separately downloadable until it is intentionally added to this public repo.
