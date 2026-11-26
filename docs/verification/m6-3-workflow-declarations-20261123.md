# M6-3 Workflow 声明校验

依据 11-22 迁移计划 M6-3、《组合总纲》第五、七、九节和《跨域结算》第六至八节。

定向和选集运行在 `d40ddff891d71e24a60abf6d383fbf5aa4190685`。主分支代码提交为 `9eb80fe9ea91a6b53515a70c8e1c34a068d75d29`，Workflow 模块、测试和该提交的加载器与独立验证提交逐文件一致。

- `backend/app/gameplay/l5_workflow.py` 编译不可变步骤，保留依赖、拒绝、失败、超时和开放义务的恢复策略。拒绝直接写入、未知命令、未知依赖和依赖环。
- `backend/app/gameplay/rule_pack_validator.py` 从正常的规则包加载入口编译 `workflows`，用解析后的命令目录验证引用。
- `backend/tests/test_l5_workflow.py` 覆盖声明、错误路径和实际规则包加载。新增节点登记到 `docs/verification/selection/m6-3-workflow.json`。
- `docs/v2-coordination/BOUNDARIES.md` 和 `PROTOCOL.md` 登记源码与测试归属。

《组合总纲》补给例的 `reserve` 继承默认超时策略 `record_obligation`，恢复表未列该步骤。按《跨域结算》的义务恢复要求，当前编译器要求每个可打开义务的步骤声明恢复动作。接入该样例需要补 `reserve` 的恢复声明或覆盖其超时动作。

## Current-tip revalidation, 2026-11-27

At A tip `8ff452c7`, the focused Workflow, RulePack Validator, Reaction and Play Pattern command returned **162 passed, 2 warnings** under Python 3.12.2 with the A-worktree `PYTHONPATH` and explicit F-drive pytest basetemp.

| Selection | Current-tip result | Raw output |
|---|---|---|
| M6-3 Workflow, 8 nodes | `selected=8 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m6-3-current-tip-20261127-01\workflow\` |
| ownership, 24 nodes | `selected=24 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m6-3-current-tip-20261127-01\ownership\` |
| shared-replay, 990 nodes | `selected=990 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m6-3-current-tip-20261127-01\shared-replay\` |

No code changed in this revalidation. Production workflow execution, durable obligation recovery, Gateway activation, UE transport and complete siege execution remain unverified. The current-tip full backend suite was not rerun. M6-3 remains `待门禁`.

## 已验证

Python 3.12.2，SQLite 3.43.1。定向测试和选集使用 `F:/codex-temp/a-m6-2-8cb4ecca/backend`，已核验 `app.__file__`。

- 新模块实现前使用 `python -m pytest -q -p no:cacheprovider backend/tests/test_l5_workflow.py`，为一个模块未建立的收集错误，退出 2。见 `F:/paralls-verification/thread-a/w-8cb4ecca/red.txt`。
- `python -m pytest -q -p no:cacheprovider backend/tests/test_l5_workflow.py backend/tests/test_rule_pack_validator.py backend/tests/test_l5_reaction.py backend/tests/test_l5_play_pattern.py` 为 129 passed、2 warnings，退出 0。见 `F:/paralls-verification/thread-a/w-8cb4ecca/targeted.txt`。
- 在 `d40ddff8` 上使用 `run_baseline.py --repo <worktree> --output <run>/workflow --test tests/test_l5_workflow.py` 为 8 passed、2 warnings，退出 0。以该次记录登记节点。
- `compare_selection.py --repo <worktree> --selection <selection.json> --output <run>/<selection>` 运行冻结五组 1,169 节点和登记十四组 115 节点。19 组各自为 `problems=0 improvements=0`，退出 0。日志位于 `F:/paralls-verification/thread-a/s-e9633135/`。
- 主分支 `9eb80fe9` 使用 `run_baseline.py --repo <worktree> --output <run>/full --freeze` 串行全量，10,558 collected，`24 failed, 10530 passed, 2 skipped, 2 xfailed, 239 warnings in 1410.86s`，退出 1。运行期间 HEAD 和源码哈希固定。与 Pipeline 的 `abfe1443` 按节点、阶段及错误类型比较，新增 0、恢复 0。相对冻结 22 项多出的仍为 `test_cold_ready` 的 KeyError 与 `test_recovery_owner_probe_measures_original_startup_before_full_oracle` 的 AssertionError。原始日志、环境与两份比较文件在 `F:/paralls-verification/thread-a/w-300a2166/`。SQLite 两项 WAL checkpoint 测试因版本跳过，未验证。

## 仅静态检查与未实施

`AppendDerivedSettlementRecipe.receipt_from_append_result` 可从已发生的一次追加取得 `SettlementReceipt`。耐久 EventStore 通过 `append_batch` 持久化成功事务的幂等结果；拒绝分支提前返回。Workflow 重建还需从 Gateway 审计或权威义务记录关联工作流版本、实例、步骤、拒绝和未知结果。结算未知时应查原幂等键，不能用缺失的回执推导出未执行。见 H-A-013。

| DoD | 状态 |
|---|---|
| U1、U2、U3 | 本切片无域迁移、新 Owner、FactType 或持久事件类型 |
| U4 | 已验证复用规则包加载器与命令目录 |
| U5 | 生产工作流执行、义务落地及重建未做 |
| U6 | 加载有专项测试，生产读取点仅静态核对 |
| U7 | 生产可见性路径未做 |
| U8 | 规则包声明和命令引用已验证 |
| U9 | 已验证 C5；C7 的可丢可重建与 Demo 探针未做 |
| U10、U11 | 本文件记录边界与验证程序；八个节点登记到选集 |
