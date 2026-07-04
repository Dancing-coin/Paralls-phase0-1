# 当前项目 Godot Sampling Production-Grade Providers 实施计划

> 对应规格：
> [2026-07-02-current-project-godot-sampling-production-grade-providers-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-02-current-project-godot-sampling-production-grade-providers-design.md)

**状态：** `planned`

**目标：** 将已有 sampling provider contract 和 L1 capture/ref 证明扩展为 production-grade Godot provider 体系，覆盖视觉、空间、听觉、身体、骨骼和环境 refs。

## 阶段 A：Provider Base Contract

目标文件建议：

- `scripts/character/ProviderSampleBase.gd`
- `backend/tests/test_godot_sampling_production_grade_providers.py`

任务：

- [ ] 定义 provider sample status
- [ ] 定义 retention/freshness/throttle/error fields
- [ ] 定义 stable source refs

## 阶段 B：Visual/Spatial/Auditory/Embodied 完整化

目标文件建议：

- `scripts/character/VisualPatchProvider.gd`
- `scripts/character/SpatialPatchProvider.gd`
- `scripts/character/AuditoryContextProvider.gd`
- `scripts/character/EmbodiedStateProvider.gd`

任务：

- [ ] visual capture artifact + camera pose
- [ ] spatial obstacle/occlusion/passability refs
- [ ] auditory source/window refs
- [ ] embodied locomotion/grounded/failure refs
- [ ] structured failure output

## 阶段 C：Skeletal/Environment refs 完整化

目标文件建议：

- `scripts/character/SkeletalStateProviderRefEmitter.gd`
- `scripts/character/EnvironmentFieldProvider.gd`

任务：

- [ ] skeletal state provider refs 接入 `EmbodiedSkeletalStateProvider` / debug replay refs
- [ ] environment field refs 输出 light/occlusion/hazard/passability/local field refs
- [ ] skeletal refs 只暴露 high/mid-level refs 或 debug snapshot refs，不把 full bone payload 送入主链
- [ ] environment refs 只表达局部环境场采样，不执行 heavy voxelization 或 full-scene runtime rescan
- [ ] 两类 refs 均带 freshness/throttle/retention/failure status
- [ ] 两类 refs 均可进入 `PerceptionQueryFrame`，不能直接写角色/司命 runtime

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

- [ ] 生成 provider artifact report
- [ ] backend 消费 provider refs 组装 PQF
- [ ] 证明 throttle 与 no-heavy-work
- [ ] 证明 visual/spatial/auditory/embodied/skeletal/environment 六类输出均有 sample 或可验证 stub artifact
- [ ] 接入 harness

验证命令：

```bash
python -m pytest -q backend/tests/test_godot_sampling_production_grade_providers.py
python scripts/verification/verify_godot_sampling_production_grade_providers.py
python scripts/verification/harness.py --profile godot-sampling-production-grade-providers
```

## 完成定义

完成后应能说：

> Godot sampling frontend 已从 contract/stub 变成 production-grade provider 体系，能稳定输出 visual、spatial、auditory、embodied、skeletal refs 和 environment refs，并进入 PQF，同时不承担重理解或重建模。
