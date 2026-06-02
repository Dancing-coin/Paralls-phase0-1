# 07-Siming Orchestrator Interface Contract

## 1. 文档目标

本文档把 `Siming Orchestrator` 固定为一个正式的运行时编排接口，而不是抽象概念。

## 2. 核心职责

`Siming Orchestrator` 负责：

1. ingest 全局事件
2. 调度 4 个公平审计子智能体
3. 生成 `FairnessStateSnapshot`
4. 生成 `InterventionCandidate`
5. 调用 `Intervention Policy Engine`
6. 调用 `Godot Execution Feasibility Layer`
7. 产出 `InterventionDecision`
8. 调用 `Intervention Dispatcher`
9. 写入 `InterventionAuditRecord`
10. 刷新 `NarrativeReadModel`

## 3. 输入

### 来自权威总线

- `world_fact_event`
- `environment_state_event`
- `conversation_state_event`
- `knowledge_state_event`
- `visual_fact_event`
- `evidence_projection_event`
- `character_behavior_event`

### 来自系统状态

- `room_phase_state`
- `room_clock_state`
- `active_actor_registry`
- `scene_scope_state`

### 来自审计与冷却

- `intervention_cooldown_state`
- `recent_intervention_history`

## 4. 输出

### 中间对象

- `FairnessStateSnapshot`
- `InterventionCandidate[]`
- `InterventionDecision`
- `InterventionAuditRecord`
- `NarrativeReadModel`

### 对外动作

- `impulse`
- `opportunity`
- `fact_reveal`
- `environment_request`
- `none`

## 5. 与 4 个 auditor 的关系

### `information-auditor`

输入：

- 关键事实可见性
- 信息传播状态
- 角色知识态分布

输出：

- `information_audit_result`

### `participation-auditor`

输入：

- 行动窗口分布
- 会话参与状态
- 被边缘化角色状态

输出：

- `participation_audit_result`

### `suspicion-auditor`

输入：

- 怀疑热度分布
- 目标集中度
- 锁死风险

输出：

- `suspicion_audit_result`

### `evidence-auditor`

输入：

- 证据可见性分布
- 高价值视觉事实分布
- 可达性差异

输出：

- `evidence_audit_result`

## 6. 主循环方法

建议至少定义：

- `ingest_event(event: Dictionary) -> void`
- `build_fairness_snapshot() -> Dictionary`
- `generate_intervention_candidates(snapshot: Dictionary) -> Array`
- `evaluate_candidates(candidates: Array) -> Array`
- `select_intervention(evaluated_candidates: Array) -> Dictionary`
- `dispatch_intervention(decision: Dictionary) -> void`
- `audit_cycle(snapshot_before, candidate, decision, snapshot_after) -> Dictionary`
- `refresh_read_model(snapshot, recent_audit) -> Dictionary`
- `tick(world_ts: float) -> void`

## 7. 主循环顺序

`tick()` 内部顺序建议固定为：

1. consume queued events
2. build fairness snapshot
3. generate candidates
4. evaluate candidates
5. select decision
6. dispatch if approved
7. audit
8. refresh read model

## 8. 不该做什么

- 不直接发低层动作控制
- 不直接写物理结果
- 不直接改角色信念真值
- 不直接持有 Godot 场景节点引用

## 9. 生命周期

### 初始化

- 绑定 room
- 加载最近公平快照
- 加载冷却态
- 绑定 4 个 auditor

### 运行中

- 持续 ingest
- 周期性 tick

### 收尾

- 存最后 snapshot
- 存最后 read model
- 写最终 audit summary

### 小世界离线期

- 不持续常驻
- 回来时通过关键事件补全恢复

## 10. Phase 1 最小实现

必做：

- ingest 全局事件
- 4 auditor 调度
- snapshot 生成
- candidate 生成
- decision 生成
- audit 记录
- read model 刷新

## 11. 一句话收束

`Siming Orchestrator` 的价值，不是再多一个“大模型入口”，而是让司命从“会想的导演概念”变成“有状态、有候选、有路径选择、有审计、有表面读模型”的运行时编排核心。
