# 10-数据 Schema、事件契约与调试回放

## 1. 文档目标

本文档冻结角色智能体系统在数据层的核心对象、事件契约与最小回放链。

## 2. 核心对象

建议固定 12 个一级对象：

1. `CharacterProfile`
2. `CharacterRuntimeState`
3. `PrivateWorldSnapshot`
4. `PerceivedEvent`
5. `EventMemoryItem`
6. `ObservationMemoryItem`
7. `KnowledgeMemoryItem`
8. `SocialMemoryItem`
9. `HigherOrderMemoryItem`
10. `BeliefUpdateDelta`
11. `IntentPacket`
12. `ExecutionPacket`

## 3. 角色运行态

运行态应至少维护：

- 主导情绪与情绪向量
- 压力与紧迫感
- 信任/怀疑运行时修正
- 身体异常 flags
- 疲劳
- 当前注意力状态
- 当前会话运行态
- autonomy mode

## 4. L2/L3/L4 核心输出对象

### L2
- `InterpretationResult`
- `BeliefUpdateDelta`
- `AffectDelta`
- `SocialInferenceDelta`
- `InnerMonologueCandidate`

### L3
- `CandidateAction`
- `TripleFilterResult`
- `IntentPacket`
- `PlayerSuggestionPacket`

### L4
- `SpeechExecutionPlan`
- `FaceExecutionPlan`
- `BodyExecutionPlan`
- `SocialSpatialExecutionPlan`
- `PhysiologyExecutionPlan`
- `ExecutionPacket`

## 5. 统一事件信封

建议角色侧统一事件信封：

- `event_id`
- `event_type`
- `world_ts`
- `producer`
- `character_id`
- `room_id`
- `scene_id`
- `zone_id`
- `causation_id`
- `correlation_id`
- `payload`

## 6. 最小回放链

必须能够重建：

`PerceivedEvent`
-> `InterpretationResult`
-> `BeliefUpdateDelta`
-> `SocialInferenceDelta`
-> `CandidateAction[]`
-> `TripleFilterResult[]`
-> `IntentPacket`
-> `ExecutionPacket`

## 7. 人类可读摘要

除结构化链外，系统应能生成简明说明：

- 角色看见了什么
- 如何理解
- 为什么怀疑或相信
- 最终为何这么做

## 8. Phase 1 范围

Phase 1 必须冻结：

- 12 个一级对象
- L2/L3/L4 输出合同
- 统一事件信封
- 最小决策周期回放链
- 基础调试日志规范
- 人类可读摘要能力

## 9. 一句话收束

角色智能体的数据层不是为了存日志，而是为了把“感知、记忆、理解、规划、执行”变成一条可追踪、可解释、可回放、可验收的连续链路。
