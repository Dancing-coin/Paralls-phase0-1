# 当前项目司命多模态链与全局态势理解实施计划

> 对应规格：
> [2026-06-29-current-project-siming-multimodal-and-global-situation-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-siming-multimodal-and-global-situation-design.md)

**状态：** `implemented-contract-slice-and-subsequent-global-situation-verified`

**实际核对：** 本 contract slice 已落地；后续 `siming-global-situation-layer` profile 已通过，报告为 `.harness/verification/siming-global-situation-layer-report.json`。

**目标：** 为司命建立专属多模态栈、专属融合链和全局态势理解能力。

## 任务

- [x] 定义司命专属多模态输入窗口与 patch 范围
- [x] 定义司命专属 Fusion
- [x] 定义司命版感知包
- [x] 明确其与 `FairnessStateSnapshot`、干预候选、工作台解释的关系
- [x] 设计 focused verifier，证明司命多模态不污染角色多模态上下文

## 产出

- 司命专属多模态链
- 司命专属感知包
- 与公平快照/催化链的接线方案

## 执行证据

- 落地文件：
  - `backend/app/world_runtime/intelligence_upgrade.py`
  - `backend/tests/test_current_project_intelligence_upgrade.py`
- 验证：
  - `python -m pytest backend/tests/test_current_project_intelligence_upgrade.py::test_siming_multimodal_stack_enhances_fairness_without_polluting_character_context -v`
  - `python scripts/verification/verify_current_project_intelligence_upgrade.py`
- 剩余风险：
  - 当前未接入真实司命多模态模型，只固定司命上下文隔离、全局态势输入窗口和公平快照增强关系。

## 后续子计划

完整司命多角色全局 patch、fusion、situation lifecycle 和 intervention evidence 接线由后续子计划继续推进：

- [2026-07-02-current-project-siming-global-situation-layer-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-siming-global-situation-layer-implementation-plan.md)
