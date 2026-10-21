# 第二阶段剩余验收实施计划

> 执行：按任务推进，代码修复遵循 systematic-debugging / test-driven-development；完成声明遵循 verification-before-completion。

**Goal:** 分开审查 A-Cognition 与 A-Embodied，固定四角色评估来源和前置合同，确认 dialogue 调度失败并取得新鲜回归证据。

**Architecture:** 复用既有 CharacterMindFrame、CandidateCompiler、L3/L4、CharacterExecutionContract 和 execution owner/activation lease。隔离评估入口只审计输入与证据，不提供新 owner 或 runtime registry。三类架构图沿用 `docs/10月分析/审查/05-第三项阿博评估档案与四角色夹具.md` §6；本计划不改变这些模块边界。

**Tech Stack:** Python、pytest、既有 Harness、YAML/JSON。

**Spec:** 本轮用户验收指令；`docs/10月分析/规格/05-角色能力图谱、认知包络与动态算力规格.md`；计划01 Task1C、计划02 Task1–3/6。

## 约束与判定

- 保留工作区既有改动，直接在当前工作区执行，不提交或重置用户文件。
- 不重复五种 Laya live negative，不执行三项禁止近战动作，不开启 B/C、玩法包、编辑器、自走棋、AD/Blender/GLB。
- 无合法 target 的题不进入动作选择质量分母；零分母不是通过。
- 没有来源的阿博数值、policy 和 gold 不猜填；教师、旧 L3、慢模型不是自动真值。
- final 必须晚于完整 policy/候选/题目/阈值冻结；缺前置项时保留 blocked，不读取 final labels。
- 原始 Harness 证据显式导出仓库外，保留用户已有产物，只清理本轮拥有的资源。

## Task 1：四角色来源冻结与评估合同

责任：`backend/tests/fixtures/character_evaluation/`、`backend/tests/test_character_evaluation_fixtures.py`、新 `backend/tests/test_character_laya_evaluation_contract.py`、新 `scripts/verification/verify_character_laya_evaluation.py`。

- [ ] 核对 a/b/c 正式来源、d 隔离来源和 provider/checkpoint/artifact pins；按内容摘要固定。
- [ ] 先写来源篡改、跨 split 泄漏、无 target 分母、零样本门和 final 隔离的 failing tests。
- [ ] 实施最小评估前置审计；按两轨独立记录 controlled error 与 seed。
- [ ] 明确 frozen frame、U/P、acceptable set、cap/policy、split、阈值和校准的缺失项。
- [ ] 仅满足前置时运行 development/calibration，冻结后运行 final/独立 holdout；否则逐项 blocked，微调不触发。

## Task 2：dialogue 根因与受控调度修复

责任：`backend/app/main.py` dialogue waiting loop、`backend/tests/test_character_dialogue_streaming.py`；仅必要时触及现有 dialogue/lease 模块。

- [ ] 新鲜全量 pytest 保存完整输出；失败取得完整 traceback，通过则保留历史失败和受控复现的区别。
- [ ] 追踪 activation conflict、lease release、non-player 判断、requeue/accept 的 owner 调度顺序。
- [ ] 确认竞态后先做确定性 failing regression，覆盖正常 background/Siming 与 foreground 拒绝对照。
- [ ] 最小修复同一 owner/lease 合同，保持正常 background behavior；若无法复现则 flaky/unverified。

## Task 3：验收、子门报告与清理

责任：审查05冻结状态、审查03阶段状态、新本轮验收报告；不重写历史证据。

- [ ] 运行四角色 focused、CandidateCompiler/L3/L4、dialogue regression。
- [ ] 修复完成后运行完整 `python -m pytest -v`，不以单项通过替代 full gate。
- [ ] 运行 `model-provider-readiness`、`embodied-interaction-contracts`、`character-behavior-evaluation`、`character-policy-calibration`；这些既有 profiles 不证明正式四角色质量或 Laya embodied 链。
- [ ] 检查代码 diff 与本轮报告；记录 .harness 实际内容及 cleanup，保留既有用户产物。
- [ ] 分别报告 A-Cognition、A-Embodied、calibration/final/holdout、dialogue、pytest 与仍关闭范围。

## 执行记录

- 初查：calibration/final 空、policy 未冻结、参考动作未注册；不能把已有 fixture 描述视为已物化题目。
- 初查：正式四角色认知/compute 数值来源不完整；冻结的是已知来源，不能将通用 runtime 默认值称 authored cap。
- 首轮全量正在运行；修改被测源码前先完成该轮采集。原始输出位于本轮系统临时目录。
