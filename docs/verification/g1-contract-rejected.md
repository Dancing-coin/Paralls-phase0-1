# G1 contract rejection

Status: contract admission rejection construction verified; G1 remains in progress.

- Base: `db22569a`; approved G0 baseline: `4c6418763dfaa2efdbefccb7b1c31d612cabf2f1`.
- Scope: route the standard contract admission rejection receipt through `rejected_result`. Contract keeps its existing validation, special duplicate paths, stage and transaction prefix; payload, digest, revision pins and append behavior remain domain-owned.
- Focused command from `backend`: the 15-file contract replay suite used for the contract unit passed 89 tests after this extraction. Its parameterized replay and stale revision cases remain unchanged.
- Full command from repository root: `D:/Temp/paralls-g0-py312/Scripts/python.exe docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g1-contract-rejected-run --freeze`. Windows 11, Python 3.12.2, package, dependency and pytest environment match G0; source hashes stayed stable.
- Result: 9,984 collected; 9,939 passed, 39 failed, 2 skipped and 2 xfailed. All 9,937 G0 nodes retain their outcomes; 45 accumulated added nodes passed. The 39 failure node/phase/error-type signatures match; normalized stacks match except the known WebSocket timeout cancel-scope runtime identifier. No collection errors.
- Raw results, manifest, invocation, environment, failure stacks and JUnit are in [g1-contract-rejected-evidence.zip](g1-contract-rejected-evidence.zip).
- Rollback: revert the commit containing this record and the contract call-site change. The shared helper is used by earlier committed units and must remain until those users are reverted.

The 39 failures remain subject to G0 approval. B3 Godot spatial sampling, credential renewal and end-to-end interaction remain unverified. D2-D10 remain open.
