# G1 ownership rejected receipt

Status: ownership municipal-certificate rejection construction verified; G1 remains in progress.

- Base: `07f8e957`; approved G0 baseline: `4c6418763dfaa2efdbefccb7b1c31d612cabf2f1`.
- Scope: extract `rejected_result` and use it for the ownership municipal certificate path. Ownership supplies its existing error code, `municipal_certificate_admission` stage and `transaction` prefix; validation, event construction, replay and writes stay in the domain.
- Before and after extraction, from `backend`: `D:/Temp/paralls-g0-py312/Scripts/python.exe -m pytest tests/test_inf4u_municipal_drought_assessment_certificate.py tests/test_inf3u_municipal_certificate_government_acknowledgment.py tests/test_inf_municipal_drought_closed_loop.py tests/test_ownership_runtime.py -q -p no:cacheprovider` passed 16 tests. Added cases freeze normal commit, exact retry, changed payload, missing advisory, stale contract and ownership revisions, receipt fields and unchanged store on rejection.
- Full command from the repository root: `D:/Temp/paralls-g0-py312/Scripts/python.exe docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g1-ownership-rejected-run --freeze`. Windows 11, Python 3.12.2, package, dependency and pytest environment match G0; source hashes stayed stable during execution.
- Result: 9,980 collected; 9,937 passed, 39 failed, 2 skipped and 2 xfailed. All 9,937 G0 nodes retain their outcomes; 43 accumulated added nodes passed. The 39 failure node/phase/error-type signatures match; normalized stacks match except the known WebSocket timeout cancel-scope runtime identifier. No collection errors.
- Raw results, manifest, invocation, environment, failure stacks and JUnit are in [g1-ownership-rejected-evidence.zip](g1-ownership-rejected-evidence.zip). The run used uncommitted unit changes; source hashes and worktree status are captured in the environment snapshot.
- Rollback: revert the commit containing this record, its shared helper, ownership change and tests. Re-run the focused suite and full baseline after rollback. Later users of the helper would need to be reverted first.

The 39 failures remain subject to G0 approval. B3 Godot spatial sampling, credential renewal and end-to-end interaction remain unverified. D2-D10 remain open.
