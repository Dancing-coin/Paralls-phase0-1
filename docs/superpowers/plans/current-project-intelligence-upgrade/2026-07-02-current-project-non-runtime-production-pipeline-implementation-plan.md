# 当前项目 Non-Runtime Production Pipeline 实施计划

> 对应规格：
> [2026-07-02-current-project-non-runtime-production-pipeline-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-02-current-project-non-runtime-production-pipeline-design.md)

**状态：** `planned`

**目标：** 将工具链 manifest 扩展为可运行的离线/半离线生产流水线，产出经过审核的 scene knowledge / spatial bake / replay dataset artifact。

## 阶段 A：Pipeline Skeleton

目标文件建议：

- `tools/production/scene_semantic_extractor.py`
- `tools/production/spatial_structure_baker.py`
- `tools/production/scene_knowledge_generator.py`
- `backend/tests/test_non_runtime_production_pipeline.py`

任务：

- [ ] 定义 pipeline manifest
- [ ] 定义 draft/review/approved/rejected 状态
- [ ] 禁止 runtime private context 输入

## 阶段 B：Artifact Contract

任务：

- [ ] scene semantic draft artifact
- [ ] spatial bake artifact
- [ ] affordance annotation artifact
- [ ] replay/dataset artifact
- [ ] review report

## 阶段 C：Review Gate

任务：

- [ ] approved artifact 才可作为 L1 seed
- [ ] rejected artifact 不进入 runtime
- [ ] review evidence 落 `.harness/verification/`

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

## 完成定义

完成后应能说：

> 非运行时生产工具链已能产出 draft/review/approved artifact，并把 approved 结果作为 L1/verification 种子，而不共享 runtime 私有上下文。
