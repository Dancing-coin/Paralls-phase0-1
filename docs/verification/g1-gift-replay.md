# G1 gift standard replay

Status: gift replay migration verified; G1 as a whole remains in progress.

- Base: `38baad8e` (ownership replay); G0 baseline: `4c6418763dfaa2efdbefccb7b1c31d612cabf2f1`.
- Scope: route the single gift duplicate lookup through `owner_runtime_base.replay_duplicate`, retaining its exception class and missing-result code. Gift's digest, four-stream transaction, revisions, events and validation remain domain-owned.
- Before and after migration, `D:/Temp/paralls-g0-py312/Scripts/python.exe -m pytest tests/test_gift_runtime.py tests/test_adventure_basic_scenario5.py -q -p no:cacheprovider` from `backend` passed all 7 tests. Added cases check changed retry and missing receipt without writes, and inject an outdated expected revision at append to verify rejection without partial writes. Existing cases cover the atomic transaction, replay and domain rejection.
- Full comparison: `D:/Temp/paralls-g0-py312/Scripts/python.exe docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g1-gift-replay-run --freeze` from the repository root. Windows 11, Python 3.12.2, package and dependency hashes match G0. Runtime source hashes remained stable during execution.
- Result: 9,941 collected; 9,898 passed, 39 failed, 2 skipped and 2 xfailed. All 9,937 G0 nodes retain their outcomes, and four added ownership and gift nodes passed. The 39 failure node/phase/error-type signatures match; all normalized stacks match except the known WebSocket timeout cancel-scope runtime identifier. No collection errors.
- Raw results, manifest, invocation, environment, failure stacks and JUnit are in [g1-gift-replay-evidence.zip](g1-gift-replay-evidence.zip). The run used the uncommitted unit changes; source hashes and worktree status are recorded in its environment snapshot.
- Rollback: revert the commit adding this record and its gift migration and tests. The shared helper comes from the earlier ownership commit and remains available independently. Re-run targeted tests and the full baseline after rollback.

The 39 failures remain subject to the recorded G0 approval. B3 Godot spatial sampling, credential renewal and end-to-end interaction remain unverified. D2-D10 remain open.
