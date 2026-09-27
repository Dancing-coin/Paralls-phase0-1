# Task 7 report — L4 execution-contract convergence

## Scope

Implemented the single production-shaped `CharacterExecutionContract` and
threaded it through canonical runtime execution while retaining
`CharacterGoalCommand` only as compatibility metadata/input. No new transport,
store, authority, body-pose, VLA, or world-write path was added.

## Changes

- Added immutable/validated `CharacterExecutionContract` with canonical turn,
  actor/source/target identity, semantic intent/action, advisory realization
  hints, revision pins, idempotency, causation/correlation, privacy/authority
  scope, and expected observation.
- Added recursive rejection of transform/velocity/pose/animation/impulse/
  damage/status/inventory/world-write/VLA payload fields.
- Added `CharacterAgentL4Executor.build_execution_contract(...)` and kept
  skill/settlement realization metadata advisory.
- Added one-way `CharacterAgentL4Adapter.from_legacy_command(...)` with a
  turn-keyed duplicate/conflict guard and `LegacyExecutionTranslation` result.
- Canonical runtime execution records the contract in the existing execution
  request payload; legacy commands carry only turn/idempotency compatibility
  pins for existing observers.

## Verification

```text
python -m pytest backend/tests/test_character_execution_contract.py backend/tests/test_character_agent_l4_execution.py backend/tests/test_character_agent_goal_command_runtime.py -v
19 passed

python -m compileall -q backend/app/character_agent
passed

git diff --check
passed
```

## Notes

The working tree contains pre-existing user/other-thread changes. Only the
Task 7-owned files should be staged for the implementation commit.

---

## Fix round 1 — canonical egress convergence

### Changed files

- `backend/app/main.py`
- `backend/app/character_agent/models/character_execution.py`
- `backend/app/character_agent/execution/l4_executor.py`
- `backend/app/character_agent/execution/l4_adapter.py`
- `backend/app/character_agent/runtime/runtime_loop.py`
- `backend/tests/test_character_execution_contract.py`

### Requirements addressed

- Production `character_agent_execution` egress now accepts and emits a
  top-level validated `CharacterExecutionContract`; the envelope builder no
  longer manufactures a legacy execution payload for commands without the
  canonical contract.
- The authority projection derives one semantic action from the contract and
  carries its exact turn, idempotency, causation/correlation, and all revision
  pins. Request identity is `${idempotency_key}:0`, independent of producer
  timestamp; the egress handler does not record a duplicate execution request.
- Runtime contract augmentation now uses JSON-normalized data followed by
  `CharacterExecutionContract.model_validate(...)`; no unsafe
  `model_copy(update=...)` remains on that path.
- Skill realization metadata excludes settlement outcomes/results. Frozen map
  serializers now apply to normal `model_dump()` as well as JSON output.
- Regressions cover canonical egress pins, unsafe nested `global_position`,
  normal dump warnings/proxies, ingress rejection, and settlement metadata
  exclusion.

### Verification

```text
python -m pytest backend/tests/test_character_execution_contract.py backend/tests/test_character_agent_l4_execution.py backend/tests/test_character_agent_goal_command_runtime.py -v
22 passed (FastAPI startup/shutdown deprecation warnings only)

python -m compileall -q backend/app/character_agent
passed

git diff --check
passed
```

### Residual risks

- The repository-wide `python -m pytest -q` was started but not allowed to
  complete within this fix run; pre-existing tests that inject legacy
  plan-shaped `character_agent_execution` envelopes will need migration to the
  canonical contract ingress.
- No Godot editor/runtime check was applicable because this fix is backend-only.

### Commit

Implementation commit: `79db55b486a6edba55228f09668a05fce01d9305`

---

## Fix round 2 — authority settlement pin continuity

### Changed files

- `backend/app/character_agent/models/character_execution.py`
- `backend/app/character_agent/execution/l4_executor.py`
- `backend/app/character_agent/execution/l4_adapter.py`
- `backend/app/contracts/l1/action_request.py`
- `backend/app/models/world_result.py`
- `backend/app/models/ai_output.py`
- `backend/app/services/esm_service.py`
- `backend/app/main.py`
- `backend/tests/test_character_execution_contract.py`

### Requirements addressed

- The execution contract now carries the canonical turn producer timestamp;
  its action requests and resulting social, dialogue, and ESM settlements no
  longer reconstruct identity from `producer_ts=0`.
- Social-space settlements now use the contract-derived request/result identity
  and preserve turn, idempotency, revision pins, and causation/correlation.
- ESM receives the already-pinned `ActionRequest` rather than rebuilding one
  from an `InteractIntent`. It preserves those pins on both accepted and
  rejected results and replays a matching canonical interaction idempotently.
- Dialogue response settlement carries the same request identity and contract
  pins.
- Added integration regressions for social-space, ESM interact, and dialogue
  settlement results, including same-identity replay assertions.

### Verification

```text
python -m pytest backend/tests/test_character_execution_contract.py backend/tests/test_character_agent_l4_execution.py backend/tests/test_character_agent_goal_command_runtime.py -v
25 passed (FastAPI startup/shutdown deprecation warnings only)

python -m compileall -q backend/app/character_agent backend/app/services
passed

git diff --check
passed
```

### Commit

Implementation commit: `265c265857a1e448341906fca86adfe7bdcbfdfc`
