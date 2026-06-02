# 04-Intervention Policy Engine 规则表

## 1. 文档目标

本文档把 `FairnessStateSnapshot` 中识别出的失衡类型，映射成最小、可执行、可 replay 的干预动作。

## 2. 固定输出带

`Phase 1` 只允许这 5 种干预带：

1. `none`
2. `impulse`
3. `opportunity`
4. `fact_reveal`
5. `environment_request`

## 3. 强度档

建议固定四档：

- `hint`
- `low`
- `medium`
- `high`

`Phase 1` 默认尽量停在：

- `hint`
- `low`
- `medium`

## 4. 失衡类型到干预映射

### 4.1 `information_starvation`

- 主动作：`fact_reveal`
- 次动作：`opportunity`
- 默认强度：`medium`
- 目标：信息匮乏者本人

### 4.2 `participation_starvation`

- 主动作：`opportunity`
- 次动作：`impulse`
- 默认强度：`medium`
- 目标：被边缘化者本人

### 4.3 `private_channel_lock`

- 主动作：`opportunity`
- 次动作：`environment_request`
- 默认强度：`low`
- 目标：被排斥在关键会话外、但理论上有接入资格的角色/玩家

### 4.4 `suspicion_runaway`

- 主动作：`fact_reveal`
- 次动作：`impulse`
- 允许：`none`
- 默认强度：`low`
- 目标：怀疑链主要参与者，而不是被怀疑对象本人优先

### 4.5 `evidence_bottleneck`

- 主动作：`fact_reveal`
- 次动作：`opportunity`、`environment_request`
- 默认强度：`medium`
- 目标：最该看到关键证据、但一直没看到的人

## 5. 干预目标选择规则

1. 若缺信息，优先补给“最该知道却不知道的人”
2. 若缺窗口，优先补给“最该有行动机会却没有的人”
3. 若怀疑锁死，优先让主要参与怀疑链的人重新获得可能性空间
4. 若证据卡死，优先让最该接触证据的人获得证据可达性

## 6. 候选对象

建议固定对象：

```json
{
  "intervention_candidate_id": "intv_cand_001",
  "snapshot_ref": "fair_snap_001",
  "imbalance_type": "participation_starvation",
  "band": "opportunity",
  "strength": "medium",
  "target_actor_ids": ["player_02"],
  "goal": "open_action_window",
  "fallback_band": "impulse",
  "priority": "p1"
}
```

## 7. 降级规则

### 情况 1：最优干预不可执行

- 若 `environment_request` 当前不可落地
- 降级到 `opportunity`
- 再不行降级到 `impulse`

### 情况 2：最优干预会抢角色自主性

- 若 `fact_reveal` 会等价于强行替角色做结论
- 降级到更弱的 `impulse`
- 或 `none`

### 情况 3：最优干预 replay 不可解释

- 降级到更稳定、可追踪的路径

## 8. 与 Godot 可执行性层的关系

本层只负责：

- 识别失衡
- 选最小干预

不负责：

- 判断这件事在 `Godot` 里能不能自然做
- 选择 `character_input_path / environment_change_path / visual_fact_path / l3_highlight_path`

这些交给 `Godot Execution Feasibility Layer`。

## 9. Phase 1 不做

先不做：

- 复杂多步干预链自动编排
- 多角色组合干预策略搜索
- 长局叙事弧优化器
- 玩家风格画像驱动的个性化干预

## 10. 一句话收束

`Intervention Policy Engine` 在 `Phase 1` 的任务，不是“写出最精彩的戏”，而是把“哪种公平失衡”可靠地映射成“哪种最小、可执行、可回放的干预动作”。\n*** End Patch
