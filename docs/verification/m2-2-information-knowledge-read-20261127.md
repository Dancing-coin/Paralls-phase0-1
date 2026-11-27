# M2-2 Information Knowledge Recipient Read

## Scope

Commit `ebb28f737840f5786c3c5789d68d7c5458f57847` adds `information_knowledge_read` for the existing Information `report_knowledge` FactType. The request identifies the report publication event. The backend requires an active bound WebSocket actor, membership in the session's `allowed_actor_refs`, and an `as_of_tick` no later than the server world clock.

The Information reader checks the report's existing recipient-private read path, the durable knowledge transaction, its report and delivery revision pins, delivery transaction, actor visibility and event/known times. Missing or inconsistent evidence returns unavailable. This does not implement generic `read_as`, historical selector qualification, FactType-wide visibility enforcement, or U7.

## Verification

- Python: `F:\codex-temp\thread-a-python312\Scripts\python.exe`, version `3.12.2`.
- `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`.
- `app.__file__`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- Exact-tip command: `python -m pytest backend/tests/test_siege_information_runtime.py backend/tests/test_information_replay_checkpoint.py backend/tests/test_information_production_wiring.py backend/tests/test_websocket_connection_context.py --basetemp F:\paralls-verification\thread-a\m2-2-information-knowledge-read-20261127-04\pytest-tmp -p no:cacheprovider -q`.
- Exact-tip result: `42 passed, 6 warnings`.
- Frozen comparison command: `python docs/verification/absorb-main-3bf3418e/compare_selection.py --repo F:\codex-temp\paralls-v2-thread-a-bond-20261121 --selection docs/verification/selection/m2-2-information-report-read.json --output F:\paralls-verification\thread-a\m2-2-information-knowledge-read-20261127-04\selection`.
- Frozen comparison result: `selected=5 problems=0 improvements=0`.
- Frozen regression selections: Ownership `24/0/0`, Modifier `12/0/0`, Equipment `87/0/0`, Inventory `56/0/0`, and shared-replay `990/0/0`; total `1,169` nodes with zero problems or improvements. Raw outputs are under `F:\paralls-verification\thread-a\m2-2-information-knowledge-read-20261127-05\`.
- Test-first check before implementation failed as expected: the runtime reader did not exist and the new WebSocket message was unavailable. Its raw output is `F:\paralls-verification\thread-a\m2-2-information-knowledge-read-20261127-01\red.log`.
- Exact-tip raw outputs are `F:\paralls-verification\thread-a\m2-2-information-knowledge-read-20261127-04\focused.log` and `selection.log`. Temporary files and pytest basetemp were placed on F:.

## Not Covered

The full backend suite was not run for this increment. The selection covers the five previously registered report-read nodes and does not convert this result into a full U7 or M2-2 pass. Faction, role, group, holder and owner selectors remain unsupported because their historical qualification sources are not available in the current read contract. Generic FactType visibility execution and legacy domain-stream attribution remain open.
