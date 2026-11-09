# G1 ownership standard replay

Status: first migration unit verified; G1 as a whole remains in progress.

- Base: `1f70ebc013255db3c61e99c3d817713b7f3f5ba7`; G0 full baseline: `4c6418763dfaa2efdbefccb7b1c31d612cabf2f1`.
- Scope: extract only standard ownership duplicate lookup to `owner_runtime_base.replay_duplicate`. Grant and transfer call it; municipal certificate replay remains independent. Digest, revision pins, events, rejection and side effects are unchanged.
- Before extraction: ownership caller files passed 52 tests; two added characterization tests passed. After extraction the same caller files and new tests passed 54 tests.
- Full comparison: `D:/Temp/paralls-g0-py312/Scripts/python.exe docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g1-ownership-replay-run --freeze`, from repository root, on Windows 11 and Python 3.12.2. Python version, package hash and dependency hashes match G0; source hashes remained stable during the run.
- Result: 9,939 collected; 9,896 passed, 39 failed, 2 skipped, 2 xfailed. All 9,937 baseline nodes retain their outcomes; the two new nodes passed. The same 39 failure node/phase/error-type signatures remain. All normalized stacks match except the already documented WebSocket timeout cancel-scope runtime identifier. No collection errors.
- Raw results, manifest, invocation, environment, failure stacks and JUnit are in [g1-ownership-replay-evidence.zip](g1-ownership-replay-evidence.zip). The run occurred with the unit changes uncommitted; its environment snapshot includes their worktree status and source hashes.
- Rollback: revert the commit adding this record and the associated ownership replay changes. Later users of the shared helper would first need to be reverted or migrated away; until then the commit is independently reversible. Re-run the targeted tests and full baseline after a rollback.

The 39 G0 failures remain accepted only under the existing G0 approval. B3 Godot spatial sampling, credential renewal and end-to-end interaction remain unverified. D2-D10 remain open.
