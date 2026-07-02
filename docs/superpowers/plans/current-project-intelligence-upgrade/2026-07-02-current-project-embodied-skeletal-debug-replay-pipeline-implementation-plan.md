# 当前项目 Embodied Skeletal Debug Replay Pipeline 实施计划

> 对应规格：
> [2026-07-02-current-project-embodied-skeletal-debug-replay-pipeline-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-02-current-project-embodied-skeletal-debug-replay-pipeline-design.md)

**状态：** `planned`

**目标：** 绑定真实 `Skeleton3D`/角色身体 runtime，补齐中层骨架参数导出和低层 debug replay artifact pipeline。

## 阶段 A：Runtime Binding

目标文件建议：

- `scripts/character/EmbodiedSkeletalStateProvider.gd`
- `backend/tests/test_embodied_skeletal_debug_replay_pipeline.py`

任务：

- [ ] 绑定 `Skeleton3D` / `CharacterReplica`
- [ ] 生成 high-level embodied state
- [ ] 生成 mid-level skeletal parameters
- [ ] 输出 main perception payload

## 阶段 B：Debug Replay Artifact

任务：

- [ ] 生成 low-level snapshot ref
- [ ] 写 `.harness/verification/skeletal-replay-*.json`
- [ ] 记录 retention `debug_replay_only`
- [ ] 关联 PQF/bundle/failure trace

## 阶段 C：Verification

目标文件建议：

- `scripts/verification/verify_embodied_skeletal_debug_replay_pipeline.py`
- `.harness/profiles/embodied-skeletal-debug-replay.json`

验证命令：

```bash
python -m pytest -q backend/tests/test_embodied_skeletal_debug_replay_pipeline.py
python scripts/verification/verify_embodied_skeletal_debug_replay_pipeline.py
python scripts/verification/harness.py --profile embodied-skeletal-debug-replay
```

## 完成定义

完成后应能说：

> 具身骨骼 provider 已绑定真实 runtime，主链只消费高/中层状态，低层骨骼快照以 debug replay artifact 形式可追踪地落盘。
