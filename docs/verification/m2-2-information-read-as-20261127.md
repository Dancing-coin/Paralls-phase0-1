# M2-2 Information `read_as` Slice

## Commit and scope

- Code commit: `97c21f06b2e00e69926e6e77515aa967bae4c805`.
- The shared `GameplayReadAs` entry accepts registered Information report and report-knowledge FactTypes. Both declarations must be Information-owned, private, declare exactly `recipient_of(subject)`, and map to their registered event schema.
- The reader accepts only a character principal and the exact scope keys required by the requested FactTypes. Unknown FactTypes, unavailable readers, invalid declarations, and missing or extra scope keys are rejected.
- The two Information WebSocket reads now call this entry with the session-bound actor and server-authoritative world tick. The Information authority remains responsible for validating the recipient-private report/delivery/knowledge chain and its source revisions.
- This is a narrow Information-backed reader. Other selectors, generic selector qualification, runtime enforcement across all FactTypes, legacy domain-stream attribution, and the complete U7 contract remain open.

## Verification

- Python: `F:\codex-temp\thread-a-python312\Scripts\python.exe`, version `3.12.2`.
- SQLite: `3.43.1`.
- `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`.
- `app.__file__`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- Focused command covered `test_siege_information_runtime.py`, `test_information_replay_checkpoint.py`, `test_information_production_wiring.py`, `test_websocket_connection_context.py`, and `test_m6_5_siege_runtime.py`.
- Focused result: `81 passed, 6 warnings in 7.01s`, exit 0. Warnings are existing Starlette/httpx and FastAPI `on_event` deprecations.
- New registered selection `docs/verification/selection/m2-2-information-read-as.json`: `selected=3 problems=0 improvements=0`.
- Frozen selections: Ownership `24/0/0`, Modifier `12/0/0`, Equipment `87/0/0`, Inventory `56/0/0`, shared-replay `990/0/0`; total 1,169 selected nodes and zero problems or improvements.
- Raw focused log: `F:\paralls-verification\thread-a\m2-2-read-as-info-20261127-01\focused-final.log`.
- Raw selection outputs: `F:\paralls-verification\thread-a\m2-2-read-as-info-20261127-01\selection` and sibling directories `ownership`, `modifier`, `equipment`, `inventory`, and `shared-replay`.
- P-1 scan covered 306 added lines from the two commits in this increment. Assignment-shaped secret, AWS key, GitHub token, JWT, and private-key-header patterns each returned zero hits. Raw output: `F:\paralls-verification\thread-a\m2-2-read-as-info-20261127-01\p1-scan.log`.
- Pytest temporary files and the comparison runner's `TEMP`/`TMP` were on F:.

## Not covered

- The full backend suite was not run.
- This result does not close M2-2 or U7. Historical qualification for faction, role, group, owner, and holder selectors; broad FactType visibility execution; other Owner read paths; D6 workload evidence; and legacy stream attribution remain incomplete.
- Production dispatch, deployment configuration, live Unreal transport, and a full siege run were not tested by this increment.
- `integration` was not modified.

## Follow-up: reject unimplemented visibility models

- Code commit: `e941b91b` adds explicit rejection when a registered FactType declares a non-null `delay`, `delay_model`, `distortion`, or `distortion_model` that this reader does not execute.
- TDD red reproduced the defect: a registered Information report declaration with `distortion` returned a projection instead of raising. The test failed with `Failed: DID NOT RAISE` before the guard was added.
- Exact follow-up focused result: `81 passed, 6 warnings in 7.29s`, exit 0. The same Information selection returned `3/0/0`; frozen Ownership/Modifier/Equipment/Inventory/shared-replay selections returned `24/12/87/56/990`, all zero differences.
- Raw red output: `F:\paralls-verification\thread-a\m2-2-read-as-info-20261127-02\red.log`.
- Raw focused output and selection runs: `F:\paralls-verification\thread-a\m2-2-read-as-info-20261127-03\`.
- P-1 scan of the 27 added code lines in `e941b91b` returned zero hits across the five credential-pattern families. Raw output: `F:\paralls-verification\thread-a\m2-2-read-as-info-20261127-03\p1-e941.log`.
- The follow-up does not implement delay or distortion models. M2-2 remains blocked and the full backend suite was not run.

## Follow-up: explicit denial for `secret` and `debug_only`

- Code commit: `76a55dd2169b2834de9bbc53693f2a24bc3ea503` returns `read_as_visibility_forbidden` for registered `secret` and `debug_only` FactTypes. Both classes are denied before the Information reader is called.
- TDD red reproduced the prior generic error: the reader rejected both classes with `read_as_qualification_unavailable`, which did not identify a visibility denial. The updated test requires the explicit forbidden result for both classes.
- Exact follow-up focused result: `81 passed, 6 warnings in 6.55s`, exit 0. Information selection `3/0/0`; frozen Ownership/Modifier/Equipment/Inventory/shared-replay selections `24/12/87/56/990`, all zero differences.
- Python `3.12.2`, SQLite `3.43.1`, and A-worktree `app.__file__` were verified. Pytest temporary data and selection outputs are under `F:\paralls-verification\thread-a\m2-2-information-class-denial-20261127-02\`.
- This implements explicit denial in the supported read boundary; it does not add a privileged debug path or implement general selector qualification. M2-2 remains blocked and the full backend suite was not run.
- P-1 scan of the two commits since the previous A remote tip checked 42 added lines; assignment-shaped secret, AWS key, GitHub token, JWT, and private-key-header patterns each returned zero hits. Raw output: `F:\paralls-verification\thread-a\m2-2-information-class-denial-20261127-02\p1-branch-delta.log`.
