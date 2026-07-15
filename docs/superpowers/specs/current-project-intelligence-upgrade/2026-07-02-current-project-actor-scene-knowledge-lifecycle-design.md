# 当前项目 Actor Scene Knowledge Lifecycle 子规格

- 日期：`2026-07-02`
- 状态：`implemented-and-verified`
- 上位规格：[2026-06-29-current-project-character-multimodal-and-actor-scene-knowledge-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-character-multimodal-and-actor-scene-knowledge-design.md)

## 1. 目标

把已有 `Actor Scene Knowledge` 契约补全为角色私有的 knowledge lifecycle layer。

它负责让角色在现有 `CharacterAgentRuntime` 内部拥有可更新、可冲突、可过期、可回查的局部场景知识，而不是只在 bundle ingestion 时临时使用碎片事实。

## 2. 定位

`Actor Scene Knowledge Lifecycle` 是角色私有知识生命周期层，不是新的角色主脑或新的 runtime 宿主。

它消费：

- `CanonicalPerceptBundle`
- L1 projected facts
- VLA advisory results
- interaction/world failure results
- embodied failure signals
- active perception results

它输出：

- private world snapshot enrichment
- working memory structured context
- actor-local scene knowledge entries
- active perception requests
- conflict and freshness metadata

它不得：

- 写 world truth
- 覆盖 L1 facts
- 替代 character mind core
- 读取司命私有上下文
- 读取其他角色私有 patch cache

## 3. 核心对象

建议对象：

```text
ActorSceneKnowledgeStore
ActorSceneKnowledgeEntry
ActorSceneKnowledgeRevision
ActorSceneKnowledgeConflict
ActorSceneKnowledgeFreshness
ActivePerceptionRequest
ActivePerceptionResult
```

entry 至少包含：

- actor id
- subject ref
- knowledge type
- source refs
- confidence
- freshness
- first_seen_at
- last_confirmed_at
- expires_at
- conflict refs
- revision history ref
- advisory/world-truth boundary marker

## 4. 生命周期

知识更新必须支持：

- add new
- hit existing
- revise existing
- mark stale
- record conflict
- resolve conflict
- expire
- request recheck

不能简单覆盖已有知识。低置信或 advisory 来源只能修正主观知识，不能改写 L1/world truth。

## 5. 主动感知闭环

角色可以从以下条件触发 active perception：

- VLA/L1 冲突
- expected target missing
- expected reachable but failed
- stale knowledge before high-risk action
- low confidence target visibility
- repeated interaction failure
- embodied reachability failure

active perception 输出必须重新进入 `PerceptionQueryFrame`，不能绕过 Godot/L1 provider 体系。

## 6. 持久化边界

第一阶段可用内存 store + trace artifact。

后续持久化必须满足：

- 按 actor 隔离
- 按 session/scene 分区
- 支持 TTL 和 revision compaction
- 不保存 raw image/audio payload
- 只保存 refs、摘要、结构化结论和来源

## 7. Verification 要求

必须证明：

- bundle ingestion 可产生或更新 ASK entry
- advisory 结果不会覆盖 L1
- stale/expired/conflicted 状态可被表达
- active perception request 可回到 PQF
- 角色之间 store 隔离
- 司命不能读取角色私有 ASK store

## 8. 一句话收束

`Actor Scene Knowledge Lifecycle` 是角色自己的局部场景知识生命周期层：它把 bundle、失败、VLA advisory 和主动感知统一收束为可追踪、可冲突、可过期的角色主观知识。
