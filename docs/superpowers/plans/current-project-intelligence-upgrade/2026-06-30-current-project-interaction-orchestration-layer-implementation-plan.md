# 当前项目交互编排层实施计划

> 对应规格：
> [2026-06-29-current-project-interaction-orchestration-layer-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-interaction-orchestration-layer-design.md)

**状态：** `implemented-contract-slice-and-subsequent-orchestration-service-verified`

**实际核对：** 本 helper/contract slice 已落地；后续 `interaction-orchestration-service` profile 已通过，报告为 `.harness/verification/interaction-orchestration-service-report.json`。

**目标：** 用统一交互编排层代替“并行模式/协作模式”两套独立系统。

## 任务

- [x] 定义交互意图输入
- [x] 定义可用通道集合
- [x] 定义单通道与多通道协作策略
- [x] 定义结果合并策略
- [x] 明确其与 `ESM` 双通道世界作用层的交界
- [x] 设计 focused verifier，证明它不会重写角色智能体或司命主脑职责

## 产出

- 交互编排层协议
- 通道选择和协作规则
- 结果合并规则

## 执行证据

- 落地文件：
  - `backend/app/world_runtime/intelligence_upgrade.py`
  - `backend/tests/test_current_project_intelligence_upgrade.py`
- 验证：
  - `python -m pytest backend/tests/test_current_project_intelligence_upgrade.py::test_interaction_orchestration_selects_channels_without_becoming_a_new_brain -v`
  - `python scripts/verification/verify_current_project_intelligence_upgrade.py`
- 剩余风险：
  - 当前编排层是协议与轻量选择 helper，未接入实时物理系统。

## 后续子计划

完整 runtime service、route、channel execution plan 和结果合并层由后续子计划继续推进：

- [2026-07-02-current-project-interaction-orchestration-service-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-interaction-orchestration-service-implementation-plan.md)
