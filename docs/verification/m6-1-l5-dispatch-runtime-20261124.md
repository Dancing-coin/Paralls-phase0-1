# M6-1 committed reaction dispatch component

- Implementation commits: `dabb7f4e0756d8bdfa61207ad808e98055623978` adds the dispatcher, and `90af2255749871fa78b063b1070592aa9f8ec232` rejects wildcard FactTypes in trusted outputs.
- Verified code SHA: `90af2255749871fa78b063b1070592aa9f8ec232`.
- Worktree: `F:\codex-temp\paralls-v2-thread-a-bond-20261121`, branch `thread-a/ownership-bond-followup-20261121`.
- Python: `D:\Temp\paralls-g0-py312\Scripts\python.exe`, version `3.12.2`.
- `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`; `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- `TEMP`, `TMP`, pytest basetemp and verification output were directed to `F:\paralls-verification\thread-a\m6-5-l5-gateway-20261124-01\`.

## Behavior

`L5ReactionDispatcher.after_transaction_dispatched` consumes the committed `AtomicEventBatch` callback contract already used by `GameplayOutboxDispatcher`. It matches the compiled reaction's FactType pattern and event type or transition, then submits a stable `l5:<reaction>:<event>` command through `TrustedGameplayCommandGateway`. Repeated delivery of the same transaction produces the same command and idempotency key. Command handlers and their explicit output FactTypes must be registered as an exact pair. A referenced condition without a registered resolver is rejected at dispatcher construction. L5 has no EventStore dependency and appends no Owner facts.

This is an L5 dispatch component. It is not yet registered in production `main.py` or loaded from an M6-5 rule package. No Morale or Presence command handler is registered by this unit. M6-5 production dispatch remains incomplete pending the authoritative gate-impact and Presence assessment input contract.

## Verification

| Check | Result |
|---|---|
| Focused and adjacent tests | `python -m pytest -q backend/tests/test_l5_dispatch_runtime.py backend/tests/test_l5_reaction.py backend/tests/test_l5_workflow.py backend/tests/test_l5_play_pattern.py backend/tests/test_rule_pack_validator.py backend/tests/test_gameplay_event_schema_registry.py` — 148 passed, 2 deprecation warnings |
| New permanent unit selection | `selected=5 problems=0 improvements=0` |
| Frozen `equipment` | `selected=87 problems=0 improvements=0` |
| Frozen `inventory` | `selected=56 problems=0 improvements=0` |
| Frozen `modifier` | `selected=12 problems=0 improvements=0` |
| Frozen `ownership` | `selected=24 problems=0 improvements=0` |
| Frozen `shared-replay` | `selected=990 problems=2 improvements=0`; the two failures are embodied interaction runner tests blocked by an external unhealthy listener on Port 8000 |
| All registered selections | 19 selections, 141 selected nodes, `problems=0 improvements=0` |
| Full suite after this component | Not run |

The frozen run and every registered selection were run with `docs/verification/absorb-main-3bf3418e/compare_selection.py` against `90af2255`. Raw output is under `F:\paralls-verification\thread-a\m6-5-l5-gateway-20261124-02\`. The two shared-replay failures also appear in the Presence component evidence and reproduce at its parent SHA `5d7cc0da`; this unit did not stop or modify the external process.

## Migration DoD status for this mechanism unit

| DoD | Status |
|---|---|
| U1 Owner declaration and classification | Not applicable to the dispatch mechanism; it creates no Owner. |
| U2 FactType declaration | Not applicable to the dispatch mechanism; it declares no domain FactType. |
| U3 Event schema and P-3 | Not applicable; no event type was added. |
| U4 Shared mechanism | Partially verified; it implements the existing post-dispatch callback shape and does not write Owner facts. |
| U5 R1/R2/R3 | Not verified; downstream durable command receipts and restart recovery are not wired by this unit. |
| U6 Reader inventory and tests | Partially verified; registered command handlers are the dispatch targets, while production Morale/Presence handlers remain unregistered. |
| U7 Read classification and visibility | Not applicable; the component performs no FactType reads. |
| U8 Rule-pack settings and Resolver registration | Partially verified; compiled reactions consume an explicit output map and conditions fail closed, while production rule-pack registration remains absent. |
| U9 Probe and frozen baseline | Partially verified; all registered selections are zero-difference, frozen shared-replay has two external Port 8000 failures, full suite not run. |
| U10 Changed files and verification levels | Recorded in the implementation commit and this evidence. |
| U11 Permanent unit selection | Verified; `docs/verification/selection/m6-1-l5-dispatch-runtime.json`, `selected=5 problems=0 improvements=0`. |

This does not complete M6-1 production wiring, M6-5, or Architecture v2 migration.
