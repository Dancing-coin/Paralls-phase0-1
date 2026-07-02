# 当前项目角色智能体多模态链与 `Actor Scene Knowledge` 实施计划

> 对应规格：
> [2026-06-29-current-project-character-multimodal-and-actor-scene-knowledge-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-character-multimodal-and-actor-scene-knowledge-design.md)

**目标：** 在心智核心已完成前提下，为角色智能体补齐多模态输入链、局部世界感知和场景知识层。

## 任务

- [x] 让角色专属多模态栈与 `Perception Query Frame` 对齐
- [x] 设计角色专属 Fusion 的输入输出
- [x] 定义 `Actor Scene Knowledge` 的结构、更新原则和与现有 memory/snapshot 的关系
- [x] 定义主动感知触发条件
- [x] 设计 focused proof，证明角色智能体不是重做心智核心，而是在其之上增强

## 产出

- 角色专属多模态链方案
- `Actor Scene Knowledge` 更新方案
- 主动感知闭环方案

## 执行证据

- 落地文件：
  - `backend/app/world_runtime/intelligence_upgrade.py`
  - `backend/tests/test_current_project_intelligence_upgrade.py`
- 验证：
  - `python -m pytest backend/tests/test_current_project_intelligence_upgrade.py::test_character_multimodal_stack_and_actor_scene_knowledge_extend_mind_core_without_rewriting_it -v`
  - `python scripts/verification/verify_current_project_intelligence_upgrade.py`
- 剩余风险：
  - 当前落地为角色私有多模态栈与 Actor Scene Knowledge 契约，未改写或重跑 character mind core。

## 后续子计划

完整角色私有 ASK store、冲突/新鲜度生命周期和主动感知闭环由后续子计划继续推进：

- [2026-07-02-current-project-actor-scene-knowledge-lifecycle-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-actor-scene-knowledge-lifecycle-implementation-plan.md)
