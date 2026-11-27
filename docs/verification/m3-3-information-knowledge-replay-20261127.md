# M3-3 Information knowledge replay validation

## Scope

- A implementation commit: `33a1c38ac8f209721f57195955a5391d3ff7ccda` validates the durable Information knowledge-update transaction and committed event receipt through `replay_duplicate` before returning a duplicate result.
- B delivery selectively applied to A: `a61c93ad` persists the existing top-level `event_time` on the knowledge event; `a1719826` adds durable checkpoint-plus-tail replay coverage and its evidence. The B selection update in `e185cfa8` was already present on A and produced an empty cherry-pick, so no duplicate commit was created.
- A-local cherry-pick commits: `07db5404` and `400d4ff9`. The B commits were not merged as a branch, and `integration` was not changed.

## Verification

- Environment: Python `3.12.2` from `F:\codex-temp\thread-a-python312\Scripts\python.exe`; SQLite `3.43.1`; `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`; `app.__file__` resolved to the A worktree. `TEMP`, `TMP`, `PYTHONPYCACHEPREFIX`, and pytest `--basetemp` all pointed to the unique F-drive run directory.
- Focused command: `python -m pytest -q -p no:cacheprovider --basetemp=F:\paralls-verification\thread-a\information-b-replay-a-tip-20261127-01\pytest-temp backend\tests\test_siege_information_runtime.py backend\tests\test_m6_5_siege_runtime.py backend\tests\test_information_replay_checkpoint.py`.
- Focused result: `53 passed, 6 warnings`, exit 0.
- M3-3 knowledge replay: `selected=1 problems=0 improvements=0`.
- B `siege_information`: `selected=26 problems=0 improvements=0`.
- M6-5 Information report source: `selected=25 problems=0 improvements=0`.
- Frozen selections: Ownership `24`, Modifier `12`, Equipment `87`, Inventory `56`, shared-replay `990`; all `problems=0 improvements=0`, total `1,169` selected nodes.
- Raw logs and batch results: `F:\paralls-verification\thread-a\information-b-replay-a-tip-20261127-01\`.

## Remaining

- M3-3 remains in progress because other direct/custom replay paths still need inventory and validation.
- M6-5 remains in progress. Production Gate values are still unconfigured. `.env.example` contains demonstration values only. No deployment target, live Unreal transport, complete siege execution, or full backend suite was verified. `deadline_world_tick` remains unknown.
- No changes were made to `integration`.
