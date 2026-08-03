# 库存、容器与负重设计

Status: `minimum-core-implemented; broader-possession-planned`

Date: `2026-07-23`

## 2026-08-02 Implementation Status

The first backend-only inventory core is implemented and profile-verified: item
definitions, container creation, event-derived single-location projection,
sealed/capacity rejection, atomic move, and a flat carried-container
encumbrance read projection. It does not implement nesting, recursive weight
propagation, storage-ring policy, stack operations, access grants, ownership,
equipment, persistence, transport, or Godot mirror delivery.

The embodied custody bridge now has a bounded implementation continuation:
`stow_from_custody` moves a verified custody holder into a policy-resolved
actor container, and `retrieve_to_custody` is the inverse backend authority
foundation. It validates an item is in the declared actor container, that its
custody projection still names that container, that the container is not
sealed, and that a backend-registered custody receiver is empty. It writes
custody, inventory transfer-out, receiver occupancy, and retrieve evidence in
one batch. This does not establish a generic player command, client-selected
container/receiver refs, a scene container, UI, ownership transfer, or Godot
inventory delivery.

## Purpose

定义角色游戏运行时中实体物品的实例、位置、可访问性、嵌套容器与负重传播规则。本规格只处理“物品在哪里、能否取用、会带来多少实体负担”；物权、货币余额与交易结算由经济领域负责，装备后的运行效果由装备领域负责。

## Scope

- `ItemDefinition`、`ItemInstance`、`ContainerState` 与位置索引。
- 有限嵌套容器、容量、体积、重量、访问条件、封印与绑定约束。
- 角色背包、地面容器、商店库存和装备激活的特殊容器。
- 可重放的库存事件、确定性的负重投影和面向 Godot 的只读镜像。

## Non-goals

- 不以物品位置证明或转移产权；地契等凭证只是一件物品。
- 不实现市场价格、生产链、物品合成或完整制作玩法。
- 不允许角色实体、宠物、坐骑或随从作为 `ItemInstance` 存入容器。
- 不允许 Godot 直接写入库存真相。

## Dependencies

- 基础事件、聚合 revision、`transaction_id`、幂等键和 authority settlement 契约。
- 状态组注册表提供 `inventory`、`encumbrance` 状态组的启用条件与可见性。
- 物权经济规格提供交易时的可转移性和授权结果；装备规格提供装备容器激活与撤销结果。

## 领域模型与接口

```text
ItemDefinition {
  definition_id, schema_version, stack_policy, unit_weight, unit_volume,
  tags, container_spec?, equip_spec?, access_policy_ref
}

ItemInstance {
  item_id, definition_id, definition_revision, quantity, mutable_state,
  provenance_ref, lifecycle_state
}

ContainerState {
  container_id, owner_ref?, host_item_id?, capacity_weight?, capacity_volume?,
  capacity_slots?, access_policy_ref, sealing_state, contents_revision
}

ItemLocation {
  item_id, container_id | world_anchor_ref, slot_key?, ordinal
}

EncumbranceProjection {
  carrier_ref, carried_weight, carried_volume, capacity_weight,
  burden_ratio, source_breakdown, revision
}
```

`ItemDefinition` 是版本化静态定义；可变耐久、绑定、质量、附魔等只能保存在 `ItemInstance.mutable_state` 并由事件改变。`ContainerState` 是独立聚合，不把内容列表复制进物品实例。每个物品在同一 revision 只能有一个活动位置；位置索引必须能反向查到容器。

容器内容使用稳定 `item_id` 与确定性排序键，不以客户端数组下标作为权威地址。堆叠、拆分和合并必须声明 `stack_policy`，且不允许混合来源、耐久或绑定语义不相同的实例。

### 特殊容器：储物戒

储物戒本身是可装备 `ItemInstance`，且在其装备授予激活后暴露一个 `ContainerState`：

- 戒指自身重量计入佩戴者负重。
- 已授权的内部物品不向佩戴者传播重量，但仍计入该容器的体积、格数、封印、绑定和禁制。
- 戒指未装备时，容器处于 `sealed` 或定义指定的只读状态，不能被普通背包遍历；它并不自动消灭内容。
- 卸装时若内部仍有物品，必须由定义明确 `reject_if_nonempty`、`seal_in_place` 或 `transfer_to_target` 策略。未满足策略不得卸装，绝不能让内容丢失。

### 命令与查询

```text
MoveItem(command_id, actor_ref, item_id, from_location, to_container_id,
         quantity?, expected_revisions, idempotency_key)
SplitStack(command_id, item_id, quantity, target_container_id, expected_revisions)
MergeStacks(command_id, source_item_id, target_item_id, expected_revisions)
OpenContainer(command_id, actor_ref, container_id, access_context)
QueryAccessibleInventory(actor_ref, access_context, revision_vector)
QueryEncumbrance(carrier_ref, revision_vector)
```

The embodied bridge's internal counterpart is deliberately narrower than a
general inventory command:

```text
RetrieveToCustody(command_id, actor_ref, asset_ref, item_id,
                  source_container_id, destination_receiver_ref,
                  expected_definition_id?, idempotency_key)
```

It is callable only after a policy/settlement layer has resolved its arguments.
The client never sends these references. `destination_receiver_ref` must be a
registered, currently empty physical custody receiver; it is not an inferred
node or a display attachment. An accepted command atomically appends
`inventory.custody_changed`, `gameplay.inventory.item_transferred_out`,
`scene.occupancy.changed`, and `embodied.inventory.retrieved`, then refreshes
the custody/receiver read models after commit. Repeating the same key replays
the prior transaction before checking mutable source state.

命令只表达意图。`OpenContainer` 的成功只授予本次读模型访问，不能绕过后续 `MoveItem` 的 authority 校验。所有写命令必须包含相关容器的预期 revision；跨领域命令还必须携带 settlement 生成的 transaction context。

## 事件与命令流

最小事件集：

```text
ItemInstantiated / ItemDestroyed
ContainerCreated / ContainerAccessPolicyChanged / ContainerSealed
ItemPlacedInContainer / ItemRemovedFromContainer / ItemMoved
ItemStackSplit / ItemStacksMerged
ContainerCapacityRejected
EncumbranceRecomputed
```

普通移动的结算顺序为：

```text
MoveItem
-> 校验 actor 权限、物品生命周期、原位置、目标容器访问与容量
-> 预留源/目标容器 revision
-> authority settlement 生成位置变化 proposal
-> 原子追加 ItemRemovedFromContainer + ItemPlacedInContainer（或 ItemMoved）
-> 重建位置索引与 EncumbranceProjection
-> 发送带 revision 的 Godot inventory/encumbrance delta
```

购买、赠与和装备不得自行调用“先移物品、后扣钱”流程；它们在同一 `transaction_id` 原子事件批次中组合库存、物权、账户和装备事件。重放时只读取事件，不调用外部背包逻辑。

负重投影从可达容器树计算：默认容器将内容总重量向宿主传播；特殊容器使用定义声明的传播策略。循环嵌套、超过最大深度或同一物品双重可达必须在启用/结算时拒绝。投影应保存每个来源的重量贡献，以供 UI、能力可用性和解释链读取。

## 权威不变量

1. 同一活跃物品实例在任何权威 revision 下至多有一个位置。
2. 任何容器内容都必须满足容量、访问、封印、绑定与禁制规则。
3. 位置变化只由后端 settlement 追加事件；Godot 本地拖拽仅是预测或请求。
4. 库存位置、物权和装备效果不可互相替代：持有不等于拥有，拥有不等于已装备。
5. 角色是 `Actor`，不进入库存图；对角色的指挥/监护/租用权仅由关系或物权契约表达。
6. `EncumbranceProjection` 是可丢弃读模型，必须能从物品与装备事件重建。

## 失败语义与恢复

失败返回统一结构化结果，并至少包含 `error_code`、`failed_stage`、`source_refs`、`expected_revision`、`actual_revision?`、`retriable` 与 `recovery_action`。

| 场景 | `error_code` | 权威写入 |
| --- | --- | --- |
| 原位置不匹配或 revision 冲突 | `inventory.revision_conflict` | 无 |
| 无访问权、封印或绑定限制 | `inventory.access_denied` | 无 |
| 目标超重、超容积或无槽位 | `inventory.capacity_exceeded` | 无 |
| 容器环、深度超限或非法宿主 | `inventory.invalid_topology` | 无 |
| 特殊容器卸装策略未满足 | `inventory.container_exit_blocked` | 无 |
| 投影故障 | `projection.rebuild_required` | 事件保留，重建投影 |

同一幂等键重复提交必须返回原结算结果而非再次移动物品。客户端漏失或乱序 delta 时丢弃局部状态并请求完整 snapshot；不得据此猜测物品位置。

## Acceptance Criteria

1. 从空事件流创建背包、物品、嵌套容器并重放，位置与负重投影完全一致。
2. 一次普通移动原子改变源和目标；失败时两者均不变。
3. 容量、封印、绑定、revision 冲突和循环嵌套均返回明确错误且无部分提交。
4. 储物戒验证自身计重、内容不向佩戴者传播重量、卸装非空策略和重放一致性。
5. 物品位置变化不会改变 `OwnershipRight`；丢失地契物品不会删除土地权利。
6. Godot 只能消费带 revision 的镜像，预测拒绝后能够恢复到权威快照。
7. A custody-to-inventory stow followed by internal retrieve preserves the same
   `item_id`, does not transfer ownership, leaves no stale tracked receiver
   occupancy, and has no partial event batch on source/container/receiver
   rejection.

## Harness Mapping

- `gameplay-foundation-contract`：模型、命令、事件和错误 schema。
- `gameplay-possession-equipment`：容器移动、嵌套、储物戒和装备协作。
- `gameplay-event-replay`：库存事件重放、检查点等价和幂等。
- `adventure-basic`：购剑入包、装备、负重与容器失败场景。
