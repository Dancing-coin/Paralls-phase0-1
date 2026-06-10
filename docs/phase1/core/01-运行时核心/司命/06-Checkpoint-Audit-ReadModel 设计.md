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

- `dispatched`
- `effective`
- `partially_effective`
- `ineffective`
- `harmful`
- `ack_timeout`
- `esm_rejected`
- `expired_ttl`
- `stale_snapshot`
- `duplicate_suppressed`
- `rolled_back`
- `unknown_effect`

### 4.1 after snapshot 规则

1. 成功 dispatch 后，在收到角色 / `ESM` / 视觉回流结果或 TTL 到期后生成 `fairness_after_checkpoint`。
2. `no_action` 也要写 audit，但 `snapshot_after_ref` 可以为空。
3. duplicate suppression 不重新 dispatch，只追加审计或计数。
4. late result 不得覆盖已有最终状态，只能追加修正记录。
5. 若角色断连、目标不可达或部分目标未送达，`observed_effect` 必须写明缺失对象。

### 4.2 幂等键

建议固定：

- dispatch 幂等键：`room_id + decision_id + selected_path`
- audit 幂等键：`room_id + decision_ref + result_event_id`

同一幂等键重复出现时，必须进入 `duplicate_suppressed` 或追加审计，不得重复执行干预。

### 4.3 result lifecycle

`InterventionAuditRecord` 必须按追加式状态机记录结果，不能原地覆盖最终结论。

| 当前状态 | 输入 | 新状态 | 记录方式 |
| --- | --- | --- | --- |
| `dispatched` | 目标 ack | `acknowledged` | 追加 result event ref |
| `dispatched` | TTL 到期无 ack | `ack_timeout` | 写 final record，可后续 correction |
| `acknowledged` | 部分目标成功 | `partially_effective` | 写 final record，列出缺失目标 |
| `acknowledged` | 明确缓解失衡 | `effective` | 写 final record 和 after snapshot |
| `acknowledged` | 没有外部效果 | `ineffective` | 写 final record 和 observed reason |
| 任意非 final | ESM 拒绝 | `esm_rejected` | 写 final record，引用 constraint |
| 任意非 final | stale candidate | `stale_snapshot` | suppress dispatch，写 audit |
| 任意状态 | duplicate dispatch key | `duplicate_suppressed` | 不重复 dispatch，只计数或追加 duplicate ref |
| final 状态 | late result | 原 final 不变 | 追加 `correction_record` |

final 状态包括：

- `effective`
- `partially_effective`
- `ineffective`
- `harmful`
- `ack_timeout`
- `esm_rejected`
- `expired_ttl`
- `stale_snapshot`
- `duplicate_suppressed`
- `rolled_back`
- `unknown_effect`

late result、重复 result、人工修正都只能追加 `correction_record`，不得重写原 `audit_id` 的 final 状态。

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
