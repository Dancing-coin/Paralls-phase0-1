# 17-司命Canonical Schema与验收对象

## 1. 文档目标

本文档把 `Phase 1` 司命的最小领域对象压成实现者可以直接落代码的 canonical schema 口径。

它补齐：

- 必填 / 可空 / 可省略字段
- 枚举归属
- 分数范围
- stale / degraded / late 语义
- 版本兼容规则

本文档不替代 `03-06` 的设计说明；它是这些设计说明的实现收束层。

## 2. Canonical 对象清单

`Phase 1` 最小公平裁判链只冻结以下 7 类对象：

1. `FairnessStateSnapshot`
2. `InterventionCandidate`
3. `ExecutionContextSnapshot`
4. `InterventionDecision`
5. `Checkpoint`
6. `InterventionAuditRecord`
7. `NarrativeReadModel`

`NarrativeStateSnapshot`、`ProjectionRun`、`EventChainCandidate`、`DramaticPriorityRecord` 属于 `Phase 2+` 或 `Phase 1` 可选 stub，不进入最小验收。

## 3. 通用字段规则

所有 canonical 对象必须带：

| 字段 | 规则 |
| --- | --- |
| `schema_version` | 必填，字符串，例如 `1.0` |
| `room_id` | 必填，跨房间隔离主键 |
| `correlation_id` | 必填，串起一次用户 / 系统链路 |
| `causation_id` | 必填，指向直接触发对象 |
| `producer_ts` | 必填，服务端生产时间 |
| `world_ts` | 可空但不可省略，房间世界时间 |
| `sim_tick_ts` | 可空但不可省略，司命 tick 时间 |

字段语义：

- `producer_ts` 参与跨系统粗排序。
- `world_ts` 只属于司命 payload / 领域对象，不进入事件总线公共信封。
- `sim_tick_ts` 只用于同一房间内裁判周期排序。
- 可空字段必须显式写 `null`，不能通过缺字段表达。

## 4. 枚举归属

| 枚举 | 合法值 |
| --- | --- |
| `dominant_imbalance_type` | `information_starvation`, `participation_starvation`, `private_channel_lock`, `suspicion_runaway`, `evidence_bottleneck`, `balanced` |
| `intervention_band` | `none`, `impulse`, `opportunity`, `fact_reveal`, `environment_request` |
| `intervention_strength` | `hint`, `low`, `medium`, `high` |
| `intervention_urgency` | `low`, `medium`, `high`, `critical` |
| `decision` | `approve`, `downgrade`, `reject` |
| `selected_path` | `character_input_path`, `environment_change_path`, `visual_fact_path`, `l3_highlight_path`, `no_action` |
| `dimension_status` | `fresh`, `stale`, `degraded`, `unimplemented` |
| `audit_result_status` | `dispatched`, `acknowledged`, `effective`, `partially_effective`, `ineffective`, `harmful`, `ack_timeout`, `esm_rejected`, `expired_ttl`, `stale_snapshot`, `duplicate_suppressed`, `rolled_back`, `unknown_effect` |

## 5. 分数规则

所有 score 字段默认范围为 `0.0-1.0`。

规则：

1. `null` 只允许用于无法计算的可空分数。
2. `NaN`、负数、超过 `1.0` 的值非法。
3. stale / degraded 维度必须保留上一份可用分数或写 `null`，并说明原因。
4. 聚合分数必须只使用 `status in fresh,degraded` 且分数非空的维度。

`global_imbalance_score` 聚合：

```text
weighted_sum = sum(score_i * weight_i for computable dimensions)
weight_sum = sum(weight_i for computable dimensions)
global_imbalance_score = weighted_sum / weight_sum
```

权重：

| 维度 | 权重 |
| --- | --- |
| `information_distribution` | `0.30` |
| `participation_distribution` | `0.28` |
| `conversation_access_fairness` | `0.18` |
| `suspicion_heat_distribution` | `0.12` |
| `evidence_visibility_distribution` | `0.12` |

若 `weight_sum == 0`，`global_imbalance_score=0.0`，`dominant_imbalance_type=balanced`，并写 `imbalance_reasons=["no_computable_dimension"]`。

dominant tie-break：

```text
information_starvation
-> participation_starvation
-> private_channel_lock
-> evidence_bottleneck
-> suspicion_runaway
-> balanced
```

## 6. `FairnessStateSnapshot`

必填字段：

- `schema_version`
- `snapshot_id`
- `room_id`
- `world_ts`
- `sim_tick_ts`
- `producer_ts`
- `correlation_id`
- `causation_id`
- `scene_scope`
- `phase_marker`
- `information_distribution`
- `participation_distribution`
- `conversation_access_fairness`
- `suspicion_heat_distribution`
- `evidence_visibility_distribution`
- `global_imbalance_score`
- `dominant_imbalance_type`
- `affected_actor_ids`
- `recommended_intervention_band`
- `intervention_urgency`
- `imbalance_reasons`

每个维度对象必须至少包含：

```json
{
  "status": "fresh",
  "score": 0.42,
  "confidence": 0.91,
  "reason_tags": [],
  "source_event_refs": []
}
```

维度不可计算时：

```json
{
  "status": "degraded",
  "score": null,
  "confidence": 0.0,
  "reason_tags": ["runtime_pressure"],
  "source_event_refs": []
}
```

## 7. `InterventionCandidate`

必填字段：

- `schema_version`
- `intervention_candidate_id`
- `room_id`
- `snapshot_ref`
- `correlation_id`
- `causation_id`
- `imbalance_type`
- `band`
- `strength`
- `target_actor_ids`
- `goal`
- `fallback_band`
- `priority`
- `created_at`

候选只表达“值得尝试的高层干预”，不得表达执行已经成功。

## 8. `ExecutionContextSnapshot`

必填字段：

- `schema_version`
- `context_id`
- `room_id`
- `world_ts`
- `sim_tick_ts`
- `scene_ids`
- `active_actor_ids`
- `active_object_ids`
- `environment_capabilities`
- `presentation_budget`
- `runtime_pressure`
- `cooldowns`
- `producer_ts`

该对象是可执行性层的输入，不是世界真值库。

## 9. `InterventionDecision`

必填字段：

- `schema_version`
- `intervention_decision_id`
- `room_id`
- `candidate_ref`
- `correlation_id`
- `causation_id`
- `decision`
- `selected_path`
- `fallback_path`
- `physical_feasibility`
- `semantic_naturalness`
- `role_autonomy_safety`
- `presentation_capacity`
- `traceability`
- `cross_system_dependency_cost`
- `dispatch_target`
- `execution_notes`
- `idempotency_key`
- `created_at`

`idempotency_key`：

```text
{room_id}:{intervention_decision_id}:{selected_path}
```

`decision=reject` 时 `selected_path=no_action`。

## 10. `Checkpoint`

必填字段：

- `schema_version`
- `checkpoint_id`
- `room_id`
- `checkpoint_type`
- `fairness_snapshot_ref`
- `focus_actor_ids`
- `hot_conversation_ids`
- `hot_evidence_refs`
- `correlation_id`
- `causation_id`
- `world_ts`
- `sim_tick_ts`
- `producer_ts`

`checkpoint_type`：

- `fairness_before`
- `fairness_after`

## 11. `InterventionAuditRecord`

必填字段：

- `schema_version`
- `audit_id`
- `room_id`
- `snapshot_before_ref`
- `candidate_ref`
- `decision_ref`
- `snapshot_after_ref`
- `expected_effect`
- `observed_effect`
- `result_status`
- `correlation_id`
- `causation_id`
- `result_event_refs`
- `correction_records`
- `idempotency_key`
- `created_at`
- `updated_at`

`snapshot_after_ref` 可为 `null`，但字段不能省略。

`correction_records` 是追加数组，不得覆盖 final 状态。

## 12. `NarrativeReadModel`

必填字段：

- `schema_version`
- `read_model_id`
- `room_id`
- `scene_scope`
- `current_state`
- `focus_entities`
- `conversation_surface`
- `evidence_surface`
- `intervention_surface`
- `summary_text`
- `derived_from_snapshot_ref`
- `updated_at`

`NarrativeReadModel` 是只读投影，不得反向写入世界事实、角色信念或 ESM 状态。

## 13. 版本兼容

兼容规则：

1. 新增字段必须先作为可选字段发布。
2. 删除字段必须先保留一个 schema 主版本。
3. 枚举新增必须有默认处理分支。
4. 分数字段权重变化必须记录在 `schema_version` 或 `scoring_version`。
5. read model 可以新增表面字段，但不得改变已存在字段语义。

## 14. 一句话收束

司命 schema 的核心不是把 JSON 列得更长，而是让同一条事件链在不同实现、不同机器和不同时间回放时，仍然能得到同一类可解释、可审计、不会越权的裁判结果。
