# M1-3 Pool casualty refold trigger

## Scope

Commit `84d12a87f8bdc3ba05324f992c0d157aeafdd695` adds `casualty` to the allowed trigger set for distribution Pool refolds. This implements the trigger needed by the approved siege-scoped `morale_refold@1` rule. It does not implement the resolver, read Organization roster facts, calculate survivor ratios, or dispatch a production Morale command.

Changed files are `backend/app/gameplay/pool_runtime.py` and `backend/tests/test_pool_runtime.py`. The regression test passes one typed casualty trigger and a pinned input revision to the registered refold callback and checks its returned 75 value and exact inputs. Before the production change, the new test failed with `pool_refold_trigger_invalid`.

## Verified

Environment was Windows, Python 3.12.2, SQLite 3.43.1. Before pytest, `PYTHONPATH=F:/codex-temp/paralls-v2-thread-a-bond-20261121/backend`; `app.__file__` resolved to `F:/codex-temp/paralls-v2-thread-a-bond-20261121/backend/app/__init__.py`. `TEMP`, `TMP`, and `TMPDIR` pointed to `F:/paralls-verification/thread-a/m1-3-casualty-refold-20261123-002/`.

Command:

```powershell
& 'D:\Temp\paralls-g0-py312\Scripts\python.exe' -B -m pytest -q --basetemp '<F-output>\pytest-tmp' -p no:cacheprovider backend/tests/test_pool_runtime.py
```

Raw output was `17 passed, 2 warnings in 0.31s`, exit 0. The warnings are Starlette's deprecated `httpx` TestClient integration and AnyIO's deprecated `BlockingPortal` alias.

The frozen `ownership`, `modifier`, `equipment`, and `inventory` selections returned respectively `selected=24/12/87/56 problems=0 improvements=0`. The Pool selection returned `selected=17 problems=0 improvements=0`. The remaining registered selections for M1-1 land-right compatibility, M3-2, M5-1's six selections, M5-2, and M6-1 through M6-4 returned zero problems and zero improvements, totaling 104 selected nodes.

`shared-replay` returned `selected=990 problems=2 improvements=0`. The two call-stage `RuntimeError` failures were `test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage]` and `[wall-clock]`, both reporting `Port 8000 is occupied by an external process without a healthy backend`. No process was stopped or modified. The other 988 nodes matched the frozen outcomes.

Raw outputs and per-node JSON are in `F:/paralls-verification/thread-a/m1-3-casualty-refold-20261123-003/`. The expected RED output is in `F:/paralls-verification/thread-a/m1-3-casualty-refold-20261123-001/red.txt`; green targeted output is in `...-002/targeted.txt`.

## Not verified

- Full pytest was not run for this trigger change.
- `harness.py --profile all`, Morale resolver behavior on authoritative roster/LifeState facts, Gateway/L5 production dispatch, and the siege demo were not run.
- shared-replay did not pass. Its two environment failures are recorded rather than treated as a passing selection.
- The merged-state full suite recorded for the preceding Pool factory slice is separate evidence and is not attributed to this change.

## Conclusion

The new casualty trigger and its pinned revision vector are verified by the Pool unit test. Pool frozen selections passed. The shared replay selection has two external-port failures. The full suite and Morale production path remain unverified. M1-3 remains pending its broader gate and existing U1/U2/U5/U7/U8 gaps.
