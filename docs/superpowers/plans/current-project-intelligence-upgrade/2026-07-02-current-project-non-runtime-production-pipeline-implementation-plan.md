# 当前项目 Non-Runtime Production Pipeline 实施计划

> 对应规格：
> [2026-07-02-current-project-non-runtime-production-pipeline-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-02-current-project-non-runtime-production-pipeline-design.md)

**状态：** `implemented-and-verified`

**目标：** 将工具链 manifest 扩展为可运行的离线/半离线生产流水线，产出经过审核的 scene knowledge / spatial bake / replay dataset artifact。

## 阶段 A：Pipeline Skeleton

目标文件建议：

- `tools/production/scene_semantic_extractor.py`
- `tools/production/spatial_structure_baker.py`
- `tools/production/multimodal_semantic_classifier.py`
- `tools/production/scene_knowledge_generator.py`
- `tools/production/review_workbench.py`
- `tools/production/dataset_and_replay_builder.py`
- `backend/tests/test_non_runtime_production_pipeline.py`

任务：

- [x] 定义 pipeline manifest
- [x] 定义 draft/review/approved/rejected 状态
- [x] 定义 `SceneSemanticExtractor`
- [x] 定义 `SpatialStructureBaker`
- [x] 定义 `MultimodalSemanticClassifier`
- [x] 定义 `SceneKnowledgeGenerator`
- [x] 定义 `ReviewWorkbench`
- [x] 定义 `DatasetAndReplayBuilder`
- [x] 禁止 runtime private context 输入

验收：

- 六个生产模块均在 manifest 中注册
- 每个模块只消费离线/半离线 artifact refs，不读取角色/司命 runtime private context

## 阶段 B：Artifact Contract

任务：

- [x] scene semantic draft artifact
- [x] spatial bake artifact
- [x] multimodal classification artifact
- [x] affordance annotation artifact
- [x] replay/dataset artifact
- [x] review report

验收：

- draft artifact 必须进入 review gate
- multimodal classification 只能补充语义候选，不能直接成为 runtime truth
- replay/dataset artifact 可供 verifier 消费

## 阶段 C：Review Gate

任务：

- [x] approved artifact 才可作为 L1 seed
- [x] rejected artifact 不进入 runtime
- [x] review workbench 记录 reviewer/status/reason/source refs
- [x] dataset/replay builder 只消费 approved 或专门标记的 verification artifact
- [x] review evidence 落 `.harness/verification/`

验收：

- draft/review/approved/rejected 状态转换可追踪
- approved artifact 可被 L1 extractor 或 verifier 消费
- rejected draft 不进入 runtime 或 L1 seed

## 阶段 D：Verification

目标文件建议：

- `scripts/verification/verify_non_runtime_production_pipeline.py`
- `.harness/profiles/non-runtime-production-pipeline.json`

验证命令：

```bash
python -m pytest -q backend/tests/test_non_runtime_production_pipeline.py
python scripts/verification/verify_non_runtime_production_pipeline.py
python scripts/verification/harness.py --profile non-runtime-production-pipeline
```

已验证证据：

- `python -m pytest -q backend/tests/test_non_runtime_production_pipeline.py`
- `python scripts/verification/verify_non_runtime_production_pipeline.py`
- `python scripts/verification/harness.py --profile non-runtime-production-pipeline`
- `python scripts/verification/harness.py --profile docs`
- `python scripts/verification/harness.py --profile mainline-unified-runtime`
- `.harness/verification/non-runtime-production-pipeline-report.json`
- `.harness/verification/non-runtime-production-pipeline-report.md`

## 完成定义

完成后应能说：

> 非运行时生产工具链已具备 scene semantic extraction、spatial baking、multimodal classification、scene knowledge generation、review workbench 和 dataset/replay builder，能产出 draft/review/approved artifact，并把 approved 结果作为 L1/verification 种子，而不共享 runtime 私有上下文。
