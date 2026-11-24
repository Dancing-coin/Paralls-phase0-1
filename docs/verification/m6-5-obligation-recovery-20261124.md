# M6-5 durable siege input obligation recovery

## Implementation slice

- Commit: `102e4380f2bbc3e85700e4332bfeae1ea01d69f3`.
- The runtime rebuilds outstanding Facility and Presence work from durable, signed input events. It asks each existing Owner to consume the input using its stable idempotency key and treats the Owner receipt as the completion evidence. It adds no workflow-state stream or duplicate domain ledger.
- Application startup invokes recovery after the durable Gameplay store and M6-5 Owner authorities are assembled. Missing Facility content configuration leaves impact evidence pending without writing a Facility fact.

## Verification

- Detached worktree: `F:/codex-temp/a-m6-5-obligation-verify-102e4380/` at the exact implementation commit.
- Environment: Python `3.12.2`, SQLite `3.43.1`, `PYTHONPATH=F:/codex-temp/a-m6-5-obligation-verify-102e4380/backend`; `app.__file__` resolved under that worktree.
- Focused command: `python -m pytest -q -p no:cacheprovider --basetemp <F-drive-run>/pytest-tmp backend/tests/test_m6_5_siege_runtime.py backend/tests/test_siege_physical_input_runtime.py backend/tests/test_place_passability_runtime.py backend/tests/test_facility_integrity_runtime.py`.
- Focused result: **26 passed, 6 deprecation warnings**.
- Permanent M6-5 selection: `selected=6 problems=0 improvements=0`.
- Frozen ownership selection: `selected=24 problems=0 improvements=0`.
- Frozen shared-replay selection: `selected=990 problems=2 improvements=0`. The two failures were `tests/test_embodied_interaction_session_runner.py::test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage]` and `[wall-clock]`. Both require Port 8000, occupied by an external process without a healthy backend. The same two nodes failed on parent `8227e94c`, with raw output at `F:/paralls-verification/thread-a/m6-5-obligation-parent-two-node-8227e94c/`.
- Raw slice output, including each frozen-selection batch, is at `F:/paralls-verification/thread-a/m6-5-obligation-verify-102e4380/`.
- Full suite: not run.

## Scope and remaining work

- Verified by component tests: Facility and Presence input recovery from persisted signed evidence, replay of the same Owner receipt on repeated recovery, and no duplicate Owner fact.
- Not verified: a crash/restart against a real durable database file, actual UE transport, production Gate content values, or a full configured siege playthrough.
- The four-layer profile still lacks authoritative gate-leaf and latch inputs. This slice only recovers the existing Facility integrity and independent Presence assessment stages. M6-5 remains incomplete.
