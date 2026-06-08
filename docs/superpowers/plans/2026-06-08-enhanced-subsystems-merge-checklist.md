# Enhanced Subsystems Merge Checklist

## Purpose

This checklist is for the moment when the enhanced `ESM`, `Siming`, and event-bus branches are ready to merge back into `paralls-phase-0-demo`.

It assumes Stage 1 architecture preparation is already present in the target branch.

Use this checklist before starting Stage 2 physical relocation or downlink v0 work.

## Preconditions

Before merging any enhanced branch, verify:

- Stage 1 seam commit `d87c627` is present in the target branch
- the current worktree is clean except for intentionally unrelated files
- `backend/` tests still pass from the `backend/` directory
- the current verification scripts still pass from repo root

Recommended commands:

```bash
git log --oneline -1
cd backend
python -m pytest -v
cd ..
python scripts/verification/verify_phase0.py
python scripts/verification/verify_phase1_slice.py
python scripts/verification/verify_l1_runtime_edges.py
python scripts/verification/verify_enhanced_merge_preflight.py
```

## Merge Order

Merge in this order:

1. enhanced event-bus branch
2. enhanced `ESM` branch
3. enhanced `Siming` branch

Reason:

- the event-bus branch defines the message and routing shape the others must land on
- `ESM` and `Siming` can then be anchored behind those bus seams

## Files Most Likely To Conflict

### Event-bus enhanced branch

Expect merge pressure on:

- `backend/app/main.py`
- `backend/app/ws_protocol.py`
- `backend/app/debug_stream.py`
- `backend/app/verification_audit.py`
- `backend/app/services/candidate_percept_service.py`
- `backend/app/services/per_character_percept_filter.py`

Stage 1 landing seams for those changes:

- `backend/app/l6/authority_bus/*`
- `backend/app/l6/perception_chain/*`
- `backend/app/l6/replay_audit/*`
- `backend/app/contracts/l6/*`

### ESM enhanced branch

Expect merge pressure on:

- `backend/app/services/esm_service.py`
- `backend/app/models/world_result.py`
- any world-execution routing in `backend/app/main.py`

Stage 1 landing seams:

- `backend/app/l1/esm/*`
- `backend/app/contracts/l1/world_execution_result.py`

### Siming enhanced branch

Expect merge pressure on:

- `backend/app/services/siming_service.py`
- `backend/app/models/siming_output.py`
- any Siming-triggered routing inside `backend/app/main.py`

Stage 1 landing seams:

- `backend/app/l2/siming/*`
- `backend/app/contracts/l2/siming_message.py`

## Merge Rules

### Rule 1: Preserve Stage 1 Public Seams

Do not remove or rename these entrypoints during merge:

- `app.l1.esm.service.ESMServiceEntry`
- `app.l2.siming.service.SimingServiceEntry`
- `app.l6.authority_bus.router.handle_envelope_entry`
- `app.l6.perception_chain.candidate_compiler.compile_candidate_percepts_entry`
- `app.l6.perception_chain.per_character_filter.filter_candidate_for_actor_entry`
- `app.l6.replay_audit.verification_audit.VerificationAuditEntry`

If an enhanced branch already has a richer implementation, move or wrap it behind these names.

### Rule 2: Prefer Moving New Logic Behind Seams Over Extending Legacy Paths

When resolving conflicts, prefer:

- enhanced implementation behind `backend/app/l1`, `l2`, or `l6`

over:

- adding even more logic directly into `backend/app/services/*`

Legacy flat modules may remain as temporary compatibility wrappers, but they should not remain the long-term landing zone.

### Rule 3: Preserve Contracts Unless There Is A Strong Reason

Do not casually rename or reshape:

- `contracts/l1/action_request.py`
- `contracts/l1/presentation_command.py`
- `contracts/l1/execution_ack.py`
- `contracts/l1/world_execution_result.py`
- `contracts/l6/envelope.py`
- `contracts/l6/raw_fact.py`
- `contracts/l6/candidate_percept.py`
- `contracts/l6/character_perceived.py`

If an enhanced branch brings a different shape, reconcile it intentionally and update both:

- the Stage 2 plan
- the corresponding tests

### Rule 4: Do Not Rewire Godot Scenes During Merge

During the merge itself:

- keep `scenes/phase0/*.tscn` pointing at the current runtime script paths
- keep `scripts/l6/*` and `scripts/presentation/*` as shell surfaces

Actual scene rewiring belongs to Stage 2 after the enhanced implementations are stable in-tree.

## Post-Merge Immediate Verification

After each enhanced branch merge, run:

```bash
cd backend
python -m pytest -v tests/test_architecture_entrypoints.py
python -m pytest -v tests/test_ws_protocol.py::test_authority_bus_router_entrypoint_matches_legacy_behavior
```

Expected:

- both pass after every branch merge

After all three enhanced branches are merged, run:

```bash
cd backend
python -m pytest -v
cd ..
python scripts/verification/verify_phase0.py
python scripts/verification/verify_phase1_slice.py
python scripts/verification/verify_l1_runtime_edges.py
```

Expected:

- all pass before Stage 2 starts

## Fast Preflight Command

For a compressed merge gate, run:

```bash
python scripts/verification/verify_enhanced_merge_preflight.py
```

Then read:

- `.omx/verification/enhanced-merge-preflight-report.md`

## Decision Gate Before Stage 2

Do not begin Stage 2 physical relocation until all of the following are true:

- all three enhanced branches are merged
- Stage 1 seam tests still pass
- full backend suite passes
- existing verification scripts pass
- no temporary merge conflict markers or duplicated compatibility paths remain unresolved

## Handoff To Stage 2

Once the merge gate is green:

1. execute:
   - [2026-06-08-stage2-merge-and-downlink-v0-implementation-plan.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/2026-06-08-stage2-merge-and-downlink-v0-implementation-plan.md>)
2. relocate merged implementations into:
   - `backend/app/l1/*`
   - `backend/app/l2/*`
   - `backend/app/l6/*`
3. reduce legacy flat modules to compatibility wrappers
4. then start downlink v0

## One-Sentence Summary

Merge enhanced logic into the Stage 1 seams first, prove the seams still work, and only then start physical relocation and downlink execution work.
