# Enhanced Subsystems Conflict Preflight

## Purpose

This is a short preflight sheet to use immediately before merging the enhanced:

- event-bus branch
- `ESM` branch
- `Siming` branch

It complements the fuller checklist here:

- [2026-06-08-enhanced-subsystems-merge-checklist.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/2026-06-08-enhanced-subsystems-merge-checklist.md>)

Use this page when you want the minimum set of files and commands likely to matter during conflict resolution.

## Merge Order

Apply merges in this order:

1. event-bus
2. `ESM`
3. `Siming`

## First Commands

Run before the first merge:

```bash
git status --short
git log --oneline -2
cd backend
python -m pytest -v tests/test_architecture_entrypoints.py
python -m pytest -v tests/test_ws_protocol.py::test_authority_bus_router_entrypoint_matches_legacy_behavior
cd ..
```

You want:

- clean worktree except intentionally unrelated files
- Stage 1 seam commit present
- seam tests green

## Highest-Risk Legacy Files

If the enhanced branches changed any of these, expect conflicts or integration decisions:

- `backend/app/main.py`
- `backend/app/ws_protocol.py`
- `backend/app/debug_stream.py`
- `backend/app/verification_audit.py`
- `backend/app/services/esm_service.py`
- `backend/app/services/siming_service.py`
- `backend/app/services/candidate_percept_service.py`
- `backend/app/services/per_character_percept_filter.py`

## Stage 1 Landing Seams

When resolving those conflicts, prefer landing merged logic here:

- event-bus logic:
  - `backend/app/l6/authority_bus/*`
  - `backend/app/l6/perception_chain/*`
  - `backend/app/l6/replay_audit/*`
- `ESM` logic:
  - `backend/app/l1/esm/*`
- `Siming` logic:
  - `backend/app/l2/siming/*`

## Public Seams That Must Survive Merge

Do not break or rename these:

- `app.l1.esm.service.ESMServiceEntry`
- `app.l2.siming.service.SimingServiceEntry`
- `app.l6.authority_bus.router.handle_envelope_entry`
- `app.l6.perception_chain.candidate_compiler.compile_candidate_percepts_entry`
- `app.l6.perception_chain.per_character_filter.filter_candidate_for_actor_entry`
- `app.l6.replay_audit.verification_audit.VerificationAuditEntry`

## Godot Rule

Do not rewire `scenes/phase0/*.tscn` during merge resolution.

Keep:

- `scripts/l6/*`
- `scripts/presentation/*`

as shell surfaces until Stage 2 physical relocation begins.

## After Each Merge

Run:

```bash
cd backend
python -m pytest -v tests/test_architecture_entrypoints.py
python -m pytest -v tests/test_ws_protocol.py::test_authority_bus_router_entrypoint_matches_legacy_behavior
cd ..
```

## After All Three Merges

Run:

```bash
cd backend
python -m pytest -v
cd ..
python scripts/verification/verify_phase0.py
python scripts/verification/verify_phase1_slice.py
python scripts/verification/verify_l1_runtime_edges.py
```

Only start Stage 2 after those are green.
