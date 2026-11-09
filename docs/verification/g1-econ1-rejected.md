# G1 Econ-1 wage rejection

Status: Econ-1 wage owner rejection construction verified; G1 remains in progress.

- Base: `6f0fb845`; approved G0 baseline: `4c6418763dfaa2efdbefccb7b1c31d612cabf2f1`.
- Scope: route `EconomyAuthority.commit_obligation_batch` wage-owner rejection receipts through `rejected_result`. The wage authority keeps its existing scope checks, fragment checks, contract validation, stage and transaction prefix; settlement and append behavior remain unchanged.
- Focused command from `backend`: `D:/Temp/paralls-g0-py312/Scripts/python.exe -m pytest tests/test_infra_economy_wage_terminal_lifecycle.py tests/test_infra_economy_wage_obligation.py tests/test_infra_semantic_economy_wage_obligation.py tests/test_econ1_authority_settlement.py -q -p no:cacheprovider` passed 44 tests before and after extraction. Added cases cover scope-denied and fragment-mismatch receipts, exact fields and zero writes; existing tests cover normal commit, retry, expiry and stale revision.
- Full command from repository root: `D:/Temp/paralls-g0-py312/Scripts/python.exe docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g1-econ1-rejected-run --freeze`. Windows 11, Python 3.12.2, package, dependency and pytest environment match G0; source hashes stayed stable.
- Result: 9,982 collected; 9,939 passed, 39 failed, 2 skipped and 2 xfailed. All 9,937 G0 nodes retain their outcomes; 45 accumulated added nodes passed. The 39 failure node/phase/error-type signatures match; normalized stacks match except the known WebSocket timeout cancel-scope runtime identifier. No collection errors.
- Raw results, manifest, invocation, environment, failure stacks and JUnit are in [g1-econ1-rejected-evidence.zip](g1-econ1-rejected-evidence.zip).
- Rollback: revert the commit containing this record, the Econ-1 call-site change and focused tests. The shared helper is used by earlier committed units and must remain until those users are reverted.

The 39 failures remain subject to G0 approval. B3 Godot spatial sampling, credential renewal and end-to-end interaction remain unverified. D2-D10 remain open.
