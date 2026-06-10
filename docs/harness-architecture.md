# Harness Architecture

## System Overview

Paralls uses a project-owned harness under `.harness/` and `scripts/verification/`. The harness is not an alternate runtime architecture; it is the verification and lifecycle layer around the Godot project, Python backend, docs, and agent workflow.

## Layers

```text
AGENTS.md / docs/INDEX.md / docs/harness.md
        |
        v
.harness/profiles/*.json  -> profile order and dispatch scripts
.harness/rules/*.json     -> stable rule ids and evidence paths
.harness/references/*.json -> external reference taxonomy mapped to project artifacts
docs/ai-engineering-workflow.md -> OpenSpec/Superpowers/Harness/Goal workflow
        |
        v
scripts/verification/harness.py
        |
        +-- static profiles: docs, boundaries, drift, backend-contract, godot-project, release-gate, harness-lifecycle, change-lifecycle, harness-reference
        +-- runtime profiles: phase0, phase1-slice
        |
        v
.harness/verification/
        +-- latest reports
        +-- run manifest
        +-- baseline
        +-- previous-run diff
        +-- runs/<run-id>/ archive
```

## Boundary

The harness may inspect docs, manifests, Python source, Godot scene text, logs, screenshots, and generated reports. It must not become the game runtime, backend authority, Siming host, or Godot scene owner.

## Change Lifecycle

`docs/ai-engineering-workflow.md` defines the project workflow for AI-assisted changes: OpenSpec/design artifacts define intent, Superpowers skills enforce execution discipline, Harness profiles accept or reject results, and Goal tracks long-running execution state. New workflow state should use Goal and `.harness` artifacts; OMX is retired for new project workflow state.

## External Reference Coverage

`.harness/references/awesome-harness-engineering.json` is the project-owned reference taxonomy adapted from `ai-boost/awesome-harness-engineering`. It maps agent loop, planning, context, tool, permission, memory/state, orchestration, verification, observability, debugging, human handoff, sandbox, and eval categories to concrete Paralls artifacts. The taxonomy is checked by the `harness-reference` profile so external ideas stay attached to maintained files instead of becoming a passive reading list.

## Future Profiles

Use `.harness/templates/profile-template.json` and `.harness/templates/rule-template.json` when adding new formal product modules. Each new module should add one profile, one rule manifest, one focused test file, and one report-producing check script. Workflow-level changes should also update the `change-lifecycle` profile when they alter Goal, Superpowers, OpenSpec/design, or native subagent routing.
