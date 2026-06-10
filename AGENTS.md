# AGENTS Operating Guide For Paralls Phase 0 Demo

This file is the short entry map for agents working in this repository. Keep detailed guidance in versioned docs and verification scripts instead of growing this file into a manual.

## Mission

This repository is a runnable validation slice for Paralls `Phase 0`.

The goal is not to build the full product. The goal is to prove that the minimum dramatic runtime loop can run end-to-end inside a real Godot project plus a Python backend.

Minimum validated loop:

1. one Godot 3D scene loads
2. two agent-driven character replicas exist
3. player submits one structured dialogue input
4. backend returns one character dialogue response
5. voice playback or approved stub voice path is observable
6. one object interaction succeeds through backend authority
7. one object interaction fails with a structured constraint result
8. one object or environment state visibly changes
9. one minimal Siming catalyst causes an observable reaction

## Start Here

- `docs/INDEX.md`: repository knowledge map.
- `docs/ai-engineering-workflow.md`: OpenSpec, Superpowers, Harness, Goal, and native subagent workflow.
- `docs/harness.md`: verification profiles, reports, and evidence rules.
- `PHASE0_README.md`: short workspace summary.
- `docs/superpowers/specs/`: approved designs.
- `docs/superpowers/plans/`: implementation plans.

Use the smallest relevant harness profile before claiming completion:

```powershell
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile boundaries
python scripts/verification/harness.py --profile drift
python scripts/verification/harness.py --profile change-lifecycle
python scripts/verification/harness.py --profile phase0
python scripts/verification/harness.py --profile phase1-slice
python scripts/verification/harness.py --profile all
```

Reports are written under `.harness/verification/`.

## AI Engineering Workflow

- Use OpenSpec/design artifacts for what changes.
- Use Superpowers skills for how changes are executed.
- Use Harness profiles for acceptance evidence.
- Use Goal for large or long-running execution state.
- Use native subagents only for independent bounded work lanes.
- OMX is retired for new project workflow state.

## Core Boundaries

Godot is responsible for:

- local high-frequency embodiment
- player input terminal behavior
- local visible and audio presentation
- local visual fact emission

Godot is not responsible for:

- world-truth authority
- full character cognition
- canonical Siming judgment
- backend-owned runtime state

Backend is responsible for:

- structured protocol contracts
- minimal session routing
- minimal character service
- minimal ESM authority
- minimal Siming catalyst
- event trace and audit truth

Cross-boundary input must be structured intent. Do not send raw keyboard, mouse, camera, or local scene noise to backend business logic.

Object and environment changes must be driven by structured backend result objects. Do not fake success purely in local scene presentation.

Siming may emit high-level catalyst outputs only. It must not directly control low-level character motion, animation bones, or physical world truth.

Do not regress into external full-bone high-frequency remote driving. Backend sends semantic or structured results, not raw pose streams.

## Editing Rules

- Preserve the existing root Godot project.
- Keep Phase 0 scenes under `scenes/phase0/`.
- Keep Godot scripts under `scripts/`.
- Keep backend code under `backend/`.
- Keep harness and verification code under `scripts/verification/`.
- Keep generated evidence under `.harness/verification/`.
- Do not copy large design docs into code comments.
- No new dependencies unless explicitly requested.

## Verification Rules

Backend milestone:

```powershell
python -m pytest -v
```

Harness milestones:

```powershell
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile boundaries
python scripts/verification/harness.py --profile drift
```

Runtime milestone:

```powershell
python scripts/verification/harness.py --profile phase0
python scripts/verification/harness.py --profile phase1-slice
```

Full completion check:

```powershell
python scripts/verification/harness.py --profile all
```

If a change has not been verified through Godot runtime or editor inspection, describe it as written, wired, or static-only; do not describe it as runtime-complete.

## Definition Of Done

`Phase 0` is done only if all of these are true:

- backend tests pass
- Godot main scene opens and runs
- dialogue loop is observable
- one authoritative successful interaction is observable
- one authoritative failed interaction is observable
- one visible world-state change is observable
- one minimal Siming intervention is observable
- demo can be repeated from the harness/runbook

## Non-Goals

Do not expand this project into:

- full role cognition architecture
- full Siming brain
- full visual fact system rollout
- full event bus cluster implementation
- full evidence chain
- multi-scene story flow
- Phase 1 production architecture cleanup

If a request starts drifting there, narrow it back to the minimum demo loop.

## Reporting Contract

When reporting progress, separate:

- completed and verified
- completed but not Godot-verified
- blocked
- next step

Do not blur static file creation with runtime proof.
