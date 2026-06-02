# 03-Fairness State Model 设计

## 1. 文档目标

本文档把司命的“天平系统”进一步压成字段级 `Fairness State Model`。它不再只是泛化的概念，而是一个可存、可传、可 replay、可用于工作台显示的运行时公平快照对象。

## 2. 核心对象

建议对象名固定为：

- `FairnessStateSnapshot`

它描述司命对当前局势的公平判断，不是真值库，不是角色记忆，也不是工作台 UI 对象。

## 3. 最小结构

```json
{
  "snapshot_id": "fair_snap_001",
  "world_ts": 123456.78,
  "room_id": "room_01",
  "scene_scope": ["scene_dining_car", "scene_corridor"],
  "phase_marker": "mid_round",

  "information_distribution": {},
  "participation_distribution": {},
  "conversation_access_fairness": {},
  "suspicion_heat_distribution": {},
  "evidence_visibility_distribution": {},

  "global_imbalance_score": 0.42,
  "dominant_imbalance_type": "participation_starvation",
  "affected_actor_ids": ["player_02", "char_mary"],

  "imbalance_reasons": [],
  "candidate_relief_paths": [],

  "recommended_intervention_band": "opportunity",
  "intervention_urgency": "medium"
}
```

## 4. 五个核心维度

### 4.1 `information_distribution`

职责：

- 看关键事实是否被极少数人垄断
- 看是否有人长期得不到可行动输入

建议字段：

- `key_fact_concentration_score`
- `single_holder_risk`
- `unreachable_key_fact_count`
- `underinformed_actor_ids`
- `overinformed_actor_ids`

### 4.2 `participation_distribution`

职责：

- 看谁长期没行动窗口
- 看谁长期被边缘化

建议字段：

- `inactive_window_score`
- `edge_actor_ids`
- `high_activity_actor_ids`
- `turn_opportunity_gap_score`
- `stalled_actor_count`

### 4.3 `conversation_access_fairness`

职责：

- 看私密通道是否锁死
- 看会话接入和偷听窗口是否失衡

建议字段：

- `private_channel_lock_score`
- `conversation_exclusion_risk`
- `repeatedly_excluded_actor_ids`
- `eavesdrop_access_gap_score`
- `public_flow_block_score`

### 4.4 `suspicion_heat_distribution`

职责：

- 看怀疑是否单点爆炸
- 看是否过早锁死叙事

建议字段：

- `single_target_heat_score`
- `premature_lock_risk`
- `heat_target_actor_id`
- `heat_spread_score`
- `misdirection_capacity_score`

### 4.5 `evidence_visibility_distribution`

职责：

- 看高价值证据是否只掌握在极少数人手里
- 看视觉事实与痕迹是否始终不可达

建议字段：

- `evidence_bottleneck_score`
- `hidden_high_value_evidence_count`
- `visible_to_too_few_actor_ids`
- `visual_fact_reach_gap_score`
- `trace_discoverability_score`

## 5. 聚合字段

### 5.1 `global_imbalance_score`

建议按加权聚合：

- information: `0.30`
- participation: `0.28`
- conversation access: `0.18`
- suspicion heat: `0.12`
- evidence visibility: `0.12`

### 5.2 `dominant_imbalance_type`

建议枚举：

- `information_starvation`
- `participation_starvation`
- `private_channel_lock`
- `suspicion_runaway`
- `evidence_bottleneck`
- `balanced`

### 5.3 `affected_actor_ids`

保存当前受影响最大的角色/玩家集合。

### 5.4 `recommended_intervention_band`

建议枚举：

- `none`
- `impulse`
- `opportunity`
- `fact_reveal`
- `environment_request`

### 5.5 `intervention_urgency`

建议枚举：

- `low`
- `medium`
- `high`
- `critical`

## 6. 解释字段

为了工作台和 replay 更有用，建议增加：

- `imbalance_reasons`
- `candidate_relief_paths`

它们分别承载：

- 为什么判断失衡
- 初步的缓解方向提示

## 7. 与其他系统的关系

- 输入来自：
  - 原始世界事件
  - 角色关键行为回写
  - 会话/知识状态变化
  - 视觉事实事件
  - 证据链关键事件
- 输出给：
  - `Intervention Policy Engine`
  - `Checkpoint / Audit`
  - `NarrativeReadModel`

## 8. Phase 1 最小实现建议

必做：

- `information_distribution`
- `participation_distribution`
- `conversation_access_fairness`
- `global_imbalance_score`
- `dominant_imbalance_type`
- `affected_actor_ids`
- `recommended_intervention_band`
- `intervention_urgency`

第二批再补：

- `suspicion_heat_distribution`
- `evidence_visibility_distribution`
- `imbalance_reasons`
- `candidate_relief_paths`

## 9. 一句话收束

`FairnessStateSnapshot` 不是“天平系统的描述性说法”，而是司命在 `Phase 1` 里真正的运行时核心状态对象：它负责把全局事件、知识、会话、视觉事实和证据可见性压缩成一份可用于判断“该不该干预、该对谁干预、该用哪种最小干预”的结构化公平快照。
