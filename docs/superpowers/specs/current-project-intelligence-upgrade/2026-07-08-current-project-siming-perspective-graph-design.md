# 当前项目 Siming Perspective Graph v0.1 设计

- 日期：`2026-07-08`
- 状态：`proposed`
- 上位规格：
  - [2026-06-29-current-project-siming-multimodal-and-global-situation-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-siming-multimodal-and-global-situation-design.md)
  - [2026-07-02-current-project-siming-global-situation-layer-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-02-current-project-siming-global-situation-layer-design.md)
  - [2026-07-05-current-project-multi-actor-private-perspective-reconciliation-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-05-current-project-multi-actor-private-perspective-reconciliation-design.md)

## 1. 目标

`Siming Perspective Graph v0.1` 只解决两个近期问题：

1. 司命上下文压缩时不串记忆。
2. 司命可以读取不同角色的可见、可听、可知视角摘要。

它不是完整世界知识图谱，也不是图数据库落地计划。

它是一层司命私有的图谱化 read/projection layer，用来把公共世界事实、角色可感知投影、多模态 advisory、会话知识状态和故事节点投影成稳定摘要。

## 2. 当前问题

当前 `SimingRuntime` 已经有：

- `InMemorySimingStateTree`
- `InMemoryStorylineState`
- `NarrativeReadModel`
- `SimingGlobalSituationLayer`
- `siming_mm:*` 多模态隔离上下文

这些结构足以表达当前 tick 的运行态、全局态势和最小故事阶段，但不适合单独承担：

- 多角色不同视角之间的差异
- 某角色知道什么、错过什么、怀疑什么
- 某个故事节点依赖哪些事实或证据
- 某个事实来自 authority、L1 fact、VLA advisory 还是角色私有感知投影
- 压缩上下文时哪些内容应该进入司命摘要，哪些应该隔离

如果继续只用状态树承接故事线节点，状态树会被迫同时表达运行状态、角色视角、知识可见性和多模态证据来源，最终容易在压缩与回放时混淆。

## 3. 定位

`Siming Perspective Graph` 位于 `SimingGlobalSituationLayer` 之后、`NarrativeReadModel` 之前。

```text
Public L1 facts / authority events / world results
        +
character perspective read facade
        +
siming_mm:* bundle / VLA advisory global findings
        |
        v
SimingGlobalSituationLayer
        |
        v
Siming Perspective Graph
        |
        +--> compression summary
        +--> per-actor perspective summary
        +--> NarrativeReadModel enrichment
        +--> intervention candidate evidence refs
```

它不替代：

- `StateTreeSnapshot`
- `StorylineStateSnapshot`
- `SimingGlobalSituationSnapshot`
- `ActorSceneKnowledge`
- 角色私有 memory/cache

它补齐的是这些结构之间的可追踪关系。

## 4. v0.1 节点

v0.1 固定最小节点集合。

### 4.1 `Actor`

表示玩家投影角色、AI 角色或关键 NPC。

最小字段：

- `actor_id`
- `actor_kind`
- `room_id`
- `active_scene_id`

### 4.2 `Perspective`

表示某个 actor 在某个时间窗内的可见、可听、可知摘要。

最小字段：

- `perspective_id`
- `actor_id`
- `capture_root_id`
- `capture_id`
- `clock_domain`
- `monotonic_tick`
- `world_anchor_scope`
- `window_started_at`
- `window_ended_at`

### 4.3 `Fact`

表示已进入公共事实链或 authority 链的事实。

最小字段：

- `fact_id`
- `fact_type`
- `authority_level`
- `source_event_id`
- `causation_id`
- `correlation_id`
- `world_anchor_id`

`authority_level` 至少支持：

- `authority_confirmed`
- `l1_projected`
- `siming_inferred`
- `advisory_only`

### 4.4 `Percept`

表示角色视角或司命视角里的感知结果。

最小字段：

- `percept_id`
- `subject_actor_id`
- `target_ref`
- `source_kind`
- `certainty`
- `clarity`
- `private_scope`

`private_scope` 至少支持：

- `public`
- `actor_read_facade`
- `siming_private`

### 4.5 `ModalityEvidence`

表示多模态、VLA、视觉事实、听觉事实、环境 patch 或身体状态输入。

最小字段：

- `evidence_id`
- `modality`
- `source_kind`
- `capture_id`
- `world_anchor_id`
- `confidence`
- `advisory_only`
- `freshness`
- `conflict_refs`

`modality` 至少支持：

- `visual`
- `auditory`
- `spatial`
- `environment`
- `embodied`
- `skeletal`
- `vla_visual_spatial`

### 4.6 `KnowledgeClaim`

表示某 actor 对某信息的知识状态。

最小字段：

- `claim_id`
- `actor_id`
- `information_ref`
- `knowledge_state`
- `knowledge_source`
- `started_at`

`knowledge_state` 至少支持：

- `unknown`
- `missed`
- `suspected`
- `confirmed`
- `public`

### 4.7 `StoryBeat`

表示当前故事线节点或候选故事线节点。

最小字段：

- `story_beat_id`
- `beat_kind`
- `active_phase`
- `status`
- `pressure_level`
- `opened_at`
- `resolved_at`

`status` 至少支持：

- `candidate`
- `active`
- `blocked`
- `resolved`
- `stale`

## 5. v0.1 关系

v0.1 固定最小关系集合。

```text
Actor HAS_PERSPECTIVE Perspective
Perspective OBSERVED Fact
Perspective MISSED Fact
Perspective HEARD Fact
Perspective DID_NOT_HEAR Fact
Perspective CONTAINS_PERCEPT Percept
Fact SUPPORTED_BY ModalityEvidence
Fact CONFLICTS_WITH ModalityEvidence
Actor HOLDS KnowledgeClaim
StoryBeat DEPENDS_ON Fact
StoryBeat SUPPORTED_BY ModalityEvidence
StoryBeat VISIBLE_TO Actor
StoryBeat BLOCKED_FOR Actor
StoryBeat PRESSURES Actor
SimingIntervention TARGETS StoryBeat / Actor / Fact
```

## 6. 角色视角 read facade

司命不得读取角色私有多模态 cache、patch session、推理历史或完整 memory。

角色侧只向司命暴露 read facade：

- 当前 actor 可见事实摘要
- 当前 actor 可听事实摘要
- 当前 actor 已知、怀疑、错过的信息摘要
- 当前 actor 的主要 attention target
- 当前 actor 视角下的 object/actor/world_anchor refs
- 必要的 certainty、clarity、source refs

read facade 必须满足：

1. 不包含角色私有推理过程。
2. 不包含可复用的 raw multimodal patch cache。
3. 不包含其他角色的 private context。
4. 所有摘要都必须带 `capture_id / world_anchor_id / source_ref_lineage`。
5. 司命只能把它作为角色视角投影，不能把它当成全局真值。

## 7. 压缩摘要规则

司命上下文压缩不得直接拼接长历史文本。

压缩摘要必须从 `Siming Perspective Graph` 和 `NarrativeReadModel` 生成，至少包含：

1. 当前活跃 `StoryBeat`。
2. 每个关键 actor 的 `known / missed / suspected / confirmed` 摘要。
3. 当前主要视角差异。
4. 当前 authority-confirmed facts。
5. 当前 advisory-only 多模态结论。
6. 当前 unresolved conflicts。
7. 最近一次司命干预目标、路径和效果。

压缩摘要必须区分：

- `confirmed truth`
- `actor perspective`
- `siming inference`
- `advisory-only evidence`
- `unresolved conflict`

## 8. 与状态树的关系

状态树继续负责当前运行态：

- environment branch
- character branch
- storyline branch
- group simulation branch

`Siming Perspective Graph` 负责跨视角和跨故事节点关系：

- 谁看到什么
- 谁没看到什么
- 谁知道什么
- 哪个事实支撑哪个故事节点
- 哪个多模态证据只是 advisory
- 哪个角色视角缺口造成叙事或公平压力

因此 v0.1 不替换 `InMemorySimingStateTree`。

它只新增从状态树、全局态势、角色 read facade 和多模态 bundle 派生的图谱投影。

## 9. 与多模态链的关系

多模态链仍然保持现有边界：

- 事实链是主感知链。
- 多模态链是增强感知链。
- VLA 是视觉/空间 advisory slow path。
- `siming_mm:*` 与 `character_mm:*` 不共享 runtime context。

图谱只保存多模态输出的可审计摘要和引用，不保存 raw patch cache。

所有 `ModalityEvidence` 必须保留：

- `source_kind`
- `modality`
- `capture_id`
- `world_anchor_id`
- `confidence`
- `advisory_only`
- `conflict_refs`

## 10. 最小 API

v0.1 建议先定义内存实现和接口，不绑定图数据库。

```text
ingest_global_situation(snapshot) -> None
ingest_actor_perspective(actor_id, facade) -> None
ingest_modality_evidence(evidence) -> None
link_story_beat(beat, refs) -> None
build_actor_perspective_summary(actor_id) -> dict
build_compression_summary() -> dict
build_read_model_enrichment() -> dict
```

## 11. Verification 要求

最小验证必须覆盖：

1. 两个 actor 看到同一 `world_anchor_id`，但形成不同 `Perspective`。
2. actor A 观察到某 fact，actor B 缺失该 fact，压缩摘要不把 B 写成已知。
3. VLA advisory 支撑某 `StoryBeat`，但不会变成 `authority_confirmed`。
4. 司命能生成 per-actor perspective summary。
5. 司命压缩摘要能区分 confirmed truth、actor perspective、advisory evidence 和 unresolved conflict。
6. 图谱不读取或持有 `character_mm:*` private cache。
7. 现有 state tree 仍可独立生成 checkpoint。

## 12. 非目标

v0.1 不做：

- 图数据库选型
- 完整世界知识图谱
- 长期跨房间社交图谱
- 完整谎言传播模型
- 角色 memory 重写
- 角色私有上下文共享
- VLA 直接写 world truth
- 低层动作控制

## 13. 一句话收束

`Siming Perspective Graph v0.1` 的价值不是把司命升级成全知数据库，而是让司命在压缩上下文时有一层稳定的、可追踪的、多角色视角图谱：状态树继续管当前运行状态，图谱管谁从哪个视角知道什么，以及这些差异如何影响故事节点和司命干预。
