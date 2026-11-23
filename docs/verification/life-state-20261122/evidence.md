# LifeState Migration Evidence

- Baseline: `94d4aa20c3093904bb5ac1daa2af4f93c6981677` (`integration-2026-11-22-8`).
- Scan and verification: `rg` source/readers; Python `D:\Temp\paralls-g0-py312\Scripts\python.exe`; focused pytest covering LifeState, population admission, and application checkpoint paths.
- Verification time: 2026-11-22 Asia/Shanghai.
- Conclusion: partial migration evidence; this is not an Architecture v2 acceptance declaration.

## U1–U11

| Item | Status | Evidence or remaining work |
|---|---|---|
| U1 Owner declaration and classification | Partial | `LifeState` is in `REGISTERED_OWNER_IDS` (`backend/app/gameplay/fact_type_registry.py:11-35`); Architecture v2 classifies it stewarded (`04-Owner/01-Owner定义.md:17,46`). Current source-validation adapter remains. |
| U2 FactType declaration | Done for candidate data | `packs/life_state/fact_types/life_state.yaml` and `machine_defs/life_state.yaml`; loader test verifies Owner, primitive, and visibility class. |
| U3 Event schema and P-3 | Verified | Existing schema registration `backend/app/gameplay/event_schema_registry.py:190-194`; test writes an actual death event, dispatches its persisted outbox, publishes the registered event type, and asserts graph domain `character`. Membership alone is not the evidence. |
| U4 Shared Owner mechanics | Partial | Uses `rejected_result` and existing `build_atomic_event_batch` (`backend/app/gameplay/life_state_runtime.py:11-12,303-310`). Specialized receipt validation remains to verify transaction/event/revision/sequence and preserve schema-v1 semantics (`:236-291`); generic `replay_duplicate` does not preserve these checks. |
| U5 R1/R2/R3 | Verified by focused tests | Durable receipt reopen and historical replay in `test_life_state_case_death_caller.py`; full rebuild and checkpoint-tail cases in `test_life_state_replay_participant.py`; application durable checkpoint path in `test_world_replay_checkpoint_application.py`. |
| U6 Reader list and focused tests | Static inventory plus focused tests | See `design.md` reader table. This is not a full caller authorization classification. |
| U7 Visibility | Not done; deviation recorded | Candidate FactType says `private`; current persisted event says `project`. Audience selectors and production `read_as` are not available in the current loader. |
| U8 Pack and Resolver | Partial | Pack registers a pure transition-table evaluator and test loads/evaluates it. Production runtime does not yet route decisions through the loaded pack resolver. |
| U9 Probe and baseline comparison | Verified for the recorded selection depth | Real writer-to-projector P-3 test and focused tests pass. Five frozen comparisons and the unit comparison report zero problems. This does not cover unselected tests. |
| U10 File inventory and evidence status | Done | Changed files listed below with verification classification. |
| U11 Unit selection | Registered and compared | `docs/verification/selection/life_state.json`; 12 registered nodes, `problems=0`. |

## Verification

Python check output:

```text
3.12.2 (tags/v3.12.2:6abddd9, Feb  6 2024, 21:26:36) [MSC v.1937 64 bit (AMD64)]
F:\codex-temp\paralls-v2-thread-b-life-state-20261122\backend\app\__init__.py
```

Baseline focused selection:

```text
62 passed, 1 xfailed, 6 warnings in 26.45s
```

P-3 red test before the outbox change:

```text
assert dispatched.published_count == 1
E assert 0 == 1
1 failed, 2 warnings in 0.35s
```

Focused verification after changes:

```text
64 passed, 1 xfailed, 6 warnings in 25.06s
```

Final focused command repeated after the last source edit; its unit-selection and secret-scan outputs were:

```text
selected=12 problems=0 improvements=0
tracked_model_secret_offender_count=0
harness_cleanup=passed run_id=6c55bd8858bc4aa6b885264ee5ff7538
```

Selection comparisons:

```text
life_state: selected=12 problems=0 improvements=0
ownership: selected=24 problems=0 improvements=0
modifier: selected=12 problems=0 improvements=0
equipment: selected=87 problems=0 improvements=0
inventory: selected=56 problems=0 improvements=0
shared-replay: selected=990 problems=0 improvements=0
tracked_model_secret_offender_count=0
```

Logs are in `F:\paralls-verification\thread-b\life-state-baseline-20261122\`, `life-state-focused-20261122\`, `life-state-p3-red-20261122\`, `life-state-p3-green-20261122\`, `life-state-gates-2-20261122\`, `life-state-frozen-20261122\`, `life-state-g6-20261122\`, and `life-state-final-20261122\`. The first LifeState selection attempt found a parameterized node ID mismatch; it was corrected to the concrete `[transaction]` case and the comparison reran with zero problems.

## Changed files

| File | Status |
|---|---|
| `backend/app/gameplay/life_state_runtime.py` | Implemented; focused tests pass |
| `backend/tests/test_life_state_case_death_caller.py` | Implemented; focused tests pass |
| `backend/tests/test_population_activation_presence_service.py` | Implemented; focused tests pass |
| `backend/tests/test_life_state_rule_pack.py` | Implemented; focused tests pass |
| `packs/life_state/pack.yaml` | Static data; loader test passes |
| `packs/life_state/fact_types/life_state.yaml` | Static data; loader test passes |
| `packs/life_state/machine_defs/life_state.yaml` | Static data; loader test passes |
| `packs/life_state/models/life_state_transition.yaml` | Static data; loader test passes |
| `docs/verification/life-state-20261122/design.md` | Static design and reader inventory |
| `docs/verification/selection/life_state.json` | Registered; 12 selected nodes, zero problems |

No event name, schema version, payload semantics, shared registry, event store, or main entry point changed. No full pytest run was performed. No migration completion or v2 acceptance is claimed.
