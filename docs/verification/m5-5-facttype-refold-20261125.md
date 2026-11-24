# M5-5 FactType distribution refold requirement

Date: 2026-11-25

## Scope and implementation

Implement the formal validator rule `facttype_refold_missing`: a FactType declaring `aggregation: distribution` must name a nonempty `refold_model_ref`. The implementation is in `backend/app/gameplay/fact_type_registry.py`; the regression is in `backend/tests/test_rule_pack_validator.py`.

This is a compile-time registration check. It does not change event schemas, persisted event payloads, Owner classification, Resolver behavior, or distribution execution. It closes only this validator rule and does not claim M5 or Architecture v2 completion.

## Environment

- Base commit: `f5cc36326d144aad78752073ae3fc819dd8ccc9d`.
- Implementation commit: `f0c9108dc715869f73b6a919e3fd674f87292b4c`.
- Interpreter: Python 3.12.2 (`D:\Temp\paralls-g0-py312\Scripts\python.exe`); pytest 9.1.1.
- `PYTHONPATH` pointed to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`; `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- A post-run environment check with the same interpreter and `PYTHONPATH` reported SQLite 3.43.1.

## Verification

| Check | Result | Raw evidence |
|---|---|---|
| TDD regression before implementation | Failed because `load_pack` did not raise `RegistrationRejected` | `F:\paralls-verification\thread-a\m5-5-facttype-refold-red-20261125-01\` |
| Focused command: `backend/tests/test_rule_pack_validator.py backend/tests/test_pool_runtime.py` | `120 passed, 2 warnings` | `F:\paralls-verification\thread-a\m5-5-facttype-refold-20261125-01\pytest-focused.log` |
| Frozen selection comparison | 5 selections, 1,169 nodes, `problems=0 improvements=0` | `F:\paralls-verification\thread-a\m5-5-refold-gates-20261125-01\` |
| Registered selection comparison | 25 selections, 222 nodes, `problems=0 improvements=0` | Same directory; per-selection `results.json`, invocation records, and `summary.txt` |
| Full backend suite at implementation commit | `10,624 passed, 24 failed, 2 skipped, 2 xfailed`, exit code 1; 10,652 collected | `F:\paralls-verification\thread-a\m5-5-facttype-refold-full-20261125-f0c9108d\full-console.log` and `full\junit.xml` |
| Failed-node comparison at parent commit | The same 24 failed node IDs, phases, and error types; `new=0 parent_extra=0` | `F:\paralls-verification\thread-a\m5-5-facttype-refold-parent-20261125-03\parent-console.log` and `parent-failing-nodes\junit.xml` |

Selection comparison used the frozen manifests under `docs/verification/absorb-main-3bf3418e/` and all 25 files under `docs/verification/selection/`. The comparison metrics were checked from the retained per-batch `results.json` against those manifests. Every selected node passed in the current run. The full-suite result is a nonzero exit and is not reported as a passing full suite. Parent comparison reran the 24 failing node IDs only, not the full suite.

## Unit DoD status

| Item | Status |
|---|---|
| U1 | 未做。本单元不声明或迁移 Owner。 |
| U2 | 未做。本单元不新增 Owner schema。 |
| U3 | 部分验证。仅校验 distribution FactType 缺少 refold 引用时被拒绝。 |
| U4 | 未做。本单元不改变 Resolver 合同。 |
| U5 | 未做。本单元不改变 Owner 提交或持久事件。 |
| U6 | 未做。本单元不改变读取方。 |
| U7 | 未做。本单元不改变投影更新。 |
| U8 | 未做。本单元不改变 replay 或 checkpoint 重建。 |
| U9 | 已运行定向测试、冻结及登记选择集，并运行全量。全量退出码为 1，24 个失败在父提交复现。 |
| U10 | 本证据文件记录了命令结果、环境、原始输出位置和未覆盖项。 |
| U11 | 已登记 `docs/verification/selection/m5-5-facttype-refold.json`，1 个回归节点。 |

## Remaining work and unverified scope

- Other rows in `m5-5-rule-pack-validator-coverage-20261122.md` retain their recorded states. Production command registration, temporal-effect contracts, package-version write boundaries, and cross-boundary application wiring are outside this rule.
- The full suite did not pass. The parent comparison establishes that this unit added no new failures among the 24 failing nodes, but it does not convert the full-suite exit code to success.
- This evidence does not establish M5 or Architecture v2 completion.
