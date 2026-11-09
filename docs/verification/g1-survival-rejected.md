# G1 survival rejection

Status: survival owner rejection construction verified; G1 remains in progress.

- Base: `0d2c5985`; approved G0 baseline: `4c6418763dfaa2efdbefccb7b1c31d612cabf2f1`.
- Scope: route `SurvivalAuthority.commit_obligation_batch` rejection receipts through `rejected_result`. Survival keeps its existing fragment and event validation, `survival_obligation_commit` stage and `transaction` prefix; state projection and append behavior remain unchanged.
- Focused command from `backend`: `D:/Temp/paralls-g0-py312/Scripts/python.exe -m pytest tests/test_infra_survival_state_obligation.py tests/test_infra_survival_heat_state_obligation.py tests/test_infra_survival_dehydration_state_obligation.py -q -p no:cacheprovider` passed 31 tests against the original construction and 31 after extraction. Added assertions cover receipt fields and zero writes for tampered payload and event order; existing tests cover normal state expiry and lifecycle behavior.
- Full command from repository root: `D:/Temp/paralls-g0-py312/Scripts/python.exe docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g1-survival-rejected-run --freeze`. Windows 11, Python 3.12.2, package, dependency and pytest environment match G0; source hashes stayed stable.
- Result: 9,982 collected; 9,939 passed, 39 failed, 2 skipped and 2 xfailed. All 9,937 G0 nodes retain their outcomes; 45 accumulated added nodes passed. The 39 failure node/phase/error-type signatures match; normalized stacks match except the known WebSocket timeout cancel-scope runtime identifier. No collection errors.
- Raw results, manifest, invocation, environment, failure stacks and JUnit are in [g1-survival-rejected-evidence.zip](g1-survival-rejected-evidence.zip).
- Rollback: revert the commit containing this record, the Survival call-site change and test assertions. The shared helper is used by earlier committed units and must remain until those users are reverted.

The 39 failures remain subject to G0 approval. B3 Godot spatial sampling, credential renewal and end-to-end interaction remain unverified. D2-D10 remain open.
