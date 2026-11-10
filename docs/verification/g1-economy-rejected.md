# G1 economy rejection

Status: economy owner rejection construction verified; G1 remains in progress.

- Base: `68e7f644`; approved G0 baseline: `4c6418763dfaa2efdbefccb7b1c31d612cabf2f1`.
- Scope: route the standard `EconomyAuthority` obligation rejection receipt through `rejected_result`. Economy keeps its existing scope, fragment, catalog and domain-specific rejection paths, including the remaining `GameplayFailure` uses; only the `economy_obligation_commit` helper path is extracted.
- Focused command from `backend`: `D:/Temp/paralls-g0-py312/Scripts/python.exe -m pytest tests/test_infra_economy_scheduled_transfer_obligation.py tests/test_infra_package_declared_negotiated_exchange.py tests/test_phase4_multi_org_commerce.py tests/test_economy_privacy_views.py tests/test_econ1_authority_settlement.py tests/test_infra_ecology_c4_economy_survival_adoption.py tests/test_infra_ecology_weather_front_economy_quote_edge.py tests/test_infra_ecology_weather_front_economy_quote_fanout.py tests/test_infra_economy_policy_instance_registration.py -q -p no:cacheprovider` passed 108 tests after the import fix. The first narrower 61-test command passed before the full caller set was added.
- The first full run (`D:/Temp/paralls-g1-economy-rejected-run`) exposed 16 `NameError` failures because three other domain rejection paths still referenced `GameplayFailure` after the import was removed. The import was restored; the expanded 108-test focus passed, and the rerun (`D:/Temp/paralls-g1-economy-rejected-rerun`) passed the full comparison.
- Full command: `D:/Temp/paralls-g0-py312/Scripts/python.exe docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g1-economy-rejected-rerun --freeze`. Windows 11, Python 3.12.2, package, dependency and pytest environment match G0; source hashes stayed stable.
- Rerun result: 9,982 collected; 9,939 passed, 39 failed, 2 skipped and 2 xfailed. All 9,937 G0 nodes retain their outcomes; 45 accumulated added nodes passed. The 39 failure node/phase/error-type signatures match; normalized stacks match except the known WebSocket timeout cancel-scope runtime identifier. No collection errors.
- Raw first-run and rerun results, manifests, environments, invocation, failure stacks and JUnit are in [g1-economy-rejected-evidence.zip](g1-economy-rejected-evidence.zip).
- Rollback: revert the commit containing this record, the Economy call-site/import change and test assertions. The shared helper is used by earlier committed units and must remain until those users are reverted.

The 39 failures remain subject to G0 approval. B3 Godot spatial sampling, credential renewal and end-to-end interaction remain unverified. D2-D10 remain open.
