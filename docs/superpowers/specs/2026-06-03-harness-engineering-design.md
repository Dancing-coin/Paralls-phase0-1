# Harness Engineering Design

## Status

- Date: `2026-06-03`
- Scope: `D:\Paralls-phase0-1`
- Purpose: make the Phase 0 demo easier for Codex and other agents to read, run, verify, and repair without expanding product scope.
- Decision mode: user-approved Harness Engineering adaptation.

## Problem

The project already has a useful agent-oriented base: `AGENTS.md`, Superpowers specs and plans, backend tests, Godot smoke verification, and verification artifacts. The remaining gap is that these pieces are not yet presented as one stable harness.

Agents can currently find the rules, but they must infer too much:

- which docs are the entry points
- which verification command proves which milestone
- which logs are durable evidence
- which boundary rules are mechanically enforced
- which checks are static-only versus runtime proof

## Design Goal

Turn the current demo into an agent-readable engineering harness where each large task can start from a small map, execute a known verification profile, and produce durable evidence.

The goal is not to implement full Phase 1. The goal is to make Phase 0 and the current Phase1-shaped slice repeatable under agent control.

## Chosen Approach

Use a narrow harness layer around the existing project instead of adding a new runtime architecture.

This design adds:

1. a repository docs index
2. a harness guide
3. a unified verification runner
4. a static boundary check entry point
5. versioned profile and rule registries
6. run-id evidence retention
7. baseline and previous-run diff artifacts
8. CI/release gate entry points
9. lifecycle artifacts adapted from `walkinglabs/learn-harness-engineering` Project 06
10. a versioned execution plan

## Architecture

### Repository Map

`AGENTS.md` remains the operating contract. `docs/INDEX.md` becomes the agent-readable map for project knowledge. It points to the active demo docs, harness docs, specs, plans, and reference material.

### Verification Harness

`scripts/verification/harness.py` becomes the stable command surface for agents. It delegates to existing verification scripts instead of duplicating their logic.

Profiles are declared under `.harness/profiles/`. The runner reads profile order, dispatch script, and Godot requirements from those manifests instead of hardcoding the project shape in Python. Rule manifests live under `.harness/rules/` so mechanical invariants can be reviewed as project-owned inputs.

Rule manifests are structured as rule-to-evidence maps. Each rule has a stable ID and points at the profile/check evidence that proves it. This keeps the harness readable by agents and reviewable by humans without parsing Python first.

Supported profiles:

- `docs`: documentation freshness and registry discoverability checks
- `boundaries`: static boundary checks through `check_boundaries.py`
- `drift`: local artifact, gitignore, and test coverage drift checks
- `backend-contract`: backend protocol model and websocket contract checks
- `godot-project`: static Godot main scene, autoload, and `res://` resource integrity checks
- `release-gate`: CI workflow and release gate metadata checks
- `harness-lifecycle`: feature ledger, local CI equivalence, clean-state checklist, retention policy, templates, quality docs, and handoff checks
- `phase0`: strict Phase 0 validation through `verify_phase0.py`
- `phase1-slice`: current Phase1-shaped runtime slice through `verify_phase1_slice.py`
- `all`: runs all profiles in order

Every run writes latest reports plus an archived copy under `.harness/verification/runs/<run-id>/`. The latest reports optimize local iteration; run-id archives preserve durable evidence for audit and regression comparison.

The harness also writes a latest run manifest, latest baseline, and latest previous-run diff under `.harness/verification/`. These are lightweight local evidence aids, not replacements for profile reports.

### Lifecycle Hardening

The lifecycle layer adapts the Project 06 solution pattern from `walkinglabs/learn-harness-engineering`. The transferable pieces are:

- feature/evidence ledger
- init or local CI-equivalent gate
- clean-state checklist
- session handoff
- quality document and evaluator rubric
- architecture and reliability docs
- benchmark/cleanup concepts

In Paralls, these become `.harness/features.json`, `.harness/ci/local-ci-gate.ps1`, `.harness/clean-state-checklist.md`, `.harness/session-handoff.md`, `.harness/quality-document.md`, `.harness/evaluator-rubric.md`, `docs/harness-architecture.md`, `docs/harness-reliability.md`, and profile-based evidence reports.

### Boundary Checks

`scripts/verification/check_boundaries.py` encodes the first set of agent-facing invariants:

- visual facts should use the approved emitter path
- websocket protocol should keep an explicit envelope model
- Phase 0 verification should produce JSON and Markdown reports
- the project should keep docs index and harness guide entry points

The check is intentionally static and narrow. Runtime proof stays in `phase0` and `phase1-slice`.

## Error Handling

The unified harness returns the first failing profile exit code. It prints the exact command and exit code for each profile so the next agent can resume from the failed layer.

Boundary checks emit JSON and Markdown reports under `.harness/verification/` and return non-zero when a required invariant is missing.

## Testing

Minimum verification for this design:

- `python scripts/verification/harness.py --profile docs`
- `python scripts/verification/harness.py --profile boundaries`
- `python scripts/verification/harness.py --profile drift`
- `python scripts/verification/harness.py --profile backend-contract`
- `python scripts/verification/harness.py --profile godot-project`
- `python scripts/verification/harness.py --profile release-gate`
- `python scripts/verification/harness.py --profile harness-lifecycle`
- `python scripts/verification/harness.py --profile phase0` when Godot is available
- `python scripts/verification/harness.py --profile phase1-slice` when Godot is available
- `python scripts/verification/harness.py --profile all` before claiming the full harness is green

## Non-Goals

- no full observability stack
- no new third-party dependencies
- no Phase 1 feature expansion
- no replacement of existing verification scripts
- no rewrite of Godot scenes or backend service logic

## Success Criteria

- agents have one docs map to start from
- agents have one command family for verification
- agents have versionable profile and rule registries instead of hidden profile order
- each run has a durable run-id evidence archive
- each run has a manifest, baseline, and diff for quick regression comparison
- CI has a project-owned release gate entry point
- lifecycle artifacts give agents a clean start, clean finish, feature ledger, quality rubric, and future-profile template path
- boundary assumptions begin moving from prose into executable checks
- existing Phase 0 verification remains the source of runtime truth
- generated evidence remains under `.harness/verification/`
