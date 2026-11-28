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

## Current A-tip recheck

- At A tip `a3e9bc3fcc3ee9aa6af17c99b635f86dc976a9c5`, Information replay/runtime/production-wiring focused tests returned `30 passed, 6 warnings`, exit 0.
- Command: `F:\codex-temp\thread-a-python312\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\information-replay-current-tip-20261127-01\temp\pytest backend/tests/test_information_replay_checkpoint.py backend/tests/test_siege_information_runtime.py backend/tests/test_information_production_wiring.py`.
- `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`; Python was `3.12.2`, SQLite `3.43.1`, and `PYTHONPATH`, `TEMP`, `TMP`, `TMPDIR`, `PYTHONPYCACHEPREFIX`, pytest basetemp, and outputs were on F:.
- The registered `siege_information` selection returned `selected=26 problems=0 improvements=0`. No frozen five-group selection was rerun in this check; the existing 1,169-node evidence above remains tied to the earlier A code tip.
- Raw output: `F:\paralls-verification\thread-a\information-replay-current-tip-20261127-01\pytest-information.log`, `selection-siege-information.log`, and `selection-siege-information\`.
- This was a recheck only. No code or integration branch changed. M2-2/U7 and M3-3 remain open as documented above.

## Current A-tip recheck at 9ee5c74a

- Python `3.12.2` from `F:\codex-temp\thread-a-python312\Scripts\python.exe`; SQLite `3.43.1`; `PYTHONPATH` and `app.__file__` resolved to the A worktree. `TEMP`, `TMP`, `TMPDIR`, Python bytecode cache and pytest basetemp were under `F:\paralls-verification\thread-a\a-continuation-20261127-02\`.
- Focused command covered `test_information_replay_checkpoint.py`, `test_siege_information_runtime.py`, `test_information_production_wiring.py`, and `test_m6_5_siege_runtime.py`; result `70 passed, 6 warnings`, exit 0.
- Current A code contains the B delivery changes. The Information knowledge event persists `event_time`, the durable checkpoint-tail test exists, and the registered selection includes the replay case. B's three source commits were not cherry-picked again because their code/test content was already present through A commits `07db5404` and `400d4ff9`; the selection update from `e185cfa8` was already equivalent on A.
- Current-tip selections: M3-3 Information knowledge `selected=1 problems=0 improvements=0`; `siege_information` `selected=26 problems=0 improvements=0`.
- Raw output: `F:\paralls-verification\thread-a\a-continuation-20261127-02\`. The frozen five selections and full backend suite were not rerun in this check.

## Current A-tip recheck at 66bb9116

- Fetched B tip `e185cfa8a97bac5c8336eff9d15fd7f7fac9f5d9`. The Information knowledge `event_time` writer, checkpoint-tail test, and selection are already present in A through `07db5404`, `400d4ff9`, and `0c3173f2`. No duplicate cherry-pick or B-branch merge was needed.
- At A HEAD `66bb91166871fb323197bf7a27016d73ddf1aa52`, focused Information replay/runtime/production-wiring tests returned `32 passed, 6 warnings`, exit 0. Python was `3.12.2`, SQLite was `3.43.1`, and `app.__file__` resolved under the A worktree.
- The registered `siege_information` selection returned `selected=26 problems=0 improvements=0`. Frozen selections returned Ownership `24/0/0`, Modifier `12/0/0`, Equipment `87/0/0`, Inventory `56/0/0`, and shared-replay `990/0/0` (`selected/problems/improvements`).
- Raw outputs are under `F:\paralls-verification\thread-a\information-b-delivery-current-20261128-01\`. The full backend suite was not run.
- Static boundary review identified `OrganizationAuthority.record_public_project_execution` in `organization_government_runtime.py` as a potential remaining custom retry path. `BOUNDARIES.md` lists that file as a shared fourth-wave ban, so it was not modified. The municipal certificate path in A-owned `ownership_runtime.py` already uses `replay_duplicate`. M3-3 remains in progress for other-owner and shared paths.
