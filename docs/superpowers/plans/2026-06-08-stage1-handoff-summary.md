# Stage 1 Handoff Summary

## What Stage 1 Completed

The current worktree now contains the completed Stage 1 architecture preparation layer:

- backend system-layer package skeletons:
  - `backend/app/l1`
  - `backend/app/l2`
  - `backend/app/l3`
  - `backend/app/l4`
  - `backend/app/l5`
  - `backend/app/l6`
- stable runtime contracts:
  - `backend/app/contracts/l1/*`
  - `backend/app/contracts/l2/*`
  - `backend/app/contracts/l6/*`
- merge-ready entrypoints and facades:
  - `app.l1.esm`
  - `app.l2.siming`
  - `app.l6.authority_bus`
  - `app.l6.perception_chain`
  - `app.l6.replay_audit`
  - `app.adapters.branch_merge.*`
- Godot-side architecture shell paths:
  - `scripts/l6/*`
  - `scripts/presentation/*`
- regression coverage:
  - `backend/tests/test_architecture_entrypoints.py`
  - authority-bus guardrail in `backend/tests/test_ws_protocol.py`

## Verification Evidence

Verified in the current worktree:

- from `backend/`: `python -m pytest -v`
  - result: `112 passed`
- from repo root:
  - `python scripts/verification/verify_phase0.py`
  - `python scripts/verification/verify_phase1_slice.py`
  - `python scripts/verification/verify_l1_runtime_edges.py`
  - all passed

## Important Runtime Note

Backend tests in this repo should be run from the `backend/` directory so the `app` package resolves correctly.

Reliable examples:

```bash
cd backend
python -m pytest -v
```

Repo-root invocations that directly point at `backend/tests/...` are not reliable in the current environment.

## What Did Not Happen Yet

Stage 1 did **not** do:

- full physical relocation of legacy implementation files
- merged enhanced `ESM`, `Siming`, or event-bus implementations
- downlink v0 implementation
- scene rewiring to the new shell script paths

The current structure is an interface-first preparation layer, not the final merged architecture.

## Where Incoming Enhanced Branches Should Land

When enhanced branches merge back, their preferred landing seams are:

- enhanced `ESM` -> `app.l1.esm`
- enhanced `Siming` -> `app.l2.siming`
- enhanced authority/event-bus logic -> `app.l6.authority_bus`

They should avoid extending the legacy flat service bucket any further unless the change is a temporary compatibility wrapper.

Use this merge procedure before starting Stage 2:

- [2026-06-08-enhanced-subsystems-merge-checklist.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/2026-06-08-enhanced-subsystems-merge-checklist.md>)

## What To Do Next

After enhanced `ESM`, `Siming`, and event-bus branches are merged:

1. execute the Stage 2 relocation plan:
   - [2026-06-08-stage2-merge-and-downlink-v0-implementation-plan.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/2026-06-08-stage2-merge-and-downlink-v0-implementation-plan.md>)
2. follow the merge checklist first:
   - [2026-06-08-enhanced-subsystems-merge-checklist.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/2026-06-08-enhanced-subsystems-merge-checklist.md>)
3. relocate merged implementations behind the Stage 1 seams
4. convert legacy flat modules into compatibility wrappers
5. start downlink v0:
   - `speak_to_actor`
   - `orient_to_target`
   - `inspect_object`

## Current Readiness Statement

The repo is now structurally ready for:

- enhanced branch reintegration,
- post-merge physical reorganization,
- and the first formal `L2 -> L1/ESM` downlink execution slice.

It is **not** yet running that downlink slice.
