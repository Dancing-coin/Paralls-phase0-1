# G1 credential standard replay

Status: credential replay migration verified; G1 as a whole remains in progress.

- Base: `f3800055` (gift replay); G0 baseline: `4c6418763dfaa2efdbefccb7b1c31d612cabf2f1`.
- Scope: route issue, revoke and supersede duplicate lookup through `owner_runtime_base.replay_duplicate`. Credential exception types and codes, digest, event payloads, pins and transaction construction remain unchanged.
- Before and after migration, `D:/Temp/paralls-g0-py312/Scripts/python.exe -m pytest tests/test_credential_runtime.py tests/test_adventure_basic_scenario1.py -q -p no:cacheprovider` from `backend` passed all 14 tests. New parameterized cases cover each command's commit, exact retry, changed command, missing receipt and rejection on an injected stale expected revision without partial writes. Existing tests cover domain rejections and projection effects.
- Full comparison: `D:/Temp/paralls-g0-py312/Scripts/python.exe docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g1-credential-replay-run --freeze` from the repository root. Windows 11, Python 3.12.2, package and dependency hashes match G0. Runtime source hashes remained stable during execution.
- Result: 9,947 collected; 9,904 passed, 39 failed, 2 skipped and 2 xfailed. All 9,937 G0 nodes retain their outcomes; ten accumulated added nodes passed. The 39 failure node/phase/error-type signatures match; normalized stacks match except the known WebSocket timeout cancel-scope runtime identifier. No collection errors.
- Raw results, manifest, invocation, environment, failure stacks and JUnit are in [g1-credential-replay-evidence.zip](g1-credential-replay-evidence.zip). The run used uncommitted unit changes; source hashes and worktree status are recorded in its environment snapshot.
- Rollback: revert the commit adding this record and its credential migration and tests. The shared helper belongs to the earlier ownership commit. Re-run targeted tests and the full baseline after rollback.

The 39 failures remain subject to the recorded G0 approval. B3 Godot spatial sampling, credential renewal and end-to-end interaction remain unverified. D2-D10 remain open.
