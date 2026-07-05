# 当前项目具身骨骼状态提供层实施计划

> 对应规格：
> [2026-06-29-current-project-embodied-skeletal-state-provider-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-embodied-skeletal-state-provider-design.md)

**状态：** `implemented-contract-slice-and-subsequent-skeletal-runtime-verified`

**实际核对：** 本 provider contract slice 已落地；后续 `embodied-skeletal-debug-replay` profile 已通过，报告为 `.harness/verification/embodied-skeletal-debug-replay-report.json`。

**目标：** 把本地身体/骨骼链掌握的骨骼空间真相抽象成稳定 Provider 层。

## 任务

- [x] 定义高层具身状态导出
- [x] 定义中层骨架参数导出
- [x] 定义低层骨骼快照导出
- [x] 明确哪些进入主感知链，哪些只进入调试/回放
- [x] 设计 focused verifier，证明这层不会把整副骨骼快照直接灌给后端角色智能体

## 产出

- 骨骼状态 Provider 层协议
- 三层导出边界
- 与 `Perception Query Frame` 和多模态链的关系

## 执行证据

- 落地文件：
  - `scripts/character/EmbodiedSkeletalStateProvider.gd`
  - `backend/app/world_runtime/intelligence_upgrade.py`
  - `backend/tests/test_current_project_intelligence_upgrade.py`
- 验证：
  - `python -m pytest backend/tests/test_current_project_intelligence_upgrade.py::test_embodied_skeletal_state_provider_excludes_low_level_snapshot_from_main_chain -v`
  - `python scripts/verification/verify_current_project_intelligence_upgrade.py`
- 剩余风险：
  - 当前未绑定真实 `Skeleton3D` runtime；低层骨骼快照只以 debug/replay ref 边界落地。

## 后续子计划

真实骨骼 runtime 绑定、中层参数导出和低层 debug replay pipeline 由后续子计划继续推进：

- [2026-07-02-current-project-embodied-skeletal-debug-replay-pipeline-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-embodied-skeletal-debug-replay-pipeline-implementation-plan.md)
