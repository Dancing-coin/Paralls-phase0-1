# 06-Checkpoint-Audit-ReadModel 设计

## 1. 文档目标

本文档定义 `Phase 1` 司命在 replay、工作台、运营与大玩家控制台上必须成立的三层结构：

1. `Checkpoint`
2. `InterventionAuditRecord`
3. `NarrativeReadModel`

## 2. 核心定义

### `Checkpoint`

记录一次关键干预前后的关键状态锚点。

### `InterventionAuditRecord`

记录：

- 为什么干预
- 选了什么
- 预期效果是什么
- 实际效果是什么

### `NarrativeReadModel`

不是世界真值库，而是给人看的“当前局势表面”。

## 3. Checkpoint 设计

建议固定两类：

### `fairness_before_checkpoint`

记录干预前：

- `fairness_snapshot_ref`
- `focus_actor_ids`
- `hot_conversation_ids`
- `hot_evidence_refs`

### `fairness_after_checkpoint`

记录干预后：

- `fairness_snapshot_ref`
- `focus_actor_ids`
- `hot_conversation_ids`
- `hot_evidence_refs`

### 最小对象

```json
{
  "checkpoint_id": "sim_cp_001",
  "world_ts": 123456.90,
  "room_id": "room_01",
  "checkpoint_type": "fairness_before",
  "fairness_snapshot_ref": "fair_snap_001",
  "focus_actor_ids": ["player_02", "char_poirot"],
  "hot_conversation_ids": ["conv_12"],
  "hot_evidence_refs": ["evid_03"]
}
```

## 4. InterventionAuditRecord 设计

最小字段：

- `audit_id`
- `world_ts`
- `snapshot_before_ref`
- `candidate_ref`
- `decision_ref`
- `snapshot_after_ref`
- `expected_effect`
- `observed_effect`
- `result_status`
- `causation_id`
- `correlation_id`

结果状态建议：

- `effective`
- `partially_effective`
- `ineffective`
- `harmful`

## 5. NarrativeReadModel 设计

作用：

- 给工作台
- 给大玩家
- 给运营 / QA

提供一层当前局势摘要，而不是底层推理链。

### 最小字段

- `read_model_id`
- `world_ts`
- `room_id`
- `scene_scope`
- `current_state`
- `focus_entities`
- `conversation_surface`
- `evidence_surface`
- `intervention_surface`
- `narrative_surface`
- `summary_text`
- `derived_from_snapshot_ref`
- `updated_at`

### `current_state`

- `imbalance_type`
- `imbalance_score`
- `intervention_urgency`
- `active_phase_marker`
- `heat_level`
- `stability_level`

### `focus_entities`

- `focus_actor_ids`
- `focus_object_ids`
- `focus_zone_ids`
- `focus_conversation_ids`
- `focus_reason_tags`

### `conversation_surface`

- `hot_conversation_ids`
- `private_channel_lock_score`
- `conversation_exclusion_risk`
- `repeatedly_excluded_actor_ids`
- `public_flow_block_score`

### `evidence_surface`

- `hot_evidence_refs`
- `evidence_bottleneck_score`
- `hidden_high_value_evidence_count`
- `visual_fact_reach_gap_score`
- `trace_discoverability_level`

### `intervention_surface`

- `recent_intervention_ids`
- `recent_intervention_bands`
- `latest_result_status`
- `cooldown_state`

### `narrative_surface`

- `current_story_pressure`
- `open_possibility_count`
- `dominant_uncertainty`
- `current_public_attention_anchor`
- `narrative_openness`

## 6. 存储建议

### PostgreSQL

持久化：

- `Checkpoint`
- `InterventionAuditRecord`
- `NarrativeReadModel`

### Redis

缓存：

- 当前 `NarrativeReadModel`
- 当前 cooldown 状态

## 7. Phase 1 最小实现建议

必做：

- `fairness_before / fairness_after checkpoint`
- `InterventionAuditRecord`
- 薄版 `NarrativeReadModel`

后补：

- 更复杂的 narrative surface
- 更细的 intervention surface
- 跨房间聚合视图

## 8. 一句话收束

这三层不是司命的“附属日志”，而是它能被 replay、被工作台、被大玩家和运营理解的最低条件。
