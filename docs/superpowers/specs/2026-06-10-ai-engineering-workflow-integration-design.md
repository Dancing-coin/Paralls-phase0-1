# AI Engineering Workflow Integration Design

## Problem

The project already has Harness profiles, Superpowers specs/plans, and Goal support, but the relationship between OpenSpec-style intent, Superpowers execution discipline, Harness verification, Goal state, and native subagent coordination is implicit.

## Design

Add a project-owned workflow document and a static `change-lifecycle` harness profile. The workflow document defines the four-layer contract:

- OpenSpec/design artifacts define what changes.
- Superpowers skills define how agents execute.
- Harness profiles define whether results are accepted.
- Goal tracks long-running execution state.

The harness profile verifies that this workflow is discoverable from project entry points, backed by versioned profile/rule manifests, reflected in reusable templates, and routed through `AGENTS.md`.

## Boundaries

- This is a development-process and verification-layer change only.
- It must not change Godot runtime behavior, backend authority behavior, or Siming logic.
- Goal is execution state, not a source of truth.
- Goal records active task continuity while OMX remains the repository orchestration/runtime-state surface.

## Acceptance

- `python scripts/verification/harness.py --profile change-lifecycle` passes.
- `python scripts/verification/harness.py --profile docs` passes.
- `python scripts/verification/harness.py --profile all` includes `change-lifecycle`.
