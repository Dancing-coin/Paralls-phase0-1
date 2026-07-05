# 当前项目 Godot Sampling Production-Grade Providers 实施计划

> 对应规格：
> [2026-07-02-current-project-godot-sampling-production-grade-providers-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-02-current-project-godot-sampling-production-grade-providers-design.md)

**状态：** `implemented-and-runtime-verified`

**实际核对：** `godot-sampling-production-grade-providers` harness profile 已通过，报告为 `.harness/verification/godot-sampling-production-grade-providers-report.json`，覆盖六类 provider refs、status fields、PQF 消费和 no-heavy-work boundary。

**目标：** 将已有 sampling provider contract 和 L1 capture/ref 证明扩展为 production-grade Godot provider 体系，覆盖视觉、空间、听觉、身体、骨骼和环境 refs。

## 阶段 A：Provider Base Contract

目标文件建议：

- `scripts/character/ProviderSampleBase.gd`
- `backend/tests/test_godot_sampling_production_grade_providers.py`

任务：

- [x] 定义 provider sample status
- [x] 定义 retention/freshness/throttle/error fields
- [x] 定义 stable source refs

## 阶段 B：Visual/Spatial/Auditory/Embodied 完整化

目标文件建议：

- `scripts/character/VisualPatchProvider.gd`
- `scripts/character/SpatialPatchProvider.gd`
- `scripts/character/AuditoryContextProvider.gd`
- `scripts/character/EmbodiedStateProvider.gd`

任务：

- [x] visual capture artifact + camera pose
- [x] spatial obstacle/occlusion/passability refs
- [x] auditory source/window refs
- [x] embodied locomotion/grounded/failure refs
- [x] structured failure output

## 阶段 C：Skeletal/Environment refs 完整化

目标文件建议：

- `scripts/character/SkeletalStateProviderRefEmitter.gd`
- `scripts/character/EnvironmentFieldProvider.gd`

任务：

- [x] skeletal state provider refs 接入 `EmbodiedSkeletalStateProvider` / debug replay refs
- [x] environment field refs 输出 light/occlusion/hazard/passability/local field refs
- [x] skeletal refs 只暴露 high/mid-level refs 或 debug snapshot refs，不把 full bone payload 送入主链
- [x] environment refs 只表达局部环境场采样，不执行 heavy voxelization 或 full-scene runtime rescan
- [x] 两类 refs 均带 freshness/throttle/retention/failure status
- [x] 两类 refs 均可进入 `PerceptionQueryFrame`，不能直接写角色/司命 runtime

验收：

- spec 中 6 类 provider/ref 范围均有对应任务：visual、spatial、auditory、embodied、skeletal refs、environment refs
- skeletal/environment refs 可在 provider artifact report 中被单独观察
- skeletal full snapshot 只以 debug replay ref 形式出现
- environment field failure 可结构化表达，不阻塞 PQF 组装

## 阶段 D：PQF 与 Harness

目标文件建议：

- `scripts/verification/GodotSamplingProvidersProbe.gd`
- `scripts/verification/verify_godot_sampling_production_grade_providers.py`
- `.harness/profiles/godot-sampling-production-grade-providers.json`

任务：

- [x] 生成 provider artifact report
- [x] backend 消费 provider refs 组装 PQF
- [x] 证明 throttle 与 no-heavy-work
- [x] 证明 visual/spatial/auditory/embodied/skeletal/environment 六类输出均有 sample 或可验证 stub artifact
- [x] 接入 harness

验证命令：

```bash
python -m pytest -q backend/tests/test_godot_sampling_production_grade_providers.py
python scripts/verification/verify_godot_sampling_production_grade_providers.py
python scripts/verification/harness.py --profile godot-sampling-production-grade-providers
```

## 完成定义

完成后应能说：

> Godot sampling frontend 已从 contract/stub 变成 production-grade provider 体系，能稳定输出 visual、spatial、auditory、embodied、skeletal refs 和 environment refs，并进入 PQF，同时不承担重理解或重建模。
