# M3-1 OwnerCommitBuilder current-tip verification

Implementation remains in `backend/app/gameplay/owner_runtime_base.py`; Ownership and Credential use the shared builder while retaining caller-owned result digests, revision maps, and idempotency-key shapes.

## Current tip

- Commit: `022f774d07fbbadc262a0a410738988fc9a780cb`
- Python: `D:\Temp\paralls-g0-py312\Scripts\python.exe`, version 3.12.2
- `PYTHONPATH`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`
- Raw output: `F:\paralls-verification\thread-a\m3-1-current-20261126\`
- Temporary and pytest directories were under the same F-drive run root.

## Results

| Check | Result |
|---|---|
| `test_owner_commit_builder.py`, `test_ownership_runtime.py`, `test_credential_runtime.py` | `23 passed, 2 warnings`, exit 0 |
| Frozen ownership selection | `selected=24 problems=0 improvements=0` |
| Frozen shared-replay selection | `selected=990 problems=0 improvements=0` |
| Current-tip full backend suite | Not run |

The shared-replay run used the existing F-drive listener-query shim only for the local port check. No process was stopped. This evidence verifies the current-tip shared mechanism and regression selections. It does not change the M3-1 scope or claim Architecture v2 completion.

## U1-U10

| DoD | Status |
|---|---|
| U1-U3 | Not applicable to this shared mechanism unit |
| U4 | Verified for Ownership and Credential callers |
| U5-U8 | Not done, outside this unit |
| U9 | Verified at current tip with focused tests and two frozen selections; current-tip full suite not run |
| U10 | Verified by this evidence and raw outputs |
| U11 | Existing M3-1 selection remains registered; this is a current-tip verification addendum |

## Current-tip revalidation, 2026-11-27

- Exact A tip: `bbfafc851d450ee7646842eaa3e8423f95eff424`.
- Python: `D:\Temp\paralls-g0-py312\Scripts\python.exe`, version 3.12.2. `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`; `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- Focused command: `python -m pytest -q --basetemp <F-drive run directory> backend/tests/test_owner_commit_builder.py backend/tests/test_ownership_runtime.py backend/tests/test_credential_runtime.py`; result `23 passed, 2 warnings in 0.75s`, exit 0.
- Frozen ownership: `selected=24 problems=0 improvements=0`. Frozen shared-replay: `selected=990 problems=0 improvements=0`. Shared-replay ran serially in 25 batches; no listener was active on port 8000 and no external process was stopped.
- Raw outputs: `F:\paralls-verification\thread-a\m3-1-current-tip-20261127-01\focused.log`, `ownership.log`, and `shared-replay.log`. Temporary, cache, and comparison output paths are under the same F-drive run directory.
- The full backend suite was not run. This revalidation does not establish U1-U10 completion or Architecture v2 completion. M3-1 remains `待门禁`.
