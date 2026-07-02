# 当前项目非运行时多模态工具链与生产工具链实施计划

> 对应规格：
> [2026-06-29-current-project-non-runtime-multimodal-tooling-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-non-runtime-multimodal-tooling-design.md)

**目标：** 把多模态能力从角色智能体私有能力扩展成也能服务审核、回放、建模注入和数据构建的工具链能力。

## 任务

- [x] 明确 `Non-Runtime Tool Stack`
- [x] 明确 `Non-Runtime Production Stack`
- [x] 设计 `Scene Semantic Extractor`
- [x] 设计 `Spatial Structure Baker`
- [x] 设计 `Multimodal Semantic Classifier`
- [x] 设计 `Scene Knowledge Generator`
- [x] 设计 `Review Workbench`
- [x] 设计 `Dataset and Replay Builder`

## 产出

- 两类非运行时多模态工具链方案
- 自动抽取 + 多模态识别 + 人工审核工作流
- 数据集和回放构建路线

## 执行证据

- 落地文件：
  - `backend/app/world_runtime/intelligence_upgrade.py`
  - `backend/tests/test_current_project_intelligence_upgrade.py`
- 验证：
  - `python -m pytest backend/tests/test_current_project_intelligence_upgrade.py::test_non_runtime_multimodal_tooling_uses_tool_contexts_and_review_only_human_role -v`
  - `python scripts/verification/verify_current_project_intelligence_upgrade.py`
- 剩余风险：
  - 当前落地为工具链 manifest 和上下文隔离契约，未实现真实资产处理或数据集构建流水线。

## 后续子计划

真实 scene semantic extraction、spatial baking、review gate 和 replay/dataset 生产流水线由后续子计划继续推进：

- [2026-07-02-current-project-non-runtime-production-pipeline-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-non-runtime-production-pipeline-implementation-plan.md)
