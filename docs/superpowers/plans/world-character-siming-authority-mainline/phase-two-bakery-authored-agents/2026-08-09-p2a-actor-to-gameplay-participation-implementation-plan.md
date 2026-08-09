# P2A Actor-to-Gameplay Participation Implementation Plan

Status: `implemented-and-verified; closed`

## Goal and dependency gate

Prove an existing profile-backed actor can emit a typed work intent without obtaining a Gameplay
store writer. Do not begin until `python scripts/verification/harness.py --profile phase1d-econ1-bakery`
is fresh-green and the P1B/P1C/Econ-1 predecessor reports are present.

## Exact files and order

1. Add `backend/tests/test_phase2a_actor_to_gameplay_participation.py` for registry lookup, package allowlist,
   actor-scoped projection, adapter no-store dependency, envelope versions and intent rejection.
2. Extend `backend/app/character_agent/execution/l4_adapter.py` with envelope-only work-intent
   output; extend `backend/app/character_agent/profile/registry.py` and `views.py` only for lookup
   and filtered input; do not add a writer.
3. Extend `backend/app/gameplay/shared_contracts.py` for the accepted envelope/reference fields and
   `backend/app/gameplay/event_schema_registry.py` for registered event versions; package input is
   the existing `GameplayPackageManifest`, not a new registry.
4. Add scope/replay assertions to `backend/tests/test_gameplay_shared_replay_and_permission.py`
   and `backend/tests/test_godot_gameplay_mirror_projection.py`.
5. Implemented profile/verifier: `.harness/profiles/phase2a-actor-to-gameplay-participation.json`,
   `scripts/verification/verify_phase2a_actor_to_gameplay_participation.py`, and their reports under
   `.harness/verification/`.

## Contract tests first

Cover valid refs, unknown/synthetic refs, package denial, `respond_shift`, `start_work`,
`finish_work`, `report_absence`, `request_break`, duplicate idempotency, payload mismatch, stale
expected revision, causation/correlation propagation, pinned revisions, and zero events on reject.

## Verification commands

```powershell
python -m pytest -q backend/tests/test_character_agent_l4_execution.py backend/tests/test_character_agent_boundary_audit.py backend/tests/test_gameplay_shared_contracts.py backend/tests/test_gameplay_event_store_contract.py backend/tests/test_gameplay_event_replay.py backend/tests/test_gameplay_shared_replay_and_permission.py
python scripts/verification/harness.py --profile phase1d-econ1-bakery
python scripts/verification/harness.py --profile phase2a-actor-to-gameplay-participation
python scripts/verification/harness.py --profile docs
```

## Stop conditions

Verification: focused P2A tests and Harness are fresh-green; P2B started only after this gate.
No CharacterAgent `append_batch`, new event store/bus/scheduler, profile mutation, or unlisted
projection owner was introduced.
