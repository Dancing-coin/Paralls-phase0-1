# 当前项目 `ESM` 双通道世界作用层实施计划

> 对应规格：
> [2026-06-29-current-project-esm-dual-channel-world-actuation-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-esm-dual-channel-world-actuation-design.md)

**状态：** `implemented-contract-slice-and-subsequent-physical-channel-runtime-verified`

**实际核对：** 本 dual-channel contract slice 已落地；后续 `esm-physical-channel-world-actuation` profile 已通过，报告为 `.harness/verification/esm-physical-channel-world-actuation-report.json`。

**目标：** 在保留当前语义结算能力的同时，为未来物理驱动交互预留并建立世界作用双通道。

## 任务

- [x] 定义 `Semantic Interaction Channel` 的保留边界
- [x] 定义 `Physical Interaction Channel` 的引入边界
- [x] 定义统一结果协议和回流规则
- [x] 明确哪些玩法走语义主导、哪些玩法走物理主导、哪些走混合
- [x] 设计 focused proof，证明双通道不会撕裂世界状态底座

## 产出

- 双通道世界作用层边界
- 统一结果与回流协议
- 与 `Interaction Orchestration Layer` 的关系

## 执行证据

- 落地文件：
  - `backend/app/world_runtime/intelligence_upgrade.py`
  - `backend/tests/test_current_project_intelligence_upgrade.py`
- 验证：
  - `python -m pytest backend/tests/test_current_project_intelligence_upgrade.py::test_esm_dual_channel_manifest_keeps_one_world_result_protocol -v`
  - `python scripts/verification/verify_current_project_intelligence_upgrade.py`
- 剩余风险：
  - 当前落地为双通道 manifest 和统一结果族约束，未实现连续物理接触 runtime。

## 后续子计划

完整 physical channel runtime、连续接触、推拉/携带和 mixed result 回流由后续子计划继续推进：

- [2026-07-02-current-project-esm-physical-channel-world-actuation-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-esm-physical-channel-world-actuation-implementation-plan.md)
