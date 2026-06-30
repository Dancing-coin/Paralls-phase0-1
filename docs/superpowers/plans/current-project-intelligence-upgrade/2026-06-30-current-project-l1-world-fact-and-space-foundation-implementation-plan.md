# 当前项目 `L1` 世界事实层与空间底座实施计划

> 对应规格：
> [2026-06-29-current-project-l1-world-fact-and-space-foundation-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-l1-world-fact-and-space-foundation-design.md)

**目标：** 把当前 `L1` 从 emitter 集合提升为真正的世界事实层，并引入静态空间底稿与动态空间占据层。

## 任务

- [x] 明确 `Scene 3D Space Model` 的对象类型、来源和抽取方式
- [x] 明确 `Runtime Spatial Occupancy Field` 的静态/动态分工
- [x] 补齐环境、遮挡、可达性、对象可供性和失败/负事实的事实上抛器族清单
- [x] 定义 `Fact Projection Layer` 与现有 emitter 的关系
- [x] 设计 focused verifier，证明 `L1` 新底座不会拖累当前运行时

## 产出

- `L1` 空间底座对象族
- 新事实上抛器族清单
- 静态离线 + 动态增量更新策略

## 执行证据

- 落地文件：
  - `backend/app/world_runtime/intelligence_upgrade.py`
  - `backend/tests/test_current_project_intelligence_upgrade.py`
- 验证：
  - `python -m pytest backend/tests/test_current_project_intelligence_upgrade.py::test_l1_world_fact_and_space_foundation_models_static_and_dynamic_space_without_runtime_rescan -v`
  - `python scripts/verification/verify_current_project_intelligence_upgrade.py`
- 剩余风险：
  - 当前未实现离线空间烘焙器，只固定可计算对象族、抽取来源和运行时禁做重扫描边界。
