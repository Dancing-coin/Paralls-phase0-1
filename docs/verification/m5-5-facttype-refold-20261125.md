# M5-5 FactType distribution refold requirement

Date: 2026-11-25

## Scope and implementation

Implement the formal validator rule `facttype_refold_missing`: a FactType declaring `aggregation: distribution` must name a nonempty `refold_model_ref`. The implementation is in `backend/app/gameplay/fact_type_registry.py`; the regression is in `backend/tests/test_rule_pack_validator.py`.

This is a compile-time registration check. It does not change event schemas, persisted event payloads, Owner classification, Resolver behavior, or distribution execution. It closes only this validator rule and does not claim M5 or Architecture v2 completion.

## Environment

- Base commit: `f5cc36326d144aad78752073ae3fc819dd8ccc9d`.
- First implementation commit: `f0c9108dc715869f73b6a919e3fd674f87292b4c`.
- Follow-up implementation commit: `3907d4eb45b93cc95d4d5e866b25cd92a5e6f74a`.
- Interpreter: Python 3.12.2 (`D:\Temp\paralls-g0-py312\Scripts\python.exe`); pytest 9.1.1.
- Follow-up primitive validation environment: Python 3.12.2, pytest 9.1.1, SQLite 3.43.1; `app.__file__` resolved inside the A worktree. Clean reruns removed inherited `GIT_CONFIG_*` environment variables because an empty `GIT_CONFIG_VALUE_0` caused nested Git commands to fail.
- `PYTHONPATH` pointed to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`; `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- A post-run environment check with the same interpreter and `PYTHONPATH` reported SQLite 3.43.1.

## Verification

| Check | Result | Raw evidence |
|---|---|---|
| TDD regression before implementation | Failed because `load_pack` did not raise `RegistrationRejected` | `F:\paralls-verification\thread-a\m5-5-facttype-refold-red-20261125-01\` |
| Focused command: `backend/tests/test_rule_pack_validator.py backend/tests/test_pool_runtime.py` | `120 passed, 2 warnings` | `F:\paralls-verification\thread-a\m5-5-facttype-refold-20261125-01\pytest-focused.log` |
| Frozen selection comparison | 5 selections, 1,169 nodes, `problems=0 improvements=0` | `F:\paralls-verification\thread-a\m5-5-refold-gates-20261125-01\` |
| Registered selection comparison at `f0c9108d` | 25 selections, 222 nodes, `problems=0 improvements=0` | Same directory; per-selection `results.json`, invocation records, and `summary.txt` |
| Full backend suite at implementation commit | `10,624 passed, 24 failed, 2 skipped, 2 xfailed`, exit code 1; 10,652 collected | `F:\paralls-verification\thread-a\m5-5-facttype-refold-full-20261125-f0c9108d\full-console.log` and `full\junit.xml` |
| Failed-node comparison at parent commit | The same 24 failed node IDs, phases, and error types; `new=0 parent_extra=0` | `F:\paralls-verification\thread-a\m5-5-facttype-refold-parent-20261125-03\parent-console.log` and `parent-failing-nodes\junit.xml` |

Selection comparison used the frozen manifests under `docs/verification/absorb-main-3bf3418e/` and all 25 files under `docs/verification/selection/`. The comparison metrics were checked from the retained per-batch `results.json` against those manifests. Every selected node passed in the current run. The full-suite result is a nonzero exit and is not reported as a passing full suite. Parent comparison reran the 24 failing node IDs only, not the full suite.

## Follow-up validator rule: missing FactType scope

The formal `facttype_scope_missing` rule distinguishes a missing scope from the general `facttype_naming_invalid` diagnostic. Pack loading previously classified both `fact:credential:link` and `fact:credential::link` as naming errors. Commit `3907d4eb45b93cc95d4d5e866b25cd92a5e6f74a` now emits the dedicated scope diagnostic for those two forms; other malformed names retain `facttype_naming_invalid`.

| Check | Result | Raw evidence |
|---|---|---|
| TDD red | Both parameter cases failed because no `facttype_scope_missing` violation was emitted | `F:\paralls-verification\thread-a\m5-5-scope-missing-red-20261125-02\` |
| Focused Validator and Pool tests | `122 passed, 2 warnings` | `F:\paralls-verification\thread-a\m5-5-scope-missing-final-focused-20261125-01\` |
| Frozen selection comparison | 5 selections, 1,169 nodes, `problems=0 improvements=0` | `F:\paralls-verification\thread-a\m5-5-scope-gates-corrected-20261125-3907d4eb\` |
| Registered selection comparison | 25 selections, 224 nodes, `problems=0 improvements=0` | Same directory; includes the 3-node M5-5 selection |
| Full backend suite with corrected F-drive pytest path | `10,623 passed, 27 failed, 2 skipped, 2 xfailed`, exit code 1; 10,654 collected | `F:\paralls-verification\thread-a\m5-5-scope-full-corrected-20261125-3907d4eb\full-console.log` and `full\junit.xml` |
| Additional flaky failure recheck | `test_original_owner_outbox_recovers_after_hard_kill[domain]` passed on an isolated retry, 1 passed, 2 warnings | `F:\paralls-verification\thread-a\m5-5-outbox-recheck-20261125-3907d4eb\pytest.log` |

The corrected full run has the same 24 failed node IDs, phases, and error types as the previous `f0c9108d` full run. Two additional `test_embodied_interaction_session_runner` cases failed because port 8000 was occupied by the external backend under `D:\cl-laya`; that process was not stopped. One additional outbox recovery case raised `PermissionError` while reading `completed.json`, then passed on the isolated retry. The full suite remains non-green.

P-1 pattern scan of the staged follow-up documentation and selection additions found 0 matches.

The first follow-up full attempt used a Windows backslash path in `PYTEST_ADDOPTS`. Pytest parsed the backslashes as escapes and created a temporary tree under `backend`, producing 48 failures. This run is invalid for comparison and is not used as the full-suite result. Its two owned scratch trees were moved to `F:\paralls-verification\thread-a\pytest-scratch-m5-5-scope-full-3907d4eb-misparsed` and `F:\paralls-verification\thread-a\pytest-scratch-m5-5-scope-gates-3907d4eb-misparsed`. Corrected runs use forward slashes in `PYTEST_ADDOPTS` and place scratch data on F:.

## Unit DoD status

| Item | Status |
|---|---|
| U1 | 未做。本单元不声明或迁移 Owner。 |
| U2 | 未做。本单元不新增 Owner schema。 |
| U3 | 部分验证。校验缺少 distribution refold 引用，并区分无 scope 的专用拒绝码。 |
| U4 | 未做。本单元不改变 Resolver 合同。 |
| U5 | 未做。本单元不改变 Owner 提交或持久事件。 |
| U6 | 未做。本单元不改变读取方。 |
| U7 | 未做。本单元不改变投影更新。 |
| U8 | 未做。本单元不改变 replay 或 checkpoint 重建。 |
| U9 | 已运行定向测试、冻结及登记选择集，并运行全量。当前全量退出码为 1；24 个既有失败保持，2 个失败源于外部端口占用，1 个权限失败在独立重跑通过。 |
| U10 | 本证据文件记录了命令结果、环境、原始输出位置和未覆盖项。 |
| U11 | 已登记 `docs/verification/selection/m5-5-facttype-refold.json`，3 个回归节点。 |

## Remaining work and unverified scope

- Other rows in `m5-5-rule-pack-validator-coverage-20261122.md` retain their recorded states. Production command registration, temporal-effect contracts, package-version write boundaries, and cross-boundary application wiring are outside this rule.
- The full suite did not pass. The parent comparison establishes that this unit added no new failures among the 24 failing nodes, but it does not convert the full-suite exit code to success.
- This evidence does not establish M5 or Architecture v2 completion.

## Follow-up validator rule: missing FactType primitive

The formal `primitive_missing` diagnostic was unreachable for rule packs because `load_pack` rejected a FactType without `primitive` during its shape check as `pack_schema_invalid`. The shape check now lets only the absent-primitive case reach `FactTypeRegistry.compile`, which emits `primitive_missing`. Unsupported non-null primitive values remain rejected by the shape check.

| Check | Result | Raw evidence |
|---|---|---|
| TDD red | New regression failed because `primitive_missing` was not emitted | `F:\paralls-verification\thread-a\m5-5-primitive-missing-investigation\` |
| Focused FactType, Validator, and Pool tests | `126 passed, 2 warnings` | `F:\paralls-verification\thread-a\m5-5-primitive-focused-clean-6bc5e6dd5fb8444aad830cba322c14a7\pytest.log` |
| Frozen selection comparison | 5 selections, 1,169 nodes, all `problems=0 improvements=0` | `F:\paralls-verification\thread-a\m5-5-primitive-gates-de033677e0964158a3a151394aa1ddb6\gate-run.log` |
| Registered selection comparison | 25 selections, 225 nodes total, all `problems=0 improvements=0`; M5-5 selection has 4 nodes | Same gate directory; per-selection batch results |
| M5-5 regression selection at exact implementation commit `a5823c4b` | `selected=4 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m5-5-primitive-regression-exact-6ae3c9e3fc734133aa7b808f4d9d8368\batch-0000\results.json` |
| Initial backend full suite | `10,646 passed, 5 failed, 2 skipped, 2 xfailed`, exit code 1 | `F:\paralls-verification\thread-a\m5-5-primitive-full-db08f57029bc4c3bb0c0c61ae8d603de\full-console.log` |
| Initial full-suite failure comparison | Four failures reproduced at parent `735e283f`; one population recovery failure passed at both current and parent after removing inherited `GIT_CONFIG_*` variables | `F:\paralls-verification\thread-a\m5-5-primitive-parent-failures-20261125.log` and `F:\paralls-verification\thread-a\m5-5-primitive-current-failure-recheck-20261125.log` |
| Sanitized backend full suite | `10,647 passed, 4 failed, 2 skipped, 2 xfailed`, exit code 1; 10,655 collected | `F:\paralls-verification\thread-a\m5-5-primitive-full-clean-69d67f5380614bcba373828e38ea4c2d\full-console.log` |

The four full-suite failures are `test_all_22_repaired_budgets_equal_fixed_official_usage`, `test_task45_headless_probe_observes_shared_path_and_contact_contract`, `test_cold_ready`, and `test_task8_headless_registry_probe_resolves_profiles_and_blocks_rejected_registration`. The same four failed on parent `735e283f` when rerun with the same sanitized Git environment. Their captured errors concern the calibration fixture, missing Godot global script classes, and missing `resource_bounds` in a population report. These paths do not consume FactType registration. The initial full run inherited an empty `GIT_CONFIG_VALUE_0`; a child fixture-generation process consequently failed to read the Git revision and produced the fifth failure. Removing inherited `GIT_CONFIG_*` variables made that population recovery node pass on both the current code and its parent. The clean full run was performed with inherited `GIT_CONFIG_*` variables removed.

## Follow-up validator rule: package-defined primitives

The rule-pack loader previously ignored a top-level `primitives` declaration and treated a `primitives` content section as a generic schema error. Both forms now receive the formal `pack_defines_primitive` rejection. Primitive definitions remain code-registered.

| Check | Result | Raw evidence |
|---|---|---|
| TDD red at parent `a5823c4b` | Both declaration forms failed because no `pack_defines_primitive` violation was emitted | `F:\paralls-verification\thread-a\m5-5-pack-defines-primitive-red-repro-20261125-confirmed.log` |
| Focused FactType, Validator, and Pool tests | `128 passed, 2 warnings` | `F:\paralls-verification\thread-a\m5-5-pack-defines-primitive-focused-clean-dd5abc0da5b04e629ae45aeb27904ea2\pytest.log` |
| M5-5 regression selection at `553c35bd` | `selected=6 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m5-5-pack-defines-primitive-selection-d089cad043ff490baa822cf2a2a152d3\batch-0000\results.json` |
| Frozen selection comparison | 5 selections, 1,169 nodes, all `problems=0 improvements=0` | `F:\paralls-verification\thread-a\m5-5-pack-defines-primitive-gates-d49ba160907842178acef60d67841bbc\gate-run.log` |
| Registered selection comparison | 25 selections, 227 nodes total, all `problems=0 improvements=0` | Same gate directory; per-selection batch results |
| Clean backend full suite | `10,648 passed, 5 failed, 2 skipped, 2 xfailed`, exit code 1; 10,657 collected | `F:\paralls-verification\thread-a\m5-5-pack-defines-primitive-full-46dda022c3cc4a9486bc221b28103e0e\full-console.log` |
| Full-suite failure comparison | Four failures reproduced at parent `a5823c4b`; the fifth node passed at parent and in a current-code targeted rerun | `F:\paralls-verification\thread-a\m5-5-pack-defines-primitive-parent-failures-20261125.log` and `F:\paralls-verification\thread-a\m5-5-pack-defines-primitive-current-failure-recheck-20261125.log` |

The four reproduced failures are the calibration-budget assertion, Task45 Godot probe, population cold-ready report, and Task8 Godot probe described above. `test_original_owner_provider_pending_survives_hard_kill_without_reingest[character]` failed once in the full suite, then passed both on parent `a5823c4b` and in a current-code targeted rerun. The suite remains non-green and no new persistent failure was observed from this unit.

## Follow-up validator rule: unknown FactType primitive

Rule-pack validation now distinguishes a primitive value outside the six registered values from a known but not-yet-implemented primitive. Unknown values receive the formal `primitive_unknown` diagnostic. The current compiler still implements only Machine and Pool, so the other four known values remain unsupported pending their L1 units.

| Check | Result | Raw evidence |
|---|---|---|
| TDD red | Unknown primitive regression failed because `primitive_unknown` was not emitted | `F:\paralls-verification\thread-a\m5-5-primitive-unknown-red-20261125\pytest.log` |
| Focused FactType, Validator, and Pool tests | `129 passed, 2 warnings` | `F:\paralls-verification\thread-a\m5-5-primitive-unknown-focused-9178ee71d16d453e89a72eacbbb20295\pytest.log` |
| M5-5 regression selection at `888ec615` | `selected=7 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m5-5-primitive-unknown-selection-8283035f75c54a5a918f5817b2ef1479\batch-0000\results.json` |
| Frozen selection comparison | 5 selections, 1,169 nodes, all `problems=0 improvements=0` | `F:\paralls-verification\thread-a\m5-5-primitive-unknown-gates-53116699456140fb923dcd3f56c1664e\gate-run.log` |
| Registered selection comparison | 25 selections, 228 nodes total, all `problems=0 improvements=0` | Same gate directory; per-selection batch results |
| Clean backend full suite | `10,650 passed, 4 failed, 2 skipped, 2 xfailed`, exit code 1; 10,656 collected | `F:\paralls-verification\thread-a\m5-5-primitive-unknown-full-9bd3859f809244019c3c8b23ed37cccf\full-console.log` |
| Full-suite failure comparison | All four failures reproduced on parent `a5823c4b` in the previous M5-5 unit; the present change only classifies invalid primitive values during pack loading | `F:\paralls-verification\thread-a\m5-5-pack-defines-primitive-parent-failures-20261125.log` |

The four baseline failures remain the calibration-budget assertion, Task45 Godot probe, population cold-ready report, and Task8 Godot probe. The full suite remains non-green. No persistent new failure was observed in the relevant selection or parent comparison.

### Primitive registry maintenance follow-up

Commit `cbee0c6cf8c436ff7fbfa00373c655b3131d2ed3` moved the six primitive IDs into `fact_type_registry.py` so the RulePack loader and FactType compiler share the registered set. This is behavior-preserving. Validator, Pool, and FactType focused tests remained `129 passed`; the five frozen selections (1,169 nodes) and all 25 registered selections (228 nodes) returned `problems=0 improvements=0`. No second full-suite run was needed for this refactor. Raw outputs are in `F:\paralls-verification\thread-a\m5-5-primitive-registry-focused-f584e2521bbd40209ee6f0ae4c6d0431\pytest.log` and `F:\paralls-verification\thread-a\m5-5-primitive-registry-gates-bb88817fca714eb29b09c96e134a253d\gate-run.log`.
### Primitive registry cardinality contract

Commit 1fb14ba45df0ebd3f9ff9448de9d754b40122c40 adds a regression asserting that the code-registered primitive set has exactly six values. Since RulePack loading rejects package-defined primitives and the runtime registry is not mutable, a package cannot exceed the count independently of a code change. The formal primitive_count_exceeded rule is therefore covered as a structural guarantee, with the exact registered count pinned by a test.

| Check | Result | Raw evidence |
|---|---|---|
| Focused FactType and RulePack Validator tests | 111 passed, 2 warnings | F:/paralls-verification/thread-a/m5-5-primitive-count-gates-74182d4414634f6cb3dc6e0020cba46e/focused-1fb14ba4-20261125/pytest.log; command: python -m pytest backend/tests/test_rule_pack_validator.py backend/tests/test_fact_type_registry.py -q |
| Frozen selection comparison | 5 selections, 1,169 nodes; problems=0 improvements=0 for every group | F:/paralls-verification/thread-a/m5-5-primitive-count-gates-74182d4414634f6cb3dc6e0020cba46e/gate-run.log |
| Registered selection comparison | 25 selections, 229 nodes total; problems=0 improvements=0 for every group, including the 8-node M5-5 selection | Same gate log and per-batch results.json files |
| Environment | Python 3.12.2, pytest 9.1.1, SQLite 3.43.1; PYTHONPATH points to A backend, app.__file__ resolves inside A worktree | environment.json files in the gate output; post-run interpreter check in this session |
| Temporary data location | Output is under F. Three pytest scratch directories totaling 2,105,631 bytes were moved from the default D temporary directory into the run's pytest-temp folder after tests completed; their D-side symlinks now target the F copies | F:/paralls-verification/thread-a/m5-5-primitive-count-gates-74182d4414634f6cb3dc6e0020cba46e/pytest-temp/ |
| Full backend suite | Not rerun at 1fb14ba4. The nearest clean full run is the predecessor M5-5 result 10,650 passed, 4 failed, 2 skipped, 2 xfailed, exit code 1; it is not evidence for the exact test-only commit | F:/paralls-verification/thread-a/m5-5-primitive-unknown-full-9bd3859f809244019c3c8b23ed37cccf/full-console.log |

The frozen and registered comparisons used the current A worktree HEAD 1fb14ba45df0ebd3f9ff9448de9d754b40122c40. The full-suite result is historical to its recorded predecessor and remains non-green. The unit does not claim broader M5 or Architecture v2 completion.

### Follow-up FactType ID naming limits

The formal FactType schema constrains the domain segment to lowercase letters and underscores with length 2–24, the name segment to lowercase letters, digits, underscores, and hyphens with length 2–48, and the full ID to at most 128 characters. Commit `3a0e35b6bf9d02ce7f34e3a9e43010946c49005f` applies these checks during FactType registration while retaining the dedicated `facttype_scope_missing` result for absent or empty scope. Six invalid forms now have regression coverage.

| Check | Result | Raw evidence |
|---|---|---|
| Focused `test_rule_pack_validator.py` | `117 passed, 2 warnings` | `F:\paralls-verification\thread-a\m5-5-facttype-naming-focused-20261125-01\pytest.log` |
| Frozen selection comparison | 5 selections, 1,169 nodes, all `problems=0 improvements=0` | `F:\paralls-verification\thread-a\m5-5-facttype-naming-gates-3a0e35b6-20261125\gate-run.log` |
| Registered selection comparison | 25 selections, 235 nodes, all `problems=0 improvements=0`; M5-5 selection has 14 nodes | Same directory, per-selection results |
| Current exact-commit backend suite | `10,637 passed, 24 failed, 2 skipped, 2 xfailed`, exit code 1; 10,665 collected | `F:\paralls-verification\thread-a\m5-5-facttype-naming-full-3a0e35b6-20261125\full-console.log` and `full\results.json` |
| Parent exact-commit backend suite at `aa1f2507` | `10,631 passed, 24 failed, 2 skipped, 2 xfailed`, exit code 1; 10,659 collected | `F:\paralls-verification\thread-a\m5-5-facttype-naming-parent-full-aa1f2507-20261125\full-console.log` and `full\results.json` |
| Full-suite failure comparison | 23 failed nodes have matching phase and error data. The current-only `test_recovery_owner_probe_measures_original_startup_before_full_oracle` and parent-only `test_original_owner_outbox_recovers_after_hard_kill[domain]` each passed when rerun alone on both commits, so those swapped failures are intermittent. No persistent new failure was observed. | Full result JSON files and isolated outputs under `F:\paralls-verification\thread-a\m5-5-facttype-naming-{current,parent}-unique-failure-20261125-01\pytest.log` |
| Runtime environment | Python 3.12.2, pytest 9.1.1, SQLite 3.43.1; `PYTHONPATH` targeted each exact worktree and `app.__file__` resolved inside it | `full\environment.json` in each full-run directory and isolated command output |

The full suite remains non-green. The exact-commit comparison is compatible with the parent baseline, with two one-off failures swapped between runs and both passing in isolated reruns. The FactType naming unit does not claim broader M5 or Architecture v2 completion.

### Follow-up `facttype_process_kind_invalid`

The FactType schema defines `process_kind` only for the `process` primitive. The compiler previously ignored this field on other primitives. Commit `d02e8c736a9b9f9e36e661d65f96f046fe89371f` now emits `facttype_process_kind_invalid` when a non-process FactType declares it. This does not implement the Process primitive.

| Check | Result | Raw evidence |
|---|---|---|
| TDD regression before implementation | Failed as expected because `load_pack` did not raise `RegistrationRejected` | `F:\paralls-verification\thread-a\m5-5-process-kind-red-20261125-01\pytest.log` |
| Focused Validator and FactType registry tests | `118 passed, 2 warnings` | `F:\paralls-verification\thread-a\m5-5-process-kind-focused-20261125-01\pytest.log` |
| Frozen selection comparison | 5 selections, 1,169 nodes, all `problems=0 improvements=0` | `F:\paralls-verification\thread-a\m5-5-process-kind-gates-d02e8c73-20261125\gate-run.log` |
| Registered selection comparison | 25 manifests, 236 nodes, all `problems=0 improvements=0`; M5-5 selection has 15 nodes | Same directory, per-selection results |
| Current exact-commit backend suite | `10,639 passed, 23 failed, 2 skipped, 2 xfailed`, exit code 1; 10,666 collected | `F:\paralls-verification\thread-a\m5-5-process-kind-full-d02e8c73-20261125\full-console.log` and `full\results.json` |
| Parent full-suite comparison at `3a0e35b6` | 23 failure nodes matched with the same phase and error data. `test_recovery_owner_probe_measures_original_startup_before_full_oracle` failed in the parent run but passed at this commit. The prior isolated reruns also passed on `3a0e35b6` and `aa1f2507`, consistent with an intermittent test. The new `process_kind` regression passed in the full run. | `F:\paralls-verification\thread-a\m5-5-facttype-naming-full-3a0e35b6-20261125\full\results.json` and current full results |
| Runtime environment | Python 3.12.2, pytest 9.1.1, SQLite 3.43.1; `PYTHONPATH` targeted the A worktree and `app.__file__` resolved inside it | `full\environment.json`, `full\invocation.json`, and `full-console.log` in this run directory |

| Unit DoD | Status |
|---|---|
| U1, U2 | Not done. This compile-time validator slice does not declare Owners or migrate a domain. |
| U3 | Verified for the specific invalid `process_kind` combination. Process primitive support remains outside this slice. |
| U4–U8 | Not done. This slice does not change Resolver execution, Owner writes, readers, projections, or replay. |
| U9 | Focused, frozen and registered selections have zero differences. The full suite exited 1 with 23 failures, all matched to the parent by node, phase, and error data. |
| U10 | This evidence records commands, environments, raw outputs and remaining scope. |
| U11 | `docs/verification/selection/m5-5-facttype-refold.json` registers 15 M5-5 regression nodes at this commit. |

The exact-commit full suite remains non-green. This unit does not establish Process support, broader M5 completion or Architecture v2 completion.
