# 当前项目 Godot 取样前端与 Provider 实施计划

> 对应规格：
> [2026-06-29-current-project-godot-sampling-frontend-and-providers-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-godot-sampling-frontend-and-providers-design.md)

**状态：** `implemented-contract-slice-and-subsequent-godot-provider-runtime-verified`

**实际核对：** 本 sampling frontend slice 已落地；后续 `godot-sampling-production-grade-providers` profile 已通过，报告为 `.harness/verification/godot-sampling-production-grade-providers-report.json`。

**目标：** 把 `Godot` 明确升级为取样前端，而不是让它承担重理解。

## 任务

- [x] 设计 `Visual Patch Provider`
- [x] 设计 `Spatial Patch Provider`
- [x] 设计 `Auditory Context Provider`
- [x] 设计 `Embodied State Provider`
- [x] 明确按需、局部、节流原则
- [x] 设计 focused verifier，证明 Godot 不承担重推理和重体素化

## 产出

- 四类 Provider 方案
- 性能保护约束
- 与 `Perception Query Frame` 的接线关系

## 执行证据

- 落地文件：
  - `scripts/character/VisualPatchProvider.gd`
  - `scripts/character/SpatialPatchProvider.gd`
  - `scripts/character/AuditoryContextProvider.gd`
  - `scripts/character/EmbodiedStateProvider.gd`
  - `backend/app/world_runtime/intelligence_upgrade.py`
- 验证：
  - `python -m pytest backend/tests/test_current_project_intelligence_upgrade.py::test_godot_sampling_frontend_declares_four_sampling_only_providers -v`
  - `python scripts/verification/verify_current_project_intelligence_upgrade.py`
- 剩余风险：
  - 当前 provider 是采样协议前端，未做 Godot runtime 截图或音频采集实跑。

## 后续子计划

production-grade provider 体系、完整 runtime sample、failure/freshness/throttle 和 PQF harness 接线由后续子计划继续推进：

- [2026-07-02-current-project-godot-sampling-production-grade-providers-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-godot-sampling-production-grade-providers-implementation-plan.md)
