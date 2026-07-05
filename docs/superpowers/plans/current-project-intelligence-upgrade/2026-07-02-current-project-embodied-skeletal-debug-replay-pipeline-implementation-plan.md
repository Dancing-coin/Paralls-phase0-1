# 当前项目 Embodied Skeletal Debug Replay Pipeline 实施计划

> 对应规格：
> [2026-07-02-current-project-embodied-skeletal-debug-replay-pipeline-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-02-current-project-embodied-skeletal-debug-replay-pipeline-design.md)

**状态：** `implemented-and-runtime-verified`

**实际核对：** `embodied-skeletal-debug-replay` harness profile 已通过，报告为 `.harness/verification/embodied-skeletal-debug-replay-report.json`，Godot runtime 状态为 `godot-runtime-binding-verified`，并证明 full-bone 不进入主链。

**目标：** 绑定真实 `Skeleton3D`/角色身体 runtime，补齐中层骨架参数导出和低层 debug replay artifact pipeline。

## 阶段 A：Runtime Binding

目标文件建议：

- `scripts/character/EmbodiedSkeletalStateProvider.gd`
- `scripts/verification/EmbodiedSkeletalRuntimeProbe.gd`
- `backend/tests/test_embodied_skeletal_debug_replay_pipeline.py`

任务：

- [x] 绑定 `Skeleton3D` / `CharacterReplica`
- [x] 生成 high-level embodied state
- [x] 生成 mid-level skeletal parameters：
  - anchor refs
  - facing vectors
  - reach envelope
  - balance/strain hints
  - hand readiness
  - contact candidate refs
  - pose feature tags
- [x] 输出 main perception payload
- [x] Godot editor/runtime probe 验证目标场景中存在真实 `Skeleton3D` binding

验收：

- 静态 backend/schema 测试不能单独满足 runtime binding 完成口径
- 必须有 Godot editor 或 runtime probe 证明 provider 绑定真实 `Skeleton3D` / `CharacterReplica`
- high-level embodied state 和 mid-level skeletal parameters 可进入 PQF
- mid-level skeletal parameters 必须覆盖 anchor/facing/reach/balance/hand/contact/pose tags
- full bone payload 不进入 main backend chain
- 如果 Godot 不可用，报告状态必须标为 `godot-runtime-binding-unverified`

## 阶段 B：Debug Replay Artifact

任务：

- [x] 生成 low-level snapshot ref
- [x] 写 `.harness/verification/skeletal-replay-*.json`
- [x] 记录 retention `debug_replay_only`
- [x] 关联 PQF/bundle/failure trace
- [x] snapshot refs 可与 failure trace 对齐

验收：

- low-level full snapshot 只进入 debug replay / verification artifact / offline diagnosis
- debug replay artifact 包含 actor id、skeleton source ref、bone count、timestamp、retention 和 trace refs

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

验证报告必须区分：

- `backend-contract-verified`
- `godot-runtime-binding-verified`
- `debug-replay-artifact-verified`
- `full-bone-main-chain-exclusion-verified`

## 完成定义

完成后应能说：

> 具身骨骼 provider 已绑定真实 runtime，主链只消费高/中层状态，低层骨骼快照以 debug replay artifact 形式可追踪地落盘。

如果缺少 Godot probe，只能说：

> 具身骨骼 debug replay 协议和 artifact 链路已写入计划或静态验证；真实 `Skeleton3D` runtime binding 尚未完成 Godot 验证。
