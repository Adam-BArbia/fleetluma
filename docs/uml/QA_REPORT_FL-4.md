# FL-4 — PlantUML verification record

**Date:** 2026-11-14  
**Scope:** 29 editable diagrams in `docs/uml/plantuml/`  
**Jira:** [FL-4](https://adambenarbia.atlassian.net/browse/FL-4)  
**Pull request:** [#3](https://github.com/Adam-BArbia/fleetluma/pull/3)

## Method

1. Inspected all 29 PlantUML source files for bounded `@startuml` / `@enduml` declarations and obvious structural problems.
2. Normalized compact class/interface/enum declarations that could be interpreted ambiguously.
3. Executed GitHub Actions **PlantUML validation** using the Ubuntu package of PlantUML and Graphviz, rendering every `.puml` to SVG.
4. Investigated renderer failures in the package, deployment, and object snapshot diagrams and corrected them.
5. Regenerated every SVG and examined a three-sheet visual overview of all 29 diagrams. Improved the timing diagram to remove overlapping annotations.
6. Verified a final GitHub Actions run completed successfully and produced exactly 29 SVGs. XML parsing of all SVGs found no unparseable documents or error placeholders.

## Evidence

- **Final green CI run:** https://github.com/Adam-BArbia/fleetluma/actions/runs/43583729787
- **Final artifact:** `fleetluma-uml-svg` attached to the successful workflow, containing 29 SVG files.
- **Review branch:** `qa/FL-4-plantuml-validation`
- **Deliverable:** source diagrams, renderer-validation workflow and this QA report.

## Acceptance decision

**Rendering QA: PASS.** All 29 sources produced SVG output; generated diagrams were reviewed as a contact sheet, and the heartbeat timing diagram was additionally inspected individually for legibility. This does not assert that every modeled implementation detail has been built or that UML designs are formally approved by the professor.

The workflow remains active for future modifications to UML source files and will detect rendering regressions on subsequent pull requests.
