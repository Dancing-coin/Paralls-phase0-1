# Adventure Basic Reference Pack Design

Status: `partially-implemented; scenario-1-backend-verified; broader-closure-planned`

Date: `2026-07-23`

## Purpose

定义首批 `adventure-basic` 参考玩法包，用一个连贯但刻意收窄的冒险流程证明 Character Gameplay Foundation 可以承载资源、身体、状态、技能约束、背包容器、储物戒、装备、交易、经济和物权，而不是只通过合成 schema fixture 自证。

该包是纵向参考实现，不是完整 RPG、战斗系统或经济模拟。

## Current Implementation Status

The strict, digest-checked `assets/gameplay/adventure-basic/manifest.json`
baseline and `adventure-basic` harness profile are implemented. Scenario 1 now
has a backend-only, explicit-seed composition that reuses the existing fixed
offer and equipment authority services to purchase and equip the iron sword.
It proves its two separate atomic settlement batches and insufficient-funds
zero-write rejection. It does not activate the Patch, prove replay or mirror
delivery, or provide Godot UI/equipment presentation evidence.

## Scope

- health/stamina 资源、疲劳/右臂伤势、overloaded 状态和有效属性。
- 已学习剑术、挥砍动作及即时 affordance 阻断。
- 背包、长剑、地契、实体/抽象货币和特殊 storage ring 容器。
- right_hand、finger_accessory 装备槽及装备 grant。
- 固定报价买卖、赠与、产权转移、债务/契约原语的最小验证。
- Godot 状态条、背包、装备外观、交易反馈及预测回滚。
- patch install/enable/disable/upgrade、完整事件重放与 checkpoint 等价验证。

## Non-goals

- 不实现完整战斗 encounter、敌人 AI、伤害平衡或连招系统。
- 不实现修炼、功法、境界、瓶颈或突破闭环；只验证相关扩展接口不会污染核心。
- 不实现供需、动态价格、商人经营、税费、生产消费或区域市场。
- 不实现制作、建造、任务、组织、完整关系图或 Siming 知识图 runtime。
- 不提供生产级内容编辑器、美术资产库或存档 UI。
- 不允许 Godot 或玩法脚本直接写权威状态。

## Dependencies

- `2026-07-23-foundation-invariants-and-domain-boundaries-design.md`
- `2026-07-23-state-group-registry-and-runtime-facade-design.md`
- `2026-07-23-event-sourcing-and-authority-settlement-design.md`
- `2026-07-23-resource-status-body-and-effective-stats-design.md`
- `2026-07-23-inventory-container-and-encumbrance-design.md`
- `2026-07-23-ownership-economy-and-transaction-design.md`
- `2026-07-23-equipment-runtime-design.md`
- `2026-07-23-skill-ability-graph-and-affordance-design.md`
- `2026-07-23-gameplay-patch-rule-ir-and-capabilities-design.md`
- `2026-07-23-godot-runtime-mirror-and-prediction-design.md`
- `2026-07-23-persistence-replay-migration-and-hot-reload-design.md`

## Pack Manifest

最小 manifest：

```yaml
patch_id: adventure-basic
version: 0.1.0
maturity: reference
dependencies:
  - gameplay-foundation >=0.1
registered_state_groups:
  - resources
  - status_tags
  - body_runtime
  - inventory
  - ownership
  - equipment
  - skills
  - ability_affordances
  - effective_stats
required_capabilities:
  - authority.resource_effect_proposal
  - authority.inventory_effect_proposal
  - authority.economy_effect_proposal
  - authority.equipment_effect_proposal
verification_profile: adventure-basic
```

包只声明 Rule IR、definitions、seed fixture 和 Godot bindings；复杂处理器必须使用 foundation 已注册的受信任 capability，包内不得携带任意 Python/GDScript。

## Reference Content

### Actors And Accounts

```text
char_player
merchant_iron
account:char_player:copper
account:merchant_iron:copper
```

初始玩家账户余额 `120 copper`，商人账户余额可容纳交易收入。账户 revision 纳入所有经济命令 expected revision set。

### Resources And Body

| Definition | Initial | Rule |
|---|---:|---|
| `health` | 100/100 | 首批只用于伤势影响展示，不做完整伤害战斗 |
| `stamina` | 60/60 | 挥砍消耗 15；低于 15 时动作被阻断 |
| `fatigue` | 0 | 高疲劳可增加 stamina cost modifier |
| `right_arm_function` | 1.0 | 低于阈值时 sword swing 被阻断 |

状态标签：

- `right_arm_injured`
- `overloaded`
- `exhausted`
- `weapon_equipped`

`effective_stats` 至少投影 `carry_capacity`、`movement_speed_multiplier`、`sword_control`，并可解释所有 modifier source。

### Skills And Actions

稳定能力图 seed：

```text
skill:swordsmanship.basic --binds--> action:sword.swing
skill:swordsmanship.basic --binds--> action:sword.guard
```

`action:sword.swing` 前置条件：

- 玩家永久掌握 `swordsmanship.basic`。
- `right_hand` 装备拥有 `weapon:sword` tag 的 item。
- stamina >= 15。
- `right_arm_function` 高于最低阈值。
- 不存在 `stunned` 等阻断 tag。

满足条件只表示可提交动作；真实 stamina 消耗仍由 settlement 产生事件。

### Items And Containers

| ID | Kind | Weight | Key rules |
|---|---|---:|---|
| `item:iron_sword:001` | unique sword | 3.0 | 可装备 right_hand，授予 sword action binding |
| `item:storage_ring:001` | unique ring/container activator | 0.1 | 装备后开放内部容器 |
| `item:land_deed:001` | document | 0.05 | 可引用 land right，但不是产权本体 |
| `item:copper_coin_stack:*` | stackable currency item | per unit | 可选实体货币测试 |

容器：

```text
container:char_player:backpack
  max_weight: 20
  max_volume: 30
  content_weight_propagation: normal

container:ring:001:interior
  max_volume: 100
  max_slots: 50
  content_weight_propagation: none_to_wearer
  denies_tags: [living, oversized, unstable]
  access_requires: equipment slot finger_accessory contains item:storage_ring:001
```

储物戒本体计入负重；内部物品不向 wearer 传播重量，但仍参与容积、格数、绑定和禁制校验。

### Equipment

首批槽位：

```text
right_hand
finger_accessory
```

长剑装备 grant：

- 激活 sword weapon requirement。
- 提供来源明确且可撤销的 combat/effective-stat modifier。
- 发送 Godot weapon attachment presentation binding。

储物戒装备 grant：

- 激活 ring interior container access。
- 发送 Godot accessory presentation binding。

卸装必须撤销全部 grant。若储物戒内部非空，reference policy 固定为 `reject_non_empty`，返回结构化失败；不得让内容消失或静默落地。

### Ownership And Economy

固定商品：

```text
iron_sword price: 80 copper
storage_ring price: 30 copper
land_plot_09 price: 100 copper (independent scenario seed)
```

首批支持：

- 账户余额购买。
- 具象物品赠与。
- `OwnershipRight` 转移。
- `DebtClaim` 与 `ContractRecord` 的创建/查询/结清原语 fixture。
- 原子 `EconomicTransaction` 审计投影。

不支持动态报价、供需、税费和信用评分。

## Scenario 1: Buy And Equip The Sword

### Commands

```text
economy.purchase_offer
equipment.equip_item
```

购买命令 read set：玩家/商人账户、商品库存容器、item/offer、目标背包、ownership policy 和对应 revisions。

成功 settlement 在同一个 `transaction_id` 原子追加：

```text
economy.balance_debited(player, 80)
economy.balance_credited(merchant, 80)
inventory.item_transferred(merchant_stock -> player_backpack)
ownership.item_title_transferred(merchant -> player)
economy.transaction_recorded
```

如果实现选择在成交时创建实例，则 `item_created` 必须在同一批次中，且 offer 库存仍能证明供应来源。任何一步失败整批不提交。

装备 settlement 原子追加：

```text
inventory.item_removed_from_container
equipment.item_equipped(right_hand)
equipment.grant_activated
effective_stats.recalculation_requested
```

投影更新后 Godot 显示长剑、right_hand 槽位和 affordance 变化。Godot 的挂载动画不构成装备成功证据。

### Failure Cases

- 余额不足：`insufficient_funds`，余额、库存、产权不变。
- offer 过期：`offer_not_active`。
- 背包容量不足：`container_capacity_exceeded`，不扣款。
- item 已被购买/revision 冲突：`revision_conflict`。
- wrong slot：`equipment_slot_incompatible`，物品仍在原容器。

## Scenario 2: Body And Resource Constraints

初始稳定能力图始终包含 `swordsmanship.basic` 和 sword actions。

流程：

1. 装备长剑，affordance 为 available。
2. 通过权威 fixture 记录 `right_arm_injured`，降低 `right_arm_function`。
3. resolver 输出 `action:sword.swing` blocked，理由为 `body_function_insufficient`。
4. 执行请求被 settlement 拒绝，stamina 不消耗。
5. 通过治疗/fixture 的 authority event 恢复手臂功能，affordance 自动恢复，无需重新学习技能。
6. 将 stamina 降至 10，再次请求挥砍，返回 `resource_insufficient` 且无消耗。

必须区分：

```text
learned=true
granted_by_equipment=true
currently_available=false
blocked_reasons=[...]
```

## Scenario 3: Storage Ring And Encumbrance

流程：

1. 玩家装备 storage ring，激活内部容器访问。
2. 把重量 12 的测试货物从 backpack 转入 ring interior。
3. backpack/container 投影显示真实位置已变化。
4. wearer 负重只包含戒指本体及其他随身传播重量，不包含内部货物重量。
5. 尝试放入 `living` 或超容积物品被拒绝，无部分移动。
6. 戒指内部非空时卸装，按 `reject_non_empty` 返回失败，装备、grant、容器内容均不变。
7. 清空后卸装成功，撤销容器访问和表现绑定。

负重解释必须列出每个 item、容器传播策略、被排除重量和 source ref，不能只返回总数。

## Scenario 4: Property Right And Deed Separation

独立 seed 保证玩家有足够余额购买 `land_plot_09`。

成功购买原子批次：

```text
economy.balance_debited
economy.balance_credited
ownership.right_created_or_transferred(asset_ref=land_plot_09)
inventory.item_transferred_or_created(item:land_deed:001)
economy.transaction_recorded
```

随后把地契丢到 world container：

- `ItemInstance` 位置变化。
- `OwnershipRight.legal_holder` 不变。

产权转移必须提交独立 `ownership.transfer_right` command，校验 holder、受让人、资产限制、凭证 policy 和 revisions。移动地契物品不能隐式转移产权。

## Scenario 5: Gift, Debt And Contract Primitives

该场景保持最小：

- 玩家赠与已拥有且可转让的普通 item，inventory 与 title 在同一批次转移。
- 创建一条经双方/authority policy 认可的 `DebtClaim` 和关联 `ContractRecord`。
- 部分或全部偿付通过原子账户变更和 debt event 更新 outstanding amount。
- 删除合同文书 item 不会删除 contract/debt truth。

本场景证明经济基础能支撑后续玩法，不实现利息、违约评级、法院或动态信用系统。

## Godot Experience Contract

Godot 至少显示或可观测：

- health/stamina 状态条。
- right-arm injury、overloaded 和 blocked reason。
- backpack/ring contents、负重和容积。
- right_hand/finger slot 与装备外观。
- copper balance、购买 pending/success/failure。
- land right 与 deed item 在不同 UI projection 中。

客户端可对 equip 和普通 action 使用可回滚 pending 表现；购买、产权和债务不能预测为 confirmed。所有最终显示从 mirror authority revision 收敛。

## Patch Lifecycle

### Install

校验所有 definitions、Rule IR、依赖、capability、Godot binding 和 event versions。失败时不注册半个包。

### Enable

对适用 world/actor materialize 状态组和 seed fixture，产生可重放配置/初始化事件。重复 enable 幂等。

### Disable

- 停止接受新的 `adventure-basic` 命令和产生新规则事件。
- 已有 item、余额、产权和历史事件不得删除。
- 状态组按 foundation policy 进入 dormant/read-only；跨包仍在使用的 foundation 组不得卸载。
- 活跃 transaction 固定旧 patch revision 并先完成或明确拒绝。

### Upgrade

`0.1.x` fixture 至少证明：旧 transaction 使用旧 revision，新 command 使用新 revision；upcaster/rebuild 后投影等价。禁止升级时原地改写历史 event payload。

## Full Replay And Checkpoint Protocol

每个场景从空 store 执行后保存：

```text
ordered event streams
transaction batch boundaries
final per-domain revisions
CharacterGameRuntimeState façade
Godot-visible snapshot
explanation outputs
```

验证路径：

1. 清空所有 projection，从创世事件完整重放。
2. 比较每个 domain projection、revision vector 和 façade canonical serialization。
3. 从中间 checkpoint 加载，再重放 checkpoint 后事件。
4. 比较 checkpoint 路径与完整重放路径。
5. 用最终后端 snapshot 驱动 Godot mirror，比较可见字段和 revisions。

比较必须排除明确声明为非确定性的观测字段（例如运行耗时），业务状态、来源、顺序和解释结果必须确定。

## Authority And Privacy Invariants

1. 所有资源、物品、产权、装备和债务变化由后端 authority settlement 产生事件。
2. 跨域交易使用单一 transaction ID 原子追加事件批次，失败时零部分提交。
3. `CharacterGameRuntimeState`、affordance、负重、交易记录和 Godot snapshot 都是可重建投影。
4. 地契 item 与土地 right 是不同 aggregate；物理位置不决定产权。
5. 稳定技能与即时可用性分离；伤势或资源不足不删除学习事实。
6. 储物戒只改变重量传播和访问规则，不让物品脱离真实容器/所有权。
7. Godot prediction、动画或 UI 不能成为经济或 world truth。
8. fixture 不使用 actor-private 关系或隐藏信息绕过权限。

## Failure Semantics

所有失败返回 foundation 统一结构：

```text
error_code
message
retriable
command_id
transaction_id
failed_stage
failed_precondition
expected_revision / actual_revision
source_refs
recovery_action
```

规则：

- precondition 失败不追加任何 authority event。
- 原子 batch 持久化失败不提交任何成员事件。
- retry 使用原 idempotency key，不能重复扣款、赠与或创建产权。
- projection 失败不回滚已提交 event；隔离 projection 并从 event/checkpoint 重建。
- Godot delta 问题不重提经济命令；只请求 snapshot/result lookup。
- 未知 patch/event version fail closed，不跳过历史。

## Acceptance Criteria

### Functional

1. 玩家能以固定报价购买长剑，余额、商人余额、物品位置、title 和 transaction 同批提交。
2. 玩家能装备/卸装长剑，所有 grant、modifier、affordance 和 Godot binding 可逆。
3. 右臂伤势和 stamina 不足分别阻断挥砍，不删除 swordsmanship 学习事实且不错误消耗资源。
4. 储物戒内部重量不传播给 wearer，容积/禁制仍有效，非空卸装按固定 policy 拒绝。
5. 地契丢失不消灭土地 right，产权只能由独立 authority transaction 转移。
6. 赠与、债务/契约创建和偿付展示正确原语边界。

### Failure And Consistency

7. 余额不足、容量不足、槽位不兼容、revision conflict 和非法物品均产生结构化失败且零部分提交。
8. 重复 purchase command 只产生一次交易。
9. 完整重放、checkpoint 加增量重放和在线 projection 的 canonical 结果完全一致。
10. patch enable/disable/upgrade 不删除历史或破坏重放。
11. 每个 modifier、能力 grant、blocked reason、负重排除、产权和交易均能解释 source refs。

### Cross-runtime

12. Godot snapshot/delta 最终与后端 façade 的可见状态和 revision vector 一致。
13. equip/action prediction 可确认或回滚；经济/产权不被本地确认。
14. 实际 Godot scene/runtime probe 显示 UI/装备/失败反馈可观察且无立即脚本错误。

### Scope Guard

15. 包不注册 cultivation state/runtime，不实现动态市场价格，也不依赖关系图或 Siming 图 runtime。

## Harness Mapping

主要 profile：`adventure-basic`。The current profile proves the manifest
baseline only; it must expand scenario-by-scenario as each authority slice is
implemented and verified.

| Scenario | Required evidence |
|---|---|
| buy/equip sword | backend command, atomic event batches, and projections proved; mirror/Godot planned |
| body/resource block | stable ability plus blocked affordance and zero cost |
| storage ring | container move, weight explanation, invalid move and unload rejection |
| property/deed | independent item location and ownership right revisions |
| gift/debt/contract | title/account/debt atomic event evidence |
| replay | online vs full replay vs checkpoint canonical diff |
| patch lifecycle | enable/disable/upgrade and rebuild report |

依赖 profile：

- `gameplay-foundation-contract`
- `gameplay-event-replay`
- `gameplay-state-groups`
- `gameplay-possession-equipment`
- `gameplay-economy-authority`
- `gameplay-patch-runtime`
- `godot-gameplay-mirror`

聚合 profile：`gameplay-foundation-all`。

Harness 必须把结构化报告、事件批次摘要、replay canonical hashes、失败矩阵、Godot runtime log 和最终 revision comparison 写入 `.harness/verification/`。单元测试通过但没有完整重放和真实 Godot runtime 证据时，只能报告后端部分完成。
