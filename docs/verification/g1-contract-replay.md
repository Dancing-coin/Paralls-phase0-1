# G1 contract standard replay

Status: contract replay migration verified; G1 as a whole remains in progress.

- Base: `6174d8ee` (debt replay); G0 baseline: `4c6418763dfaa2efdbefccb7b1c31d612cabf2f1`.
- Scope: four ordinary contract commands use `replay_duplicate`. Contract validation, digests, pins, payloads and special municipality and facility duplicate paths remain domain-owned.
- Before and after migration, the 15-file focused suite recorded in the archive's `focused-command.txt` passed 89 tests. Added parameterized cases cover create, fulfill, terminate and complete: normal commit, exact retry, changed payload, missing receipt and injected stale revision without partial writes. Existing cases cover rejection and domain effects.
- Full command from the repository root: `D:/Temp/paralls-g0-py312/Scripts/python.exe docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g1-contract-replay-final --freeze`. Windows 11, Python 3.12.2, package, dependency and pytest environment match G0; source hashes stayed stable during the run. The test-barrier fix was present as an uncommitted change and is committed separately.
- Final result: 9,976 collected; 9,933 passed, 39 failed, 2 skipped and 2 xfailed. All 9,937 G0 nodes retain their outcomes; 39 accumulated new nodes passed. The 39 failure node/phase/error-type signatures match; normalized stacks match except the known WebSocket timeout cancel-scope runtime identifier. No collection errors.
- The first full run had an additional world-admin test failure; the second matched G0 before fixing its test barrier. The diagnostic and the limitation on identifying the original signal are recorded in [g1-world-admin-test-barrier.md](g1-world-admin-test-barrier.md). All three runs are retained in [g1-contract-replay-evidence.zip](g1-contract-replay-evidence.zip).
- Rollback: revert the commit containing this record, the contract runtime change and its tests. The shared helper belongs to the earlier ownership commit. Re-run focused and full baseline tests after rollback.

The 39 failures remain subject to the recorded G0 approval. B3 Godot spatial sampling, credential renewal and end-to-end interaction remain unverified. D2-D10 remain open.
