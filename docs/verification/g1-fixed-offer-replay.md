# G1 fixed-offer standard replay

Status: fixed-offer replay migration verified; G1 as a whole remains in progress.

- Base: `185528ba` (land-right replay); G0 baseline: `4c6418763dfaa2efdbefccb7b1c31d612cabf2f1`.
- Scope: route offer publication and purchase duplicate lookup through `owner_runtime_base.replay_duplicate`, passing their original distinct principals. Domain validation, digest, events, revision pins and transaction construction remain unchanged.
- Before and after migration, `D:/Temp/paralls-g0-py312/Scripts/python.exe -m pytest tests/test_fixed_offer_purchase.py tests/test_adventure_basic_scenario1.py tests/test_adventure_basic_scenario4.py tests/test_adventure_basic_mirror_source.py -q -p no:cacheprovider` from `backend` passed all 22 tests. Added tests cover exact replay, changed request, missing receipt and injected stale commit for both operations, plus equal keys under the two principals. Existing tests cover atomic settlement, stale offer and domain rejection.
- Full comparison: `D:/Temp/paralls-g0-py312/Scripts/python.exe docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g1-fixed-offer-replay-run --freeze` from the repository root. Windows 11, Python 3.12.2, package and dependency hashes match G0. Runtime source hashes remained stable during execution.
- Result: 9,954 collected; 9,911 passed, 39 failed, 2 skipped and 2 xfailed. All 9,937 G0 nodes retain their outcomes; seventeen accumulated added nodes passed. The 39 failure node/phase/error-type signatures match; normalized stacks match except the known WebSocket timeout cancel-scope runtime identifier. No collection errors.
- Raw results, manifest, invocation, environment, failure stacks and JUnit are in [g1-fixed-offer-replay-evidence.zip](g1-fixed-offer-replay-evidence.zip). The run used uncommitted unit changes; source hashes and worktree status are recorded in its environment snapshot.
- Rollback: revert the commit adding this record and its fixed-offer migration and tests. The shared helper belongs to the earlier ownership commit. Re-run targeted tests and the full baseline after rollback.

The 39 failures remain subject to the recorded G0 approval. B3 Godot spatial sampling, credential renewal and end-to-end interaction remain unverified. D2-D10 remain open.
