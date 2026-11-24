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
