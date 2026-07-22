# Godot Runtime Mirror And Prediction Design

Status: `awaiting-user-review`

Date: `2026-07-23`

## Purpose

定义角色玩法状态从后端权威投影同步到 Godot 的正式边界，使 UI、动画、音频、交互反馈和本地数值预览能够读取同一份角色运行时镜像，同时不让 Godot 成为第二个玩法真相源。

本设计采用两层结构：

```text
Backend authority projections
-> global CharacterGameplayRuntimeBridge
-> route by actor_id
-> per-character CharacterGameplayStateMirrorComponent
-> UI / animation / audio / interaction / debug
```

## Scope

- 后端 `CharacterGameRuntimeState` snapshot/delta 的 Godot 传输契约。
- 全局 bridge 的连接、订阅、路由、重同步和 schema 门禁职责。
- 每个角色实例的 mirror component、revision vector 和只读查询面。
- 可回滚本地预测及确认、拒绝、超时、重连语义。
- 状态组的后端启停与 Godot 表现启停边界。
- UI、动画、表现和本地预览消费者的使用约束。

## Non-goals

- 不在 Godot 中实现 authority settlement、Rule IR 或经济事务。
- 不允许 Godot 直接修改权威资源、背包、物权、装备或能力状态。
- 不复制后端完整事件存储，也不允许 Godot 从事件历史重建权威真相。
- 不把网络连接对象挂到每个角色节点上。
- 不规定具体 HUD、美术资产、动画树或音频风格。
- 不允许本地预测产生不可逆世界结果。

## Dependencies

- `2026-07-23-foundation-invariants-and-domain-boundaries-design.md`
- `2026-07-23-state-group-registry-and-runtime-facade-design.md`
- `2026-07-23-event-sourcing-and-authority-settlement-design.md`
- `2026-07-23-persistence-replay-migration-and-hot-reload-design.md`
- 现有 `BackendBridge`、WebSocket authority/runtime event 路径与 `LocalPresentationBus`。
- 现有 actor identity、scene identity 和 authority event envelope。

## Runtime Components

### `CharacterGameplayRuntimeBridge`

该组件是全局单例或等价的全局 runtime service。它负责：

- 维护唯一后端连接或复用现有 `BackendBridge` 连接。
- 为当前 scene/session 订阅可见 actor 的玩法状态。
- 校验 transport envelope、schema version、session、actor 和 revision。
- 按 `actor_id` 将 snapshot、delta、prediction result 路由到对应 mirror。
- 缓存尚未绑定角色节点的最新完整 snapshot，缓存必须有数量和 TTL 上限。
- 在漏包、乱序、未知状态组或 schema 不兼容时请求重同步。
- 将表现事件转发到 `LocalPresentationBus`，但不把表现完成当作 authority 成功。

它不负责：

- 计算有效属性、负重、交易结果或能力可用性。
- 根据 UI 操作直接改 mirror。
- 保存 actor-private 后端数据。
- 让某个角色节点拥有独立 WebSocket。

### `CharacterGameplayStateMirrorComponent`

每个游戏内角色实例挂载一个 mirror component。组件必须显式绑定：

```text
actor_id
scene_instance_id
mirror_schema_version
connection_epoch
revision_vector
enabled_state_groups
state_groups
pending_predictions
sync_status
```

组件负责：

- 保存该 actor 当前已确认的只读状态组投影。
- 提供按组和稳定路径查询的 typed accessor。
- 发出 `state_group_changed`、`snapshot_replaced`、`prediction_changed` 和 `sync_status_changed` 信号。
- 保存有限的预测 overlay；confirmed base 与 predicted overlay 必须分离。
- 在 actor 节点复用或换绑时清空旧 actor 数据、预测和 revision。

组件不得：

- 直接接受其他 actor 的消息。
- 把预测 overlay 写回 confirmed base。
- 为未知字段猜测默认玩法含义。
- 向 UI 暴露未通过后端可见性投影的字段。

## Transport Contracts

### Snapshot

```json
{
  "message_type": "character_gameplay_state.snapshot",
  "schema_version": 1,
  "session_id": "session-01",
  "actor_id": "char_player",
  "snapshot_id": "snap-00042",
  "connection_epoch": 3,
  "configuration_revision": 12,
  "revision_vector": {
    "resources": 18,
    "body_runtime": 9,
    "inventory": 24,
    "equipment": 7
  },
  "enabled_state_groups": ["resources", "body_runtime", "inventory", "equipment"],
  "state_groups": {},
  "projection_policy_ref": "godot:player-visible:v1",
  "generated_at": "2026-07-23T12:00:00Z"
}
```

规则：

- snapshot 是指定 actor 在某个 configuration revision 下的完整可见镜像。
- bridge 只能原子替换整个 confirmed base；不能逐字段应用半份 snapshot。
- snapshot 未列出的状态组视为未启用或对该客户端不可见，不能沿用旧值。
- `revision_vector` 是状态组 revision 的权威集合，不能由客户端生成。

### Delta

```json
{
  "message_type": "character_gameplay_state.delta",
  "schema_version": 1,
  "session_id": "session-01",
  "actor_id": "char_player",
  "connection_epoch": 3,
  "group_id": "resources",
  "base_revision": 18,
  "target_revision": 19,
  "configuration_revision": 12,
  "operations": [
    {"op": "replace", "path": "/values/stamina/current", "value": 42}
  ],
  "transaction_id": "tx-swing-017",
  "causation_id": "cmd-swing-017",
  "prediction_id": "pred-017"
}
```

`operations` 只能使用协议白名单中的 typed patch 操作。禁止任意脚本、表达式和节点路径。bridge 仅在以下条件全部满足时应用 delta：

- `actor_id` 与目标 mirror 绑定一致。
- `connection_epoch` 是当前连接 epoch。
- `base_revision` 等于该组 confirmed revision。
- configuration revision 兼容。
- group schema 已注册且 operation 校验通过。

任一条件不成立时，该组进入 `resync_required`，停止应用后续 delta，直到完整 snapshot 到达。

### Subscription And Resync

客户端请求只表达需求，不授予读取权限：

```text
character_gameplay_state.subscribe
character_gameplay_state.unsubscribe
character_gameplay_state.request_snapshot
```

请求必须携带 `session_id`、`actor_ids`、客户端支持的 schema versions 和现有 revision vector。后端按授权范围裁剪 actor 和状态组；不能因为客户端请求了某 actor 就返回其私有状态。

## State Group Enablement

状态组启停是后端配置与 authority 决策：

- Godot 可以发送 `request_state_group_enablement`。
- 后端校验世界配置、玩法包、actor archetype 和权限后决定接受或拒绝。
- 接受后通过新的 `configuration_revision` 和 snapshot/delta 生效。
- Godot 可以本地隐藏某组 UI 或关闭某类表现，但这只是 presentation preference。
- 本地隐藏不能停止后端计算、持久化或权威同步。
- 未启用组必须返回 `state_group_not_enabled`，不能由客户端创建空组冒充启用。

## Prediction Model

### Allowed Predictions

首批只允许短时、可逆、且能从权威结果完全校正的预测：

- 按键后立即显示的 stamina 预览。
- 拾取、使用、装备请求的 pending UI 状态。
- 武器切换、受击和交互的临时动画/音效。
- 本地移动与姿态表现中已有权威协议允许的预测。

禁止预测：

- 货币或产权最终转移。
- 物品创建、销毁或跨容器最终归属。
- 债务、契约或交易完成。
- 技能永久学习或晋升。
- 隐藏信息揭示和 actor-private 关系变化。

### Prediction Request

```json
{
  "message_type": "character_gameplay.command",
  "command_id": "cmd-equip-021",
  "idempotency_key": "client-7:equip:021",
  "prediction_id": "pred-equip-021",
  "actor_id": "char_player",
  "command_type": "equipment.equip_item",
  "expected_revision_vector": {"inventory": 24, "equipment": 7},
  "payload": {"item_instance_id": "item-sword-01", "slot_id": "right_hand"}
}
```

本地只把预测结果写入 overlay，并保存恢复所需的 base revision。一个 prediction 必须处于以下状态之一：

```text
pending -> confirmed
pending -> rejected -> rolled_back
pending -> expired -> resync_required
pending -> superseded -> rolled_back
```

### Confirmation And Rejection

- 确认消息必须引用相同 `prediction_id`、`command_id` 和 transaction。
- mirror 先应用权威 snapshot/delta，再删除 overlay，不能把 overlay 当成确认值。
- 拒绝包含结构化 error；mirror 回滚 overlay，但不回滚已经确认的其他 transaction。
- 超时只表示结果未知，不能展示“失败”或重发非幂等命令；客户端先按原 idempotency key 查询结果或请求重同步。
- 同一状态路径上存在多个预测时，必须按本地序号重放尚未解决的 overlay；不能用后到的权威 delta 清空所有无关预测。

## Read API And Consumer Rules

mirror 至少提供：

```text
get_group(group_id)
get_resource(resource_id)
has_status_tag(tag_id)
get_effective_stat(stat_id)
get_inventory_summary()
get_equipment_slot(slot_id)
get_ability_affordance(action_id)
get_sync_status()
```

- UI 和表现只读 mirror，不保留另一份长期业务状态。
- 本地计算只允许用于显示、动画混合、预览和输入可用性提示。
- 最终 action 可执行性必须以后端 settlement 为准。
- 消费者必须处理 `unknown`、`not_visible`、`not_enabled` 和 `stale`，不得都映射成零值。

## Authority And Privacy Invariants

1. 后端事件流和投影是唯一玩法真相；Godot mirror 是可丢弃、可替换的读模型。
2. 全局 bridge 只路由，不拥有角色领域规则；每角色 component 只保存被路由的 actor 数据。
3. actor-private 数据必须在后端投影阶段过滤，不能先发到 Godot 再隐藏。
4. 观察者、玩家、调试员可以拥有不同 `projection_policy_ref`；调试权限不能默认进入正式构建。
5. prediction 永远不构成 authority 证据、经济审计或世界事实。
6. presentation 完成、动画事件或 UI 成功提示不能反向提交为权威成功。
7. 所有客户端命令都必须重新经过权限、revision、规则和 settlement 校验。

## Failure Semantics

| Failure | Required behavior |
|---|---|
| unknown actor | 丢弃消息，记录脱敏 trace，请求订阅表刷新 |
| actor binding changed | 清空旧 mirror 和预测，等待新 actor snapshot |
| revision gap / out-of-order | 标记该组 stale，停止 delta，申请完整 snapshot |
| duplicate delta | 按 message/event id 幂等忽略 |
| schema unsupported | 不应用数据，进入 incompatible，不猜测字段 |
| unknown state group | 隔离该组并请求兼容 snapshot；其他组可继续 |
| prediction rejected | 回滚对应 overlay，展示结构化失败原因 |
| prediction timeout | 标记 unknown，按 idempotency key 查询或重同步 |
| reconnect | 增加 connection epoch，旧 epoch 消息全部作废 |
| privacy violation | 拒绝载入、记录安全事件，不把 payload 写入普通日志 |

## Acceptance Criteria

1. 单一全局 bridge 能将两个 actor 的交错 delta 正确路由到两个独立 mirror。
2. 角色节点换绑 actor 后不会保留前一 actor 的状态或 prediction。
3. snapshot 原子替换状态组，禁用组不会残留旧值。
4. 连续 delta 只在 revision 连续时生效；漏包、乱序和旧 epoch 都触发确定性恢复。
5. 可回滚 stamina/equipment 预测分别通过确认和拒绝路径，并最终与后端 projection 一致。
6. 买卖、物权和技能晋升不能被客户端预测为 confirmed truth。
7. 未授权客户端无法订阅 actor-private 或不可见状态组。
8. Godot 重连后通过完整 snapshot 恢复，与后端 façade 的 revision vector 和可见内容一致。
9. UI、动画和 debug consumer 均从 mirror 查询，不各自维护竞争性状态副本。
10. Godot runtime 测试证明目标节点存在、脚本可加载、信号可触发且无立即运行错误。

## Harness Mapping

主要 profile：`godot-gameplay-mirror`

| Evidence claim | Harness check |
|---|---|
| 全局 bridge 按 actor 路由 | two-actor interleaved snapshot/delta fixture |
| revision 连续性 | gap, duplicate, out-of-order and old-epoch cases |
| 预测可回滚 | prediction confirm/reject/timeout scenarios |
| 隐私裁剪发生在后端 | unauthorized projection transport assertion |
| 重连收敛 | reconnect plus full-snapshot equivalence |
| Godot 节点真实可用 | headless scene/script load and signal probe |

聚合 profile：`gameplay-foundation-all`。

Harness 证据写入 `.harness/verification/`，至少包含结构化报告、Godot 运行日志和后端/Godot 最终 revision 对比；静态脚本存在不能替代 Godot runtime 证明。
