# AGENTS Operating Guide For Paralls Phase 0 Demo

This file governs the repository rooted at `D:\Users\User\Documents\paralls-phase-0-demo`.

Its purpose is to let coding agents execute the `Phase 0` validation demo without drifting into `Phase 1` system redesign.

## 1. Mission

This project is a runnable validation slice for 《开本 / Paralls》 `Phase 0`.

The goal is not to implement the full product.
The goal is to prove that the minimum dramatic runtime loop can run end-to-end inside a real Godot project plus a Python backend.

The minimum validated loop is:

1. one Godot 3D scene loads
2. two agent-driven character replicas exist
3. player can submit one structured dialogue input
4. backend returns one character dialogue response
5. voice playback or approved stub voice path is observable
6. one object interaction succeeds through backend authority
7. one interaction fails with a structured constraint result
8. one object or environment state visibly changes
9. one minimal Siming catalyst causes an observable reaction

## 2. Source Of Truth Hierarchy

When this project needs design truth, use this order:

1. explicit user instruction in the current thread
2. `D:\Projects\Paralls\docs\superpowers\plans\2026-05-31-phase0-demo-implementation-plan.md`
3. `D:\Projects\Paralls\docs\phase0\*.md`
4. `D:\Projects\Paralls\docs\phase1\core\00-总纲\Godot源码底层基础设施与运行时约束.md`
5. `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\*.md`

Do not invent a new architecture if those files already define the boundary.

## 2.1 Engineering Workflow Entry Points

For repository-local AI engineering workflow, use:

- `docs/INDEX.md`
- `docs/ai-engineering-workflow.md`
- `docs/harness.md`

Workflow continuity and evidence rules for this repository:

- Use Goal for active long-running execution continuity.
- Use Superpowers skills and native subagents when the task shape warrants them.
- Keep durable verification evidence under `.harness/verification/`.

For broad verification, run:

- `python scripts/verification/harness.py --profile all`

## 3. Core Boundary Rules

### 3.1 Godot

Godot is:
- local high-frequency embodiment host
- player input terminal
- local visible/audio presentation runtime

Godot is not:
- world-truth authority
- full character cognition host
- Siming host

### 3.2 Backend

The Python backend currently hosts:
- structured protocol contracts
- minimal session routing
- minimal character service
- minimal ESM authority
- minimal Siming catalyst
- event trace summary

### 3.3 Input Boundary

Cross-boundary input must be structured intent.
Do not send raw keyboard, mouse, or camera noise to the backend business layer.

### 3.4 World Truth Boundary

Object and environment changes must be driven by structured backend result objects.
Do not fake success purely in local scene presentation.

### 3.5 Siming Boundary

Siming may emit high-level catalyst outputs only.
It must not directly control low-level character motion or directly overwrite physical world truth.

### 3.6 Animation Boundary

Do not regress into external full-bone high-frequency remote driving.
Preserve the direction:
- local main track
- local refinement track
- backend sends semantic or structured results, not raw pose streams

## 4. Required Reading Before Major Work

Before changing behavior, read these files:

- `D:\Projects\Paralls\docs\superpowers\plans\2026-05-31-phase0-demo-implementation-plan.md`
- `D:\Projects\Paralls\docs\phase0\01-Phase0启动方案.md`
- `D:\Projects\Paralls\docs\phase0\02-Demo范围与验收标准.md`
- `D:\Projects\Paralls\docs\phase0\03-Demo联调清单.md`
- `D:\Projects\Paralls\docs\phase0\08-PlayerInput最小协议草案.md`
- `D:\Projects\Paralls\docs\phase0\09-AIOutput最小协议草案.md`
- `D:\Projects\Paralls\docs\phase0\10-ObjectEnvironmentResult最小协议草案.md`
- `D:\Projects\Paralls\docs\phase0\11-SimingMinimalOutput最小协议草案.md`
- `D:\Projects\Paralls\docs\phase0\12-最小具身表现集建议.md`
- `D:\Projects\Paralls\docs\phase0\12-ESM最小设计与Phase0落位.md`
- `D:\Projects\Paralls\docs\phase1\core\00-总纲\Godot源码底层基础设施与运行时约束.md`

## 5. Execution Order

Unless the user explicitly changes priority, use this order:

1. repair and stabilize Godot project structure
2. register autoloads and fix scene/script references
3. verify `MainDemo.tscn` opens and runs
4. rerun backend tests locally
5. start backend and connect Godot WebSocket path
6. prove dialogue loop
7. prove object interaction success and failure
8. prove environment or object visible state change
9. prove minimal Siming catalyst reaction
10. harden runbook and acceptance checklist

## 6. Godot MCP Policy

If Godot MCP is available in the session:
- use it for real scene inspection
- use it for node hierarchy validation
- use it for autoload verification
- use it for runtime checks and screenshots
- prefer real editor/runtime verification over static confidence

If a change has not been verified through Godot runtime or editor inspection, do not describe it as completed.
Describe it as:
- written
- wired
- unverified in editor
or
- static-only

## 7. Editing Rules

- Prefer small, targeted edits.
- Preserve the existing root Godot project instead of creating a second project.
- Keep new Phase 0 scenes under `scenes/phase0/` unless the user asks otherwise.
- Keep scripts under the existing `scripts/` tree.
- Keep backend code under `backend/`.
- Do not move design docs into this runtime project.
- Do not copy large chunks of documentation into code comments.

## 8. Verification Rules

Before claiming any milestone complete:

### Backend milestone
Run:
- `python -m pytest -v`

### Godot milestone
Verify at least one of:
- scene opens in editor without script/resource errors
- scene runs without immediate runtime errors
- target node exists in tree and receives the expected script/autoload link

### Integration milestone
Verify:
- backend is running
- Godot connects to backend
- one real message crosses the boundary
- one scene-visible result occurs from that message

## 9. Definition Of Done

`Phase 0` is done only if all of these are true:
- backend tests pass
- Godot main scene opens and runs
- dialogue loop is observable
- one authoritative successful interaction is observable
- one authoritative failed interaction is observable
- one visible world-state change is observable
- one minimal Siming intervention is observable
- demo can be repeated from the runbook

## 10. Non-Goals

Do not expand this project into:
- full role cognition architecture
- full Siming brain
- full visual fact system rollout
- full event bus cluster implementation
- full evidence chain
- multi-scene story flow
- Phase 1 production architecture cleanup

If a request starts drifting there, narrow it back to the minimum demo loop.

## 11. Reporting Contract

When reporting progress, separate:
- completed and verified
- completed but not Godot-verified
- blocked
- next step

Do not blur static file creation with runtime proof.
