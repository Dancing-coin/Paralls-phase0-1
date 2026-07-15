# 当前项目 Embodied Skeletal Debug Replay Pipeline 子规格

- 日期：`2026-07-02`
- 状态：`implemented-and-runtime-verified`
- 上位规格：[2026-06-29-current-project-embodied-skeletal-state-provider-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-embodied-skeletal-state-provider-design.md)

## 1. 目标

把已有三层 skeletal provider contract 补全为中层参数 runtime 导出和低层 debug replay pipeline。

## 2. 边界

主感知链只能消费：

- high-level embodied state
- mid-level skeletal parameters
- debug snapshot refs

低层完整骨骼快照只进入：

- debug replay
- verification artifact
- offline diagnosis

不得把 full bone snapshot 直接灌入 backend 角色心智或业务决策层。

## 3. 中层参数

中层参数应包含：

- anchor refs
- facing vectors
- reach envelope
- balance/strain hints
- hand readiness
- contact candidate refs
- pose feature tags

## 4. Debug Replay

debug replay artifact 应包含：

- actor id
- skeleton source ref
- bone count
- sampled timestamp
- redacted/full retention policy
- replay-only storage path
- associated PQF/bundle/interaction trace refs

## 5. Verification 要求

必须证明：

- high/mid-level state 进入 PQF
- low-level snapshot 只进入 debug replay
- snapshot refs 可与 failure trace 对齐
- full bone payload 不进入 main backend chain

## 6. 一句话收束

该 pipeline 让骨骼空间真相可调试、可回放、可定位失败，同时保持主感知链只消费高/中层摘要。
