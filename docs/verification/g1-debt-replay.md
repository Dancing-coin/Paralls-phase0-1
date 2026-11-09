# G1 debt standard replay

Status: debt replay migration verified; G1 as a whole remains in progress.

- Base: `f7e8b2ae` (fixed-offer replay); G0 baseline: `4c6418763dfaa2efdbefccb7b1c31d612cabf2f1`.
- Scope: route seven debt command duplicate lookups through `owner_runtime_base.replay_duplicate`. Domain validation, digest, settlement plan, events and revision pins remain unchanged.
- Before and after migration, `D:/Temp/paralls-g0-py312/Scripts/python.exe -m pytest tests/test_debt_runtime.py tests/test_infra_debt_settlement_formal_spine.py tests/test_phase4_government_credit.py tests/test_economy_privacy_views.py tests/test_adventure_basic_scenario5.py -q -p no:cacheprovider` from `backend` passed all 48 tests. Added cases cover issue, payment, cancellation, overdue, default, cancellation reversal and payment correction: commit, exact replay, changed command, missing receipt and injected stale revision with no partial writes. Existing tests cover domain rejections, event contents and financial effects.
- Full comparison: `D:/Temp/paralls-g0-py312/Scripts/python.exe docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g1-debt-replay-run --freeze` from the repository root. Windows 11, Python 3.12.2, package and dependency hashes match G0. Runtime source hashes remained stable during execution.
- Result: 9,968 collected; 9,925 passed, 39 failed, 2 skipped and 2 xfailed. All 9,937 G0 nodes retain their outcomes; thirty-one accumulated added nodes passed. The 39 failure node/phase/error-type signatures match; normalized stacks match except the known WebSocket timeout cancel-scope runtime identifier. No collection errors.
- Raw results, manifest, invocation, environment, failure stacks and JUnit are in [g1-debt-replay-evidence.zip](g1-debt-replay-evidence.zip). The run used uncommitted unit changes; source hashes and worktree status are recorded in its environment snapshot.
- Rollback: revert the commit adding this record and its debt migration and tests. The shared helper belongs to the earlier ownership commit. Re-run targeted tests and the full baseline after rollback.

The 39 failures remain subject to the recorded G0 approval. B3 Godot spatial sampling, credential renewal and end-to-end interaction remain unverified. D2-D10 remain open.
