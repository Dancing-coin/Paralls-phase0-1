# Equipment Runtime Design

Status: `partially-implemented; broader-closure-planned`

Date: `2026-07-23`

## Purpose

定义装备从可携带 item 转换为角色当前 loadout 的权威运行时协议。一次装备或卸装必须同步处理 item placement、身体/装备槽位、modifier、ability grant、附属容器访问和 Godot presentation refs，并以完整事件溯源和单一原子事件批次保证所有效果一起激活、一起撤销或完全不发生。

装备状态不是 Godot 节点挂载结果，也不是物品 definition 中的布尔值。它是 backend authority 在 pinned item/body/inventory/policy revisions 上结算得到的可重建事实。

## Scope

- equipment profile、slot definition、loadout 与 occupancy 模型；
- 身体部位、槽位兼容、互斥组、层级和双手占用；
- equip/unequip/swap 命令和跨域原子事件流；
- modifier activation/deactivation；
- ability/action grant activation/deactivation；
- 装备提供的容器访问与传播 policy activation/deactivation；
- Godot presentation refs 的权威绑定状态与本地表现应用；
- revision、幂等、失败恢复、replay 和解释查询。

## Current Implementation Boundary

The repository implements only the first backend authority slice: one item can
move from a validated inventory container into one compatible equipment slot,
and later return to a validated destination container. Inventory placement,
equipment activation/deactivation, activation-scoped ability-path grant
activate/revoke events, and registered modifier-source activate/deactivate
events are appended in one atomic batch. The grant and modifier each have the
activation as their source and are projected by their owning ability/modifier
domains; neither creates a learned-skill fact. Source-placement, body-function,
slot-conflict, revision, and idempotency checks occur before commit. The slice
also supports one multi-slot activation: every occupied slot is recorded under
the same activation, and a conflict in any required slot rejects the complete
batch. It also implements the minimum swap: old activation effects are revoked,
the outgoing item returns to a validated destination, and the incoming item
activates only if all its slots validate in the same batch. The focused
`gameplay-possession-equipment` profile proves this slice.

Equipment action/skill grants beyond the implemented path grant form, generic
modifier authoring and non-equipment sources, container access/propagation,
ownership/control policy, presentation bindings,
checkpoint replay equivalence, and Godot mirror delivery remain specified but
unimplemented.

## Non-goals

- 不定义完整技能图、affordance resolver 或 modifier 数学；
- 不定义 item ownership、购买、价格或债务；
- 不实现骨骼动画、IK、布料、模型导入或资源下载管线；
- 不允许 Godot attach/reparent 节点直接确认装备成功；
- 不实现无限层穿戴、自动最优配装、随机词缀生成或耐久系统；
- 不在装备域复制身体健康、资源、inventory placement 或 ownership 真相；
- 不允许卸装时静默删除、倾倒或隐藏附属容器内容物。

## Dependencies

- `2026-07-23-foundation-invariants-and-domain-boundaries-design.md`
- `2026-07-23-event-sourcing-and-authority-settlement-design.md`
- `2026-07-23-state-group-registry-and-runtime-facade-design.md`
- `2026-07-23-resource-status-body-and-effective-stats-design.md`
- `2026-07-23-inventory-container-and-encumbrance-design.md`
- `2026-07-23-skill-ability-graph-and-affordance-design.md`
- `2026-07-23-godot-runtime-mirror-and-prediction-design.md`
- `2026-07-23-gameplay-patch-rule-ir-and-capabilities-design.md`
- `../2026-06-29-execution-semantics-and-realization-runtime-design.md`

身体域拥有 anatomy/function projection；inventory 域拥有 item placement/container/control；ability/modifier 域拥有效果求值；Godot 只拥有本地 presentation 实例。装备域拥有 loadout、slot occupancy 和每次 activation 的生命周期编排。

## Domain Model And Interfaces

### Equipment profile

```text
EquipmentProfile
  profile_id
  profile_version
  compatible_slot_expressions[]
  required_body_capabilities[]
  occupied_slot_patterns[]
  conflict_groups[]
  layer_key?
  layer_order?
  modifier_templates[]
  ability_grant_templates[]
  container_access_templates[]
  propagation_policy_refs[]
  presentation_refs[]
  source_ref
```

profile 是版本化规则输入，不是运行态。item instance 通过 definition 引用 profile。每次 settlement 固定 profile/patch revision；升级 profile 不就地重写已经提交的历史 activation，reconcile 必须由显式命令和新事件完成。

### Slot and body binding

```text
EquipmentSlotDefinition
  slot_key
  body_part_selector
  accepted_tag_expression
  capacity: integer
  conflict_groups[]
  layer_policy_ref?
  required_body_functions[]
  source_ref

EquipmentSlotRuntime
  actor_ref
  slot_key
  resolved_body_part_refs[]
  availability: available | impaired | absent | disabled
  occupied_activation_ids[]
  source_revision_vector
```

slot 是 gameplay identity，不以 Godot bone name 或 scene path 为 ID。body part 缺失/失能时 availability 来自身体投影；装备域不能改写伤势。首批至少支持 `right_hand`、`left_hand`、`finger.*` 和注册的服装/护甲槽位。

### Loadout and activation

```text
EquipmentLoadout
  actor_ref
  activation_ids[]
  revision

EquipmentActivation
  activation_id
  actor_ref
  item_ref
  profile_ref
  occupied_slots[]
  source_placement_ref
  equipped_placement_ref
  modifier_instance_refs[]
  ability_grant_refs[]
  container_access_grant_refs[]
  propagation_policy_refs[]
  presentation_binding_refs[]
  status: active | deactivating | inactive
  activated_by_event_ref
  deactivated_by_event_ref?
```

`activation_id` 由成功 equip transaction 确定，并成为所有派生 grant/binding 的来源根。派生 ID 必须可重放稳定生成或直接记录在事件 payload 中。不能只按 item definition 撤销效果，因为同类 item 可以有多个 instance。

### Modifier activation

```text
EquipmentModifierInstance
  modifier_instance_id
  activation_ref
  target_ref
  modifier_definition_ref
  operation
  value
  priority
  stacking_key
  conditions[]
  source_ref
  status
```

装备事件激活/撤销 modifier instance；effective stats resolver 负责确定性排序和求值。撤销只撤销同一 `activation_ref` 创建的 instance，不能按宽泛 tag 删除其他来源 modifier。

### Ability and action grants

```text
EquipmentAbilityGrant
  grant_id
  activation_ref
  actor_ref
  ability_ref
  grant_kind: action | passive | capability
  availability_conditions[]
  source_ref
  status
```

装备长剑可激活 sword action grant，但不会创建“已学习 swordsmanship”的稳定技能事实。身体受伤、资源不足或环境条件可让 grant 当前不可用；这由 affordance projection 表达 blocked reason，不删除 grant 或学习事实。卸装只撤销该装备 activation 产生的 grant。

### Container access and propagation activation

装备可以提供附属 container capability：

```text
EquipmentContainerAccessGrant
  access_grant_id
  activation_ref
  subject_ref
  container_ref
  capabilities[]
  conditions[]
  source_ref
  status
```

储物戒 equip 后激活内部 container 的 access grant 和 `storage_ring.propagation.v1`；戒指本体质量传播、内部质量不向 wearer 传播。内部容积/质量/禁制仍由 inventory container 校验。首批非空卸装 policy 是 reject，因此 access 和传播 policy 不会在内容仍存在时被撤销。

### Presentation binding

```text
PresentationBinding
  binding_id
  activation_ref
  actor_ref
  item_ref
  presentation_ref
  anchor_semantic: right_hand | left_hand | finger | head | torso | other_registered
  variant_key?
  visibility_scope
  status: requested | active_projection | inactive
  source_ref
```

`presentation_ref` 是稳定资源引用，不是任意 filesystem path 或 Godot node path。authority event 确认应显示什么语义资产；Godot mirror adapter 将其解析到本地资源和 anchor。资源缺失只产生 presentation degradation/error，不回滚已经提交的 gameplay equip，除非 command policy 在结算前明确要求 asset readiness evidence。

### Query and proposal interfaces

```text
get_loadout(actor_ref, at_revision?) -> EquipmentLoadoutView
get_slot(actor_ref, slot_key, at_revision_vector?) -> EquipmentSlotView
can_equip(actor_ref, item_ref, requested_slots?, context) -> EquipDecision
can_unequip(actor_ref, activation_ref, destination_ref, context) -> UnequipDecision
explain_activation(activation_ref) -> EquipmentExplanation
get_presentation_bindings(actor_ref, privacy_scope) -> PresentationBindingView[]

propose_equipment_effect(command, pinned_context) -> EquipmentEffectProposal
validate_equipment_proposal(proposal, pinned_context) -> ValidationResult
apply_equipment_event(state, event) -> state
```

`can_equip` 只提供 revision-bound 决策提示，不预留槽位，也不保证之后命令成功。最终 authority settlement 必须重新验证同一 expected revisions。

## Commands And Event Flows

### Commands

```text
equipment.equip_item
equipment.unequip_item
equipment.swap_item
equipment.reconcile_activation_by_policy
equipment.force_deactivate_by_authority
```

普通客户端只能提交前三种 structured command。reconcile/force 命令仅供 patch migration、身体结构变化或管理员修复，并仍产生完整事件与 audit evidence。

### Equip pipeline

```text
1. 校验 command、principal、actor/item identity、idempotency 与 expected revisions
2. 固定 item profile、body、inventory、equipment、modifier/ability 与 patch revisions
3. 验证 item active，actor 具有 equip control，source placement 可访问
4. 解析兼容 slots/body parts，检查 availability、capacity、layers、conflicts
5. 检查 required body capabilities 与 equipment policy
6. 请求 inventory 域验证 source remove 和 equipped placement
7. 实例化 modifier、ability、container access、propagation 和 presentation bindings
8. 验证完整 candidate batch 与 deterministic IDs
9. authority settlement compare revisions 并原子 append
10. transaction-boundary projector 更新 loadout/effective stats/affordance/encumbrance/Godot mirror
```

典型长剑 equip 批次：

```text
inventory.item_removed_from_container
inventory.item_placed_in_equipment_slot
equipment.slot_occupied
equipment.activation_started
modifier.equipment_modifier_activated
ability.equipment_grant_activated
inventory.encumbrance_inputs_changed
equipment.presentation_binding_activated
equipment.activation_completed
```

事件顺序由 transaction sequence 固定，对外投影只在完整 transaction boundary 发布。`activation_completed` 不是修补先前部分提交；所有事件仍属于同一不可分 batch。

### Unequip pipeline

卸装必须先验证 destination container、容量、访问和 item 控制，再形成撤销批次：

```text
equipment.presentation_binding_deactivated
ability.equipment_grant_deactivated
modifier.equipment_modifier_deactivated
equipment.container_access_deactivated?
equipment.propagation_policy_deactivated?
equipment.slot_released
inventory.item_removed_from_equipment_slot
inventory.item_placed_in_container
inventory.encumbrance_inputs_changed
equipment.activation_ended
```

若附属容器 non-empty policy 为 reject（首批储物戒），在形成 proposal 前拒绝，所有 grant、slot、placement 和 binding 保持 active。不能先隐藏模型或撤销访问再发现无法卸装。

### Swap and multi-slot items

swap 不是两个独立命令。它在一个 transaction 中验证旧 item 的目标 placement、新 item 的 source placement、全部 slot conflicts 和所有 grants，然后原子撤销旧 activation 并激活新 activation。双手物品或多槽装备只创建一个 activation，包含多个 slot occupancy；任一 slot 不可用则零提交。

### Body change and reconciliation

身体部位突然失能/缺失不会让装备域静默编辑 loadout。body event 使 equipment/affordance projection 标记 activation 为 `blocked` 或 `reconciliation_required`；注册 policy 再提交显式 reconcile command：

- 保留装备但禁止相关 action；
- 原子卸装到合法 destination；
- authority force-deactivate 并进入 recovery container。

选择必须由 source policy 记录并可重放，绝不能因 Godot bone 消失删除 item。

## Authority Invariants

1. loadout、slot occupancy 和 activation 生命周期只能从已提交 event stream 重建。
2. Godot attach、动画、资源加载和本地 prediction 都不是装备权威事实。
3. 一次 equip/unequip/swap 涉及的 placement、slot、modifier、ability、container access、propagation 与 presentation events 必须同批全提交或零提交。
4. 每个 active activation 必须引用一个 active item instance、完整 occupied slots 和唯一 equipped placement。
5. 同一 slot 的占用不得超过 capacity；互斥组、layer 与多槽约束使用 pinned policy 一次验证。
6. modifier/grant/access/binding 都必须引用 activation source；撤销仅影响同一 activation 创建的对象。
7. 装备 ability grant 不等于稳定技能学习事实，阻断当前使用也不删除 grant 或学习事实。
8. inventory placement、custody/control、ownership right 和 equipment activation 彼此分离，不得互相隐式覆盖。
9. 非空储物戒在首批 policy 下不可卸装；戒指本体计重，内部物不向 wearer 传播但仍受内部 capacity/禁制。
10. presentation binding 失败不得伪造 gameplay rollback；presentation refs 必须经过允许列表/registry 解析。
11. profile/patch upgrade 不改写历史 activation；活跃事务固定旧 revision，新事务使用新 revision。
12. correction/reconciliation 通过显式 command 和新事件完成，不直接修 projection。
13. 完整 replay、checkpoint replay 与在线 projection 必须产生相同 loadout、grants 和 bindings。

## Failure Semantics

失败统一返回 `SettlementFailure`，`details` 可包含安全裁剪的 slot、item、activation、destination 和 source rule refs。

| Error code | Failed precondition | Commit | Recovery |
| --- | --- | --- | --- |
| `equipment_item_not_equippable` | item 无有效 profile/状态 | none | 选择可装备 item |
| `equipment_control_denied` | actor 无 equip/unequip control | none | 获取授权；不泄漏隐藏 owner |
| `equipment_slot_unknown` | slot 未注册 | none | 刷新 body/loadout schema |
| `equipment_slot_unavailable` | body part 缺失、失能或 slot disabled | none | 恢复身体条件或选其他 slot |
| `equipment_slot_incompatible` | tags/profile 与 slot 不匹配 | none | 选择兼容 slot/item |
| `equipment_slot_occupied` | capacity/conflict group 阻断 | none | 使用 swap 或先卸装 |
| `equipment_layer_conflict` | 穿戴层级非法 | none | 调整 layer 组合 |
| `equipment_body_requirement_failed` | required function/capability 不满足 | none | 恢复条件或选择其他装备 |
| `equipment_source_placement_mismatch` | item 不在声明 source | none | 刷新 inventory 后重提 |
| `equipment_destination_rejected` | 卸装目标容量/访问失败 | none | 选择合法 destination |
| `equipment_container_non_empty` | 附属容器 policy 禁止卸装 | none | 原子清空容器后重提 |
| `equipment_activation_not_found` | activation 已撤销或不可见 | none | 刷新 loadout |
| `equipment_effect_proposal_invalid` | grant/modifier/binding 不可注册或 ID 冲突 | none | 修复 profile/patch；禁止部分激活 |
| `equipment_presentation_ref_unregistered` | presentation ref 不在 registry | none when readiness required | 修复内容包或选择 fallback policy |
| `revision_conflict` | item/body/inventory/equipment/policy 任一 revision 变化 | none | 刷新完整上下文后新命令重提 |
| `atomic_append_failed` | batch commit 未确认 | none/unknown | 用原 idempotency key 查询事务状态 |

提交后 Godot 资源加载失败返回本地 `presentation_asset_unavailable`，但 authority equip 保持 committed；客户端使用注册 fallback/隐藏视觉并报告 binding ID。projection apply 失败隔离相关 projector，从 event/checkpoint 重建，不能通过再发 equip 命令修复投影。

Godot 可先显示 pending equip 表现，但必须：

- 绑定 prediction ID；
- 不提前启用权威 ability、modifier 或 container access；
- success 时以 confirmed activation/binding refs 替换 pending；
- rejection、revision gap 或 schema incompatibility 时回滚 pending 并请求 snapshot。

## Acceptance Criteria

1. 长剑从 backpack 装备到 `right_hand` 时，placement、slot、activation、modifier、sword action grant、encumbrance input 和 presentation binding 同批提交。
2. 长剑卸装时只撤销该 activation 的效果并原子放入目标容器；其他装备来源的 modifier/grant 不受影响。
3. slot occupied、身体不满足、无控制权、目标容器满和 revision conflict 均结构化拒绝且 event count 不变。
4. batch 任一 event 的 fault injection 不产生“物品已移走但 slot/grant 未激活”或其逆向状态。
5. 两个命令竞争同一 slot/revision 时至多一个成功，失败方刷新后才能重提。
6. 双手/多槽 item 对所有 slot 一次占用、一次释放，不能出现半边装备。
7. swap 在单一 transaction 中完成旧 activation 撤销和新 activation 激活，任何前置条件失败都保留原 loadout。
8. 右臂受伤时稳定 swordsmanship 学习事实不变；sword grant/affordance 展示身体阻断且非法 action 不消耗资源。
9. 储物戒装备后激活内部 container access 和传播 policy；wearer 负重只含戒指本体，内部容量/禁制继续生效。
10. 非空储物戒卸装返回 `equipment_container_non_empty`，slot、access、传播、binding 和内部 item 均不变。
11. presentation binding 含稳定 asset/anchor refs；Godot 资源缺失时 gameplay equip 仍与权威状态一致并使用明确 degradation。
12. prediction reject 能按 prediction ID 回滚本地模型/UI，不留下 modifier、action 或 container access 假状态。
13. profile/patch 升级期间活跃事务使用 pinned revision；后续 reconcile 以新事件表达且旧 replay 不变。
14. 完整重放、checkpoint 加增量重放和在线 projection 的 loadout、slot、grant、modifier、access 与 binding canonical state 相同。
15. explain activation 能追溯 item/profile/patch/body slots、每个 effect source、事务和撤销事件。

## Harness Mapping

### Current review gate

- `python scripts/verification/harness.py --profile docs`

### Required implementation profiles

- `gameplay-foundation-contract`
  - equipment profile、slot、activation、grant、binding 与 failure schemas；
  - unknown version/ref fail-closed。
- `gameplay-event-replay`
  - activation/grant 生命周期、swap、多槽占用与 deterministic ID；
  - online/full replay/checkpoint canonical diff。
- `gameplay-possession-equipment`
  - equip/unequip/swap 原子批次；
  - slot/body/capacity/control failures；
  - 储物戒 access、传播和非空卸装策略。
- `gameplay-state-groups`
  - equipment/ability/modifier/container state groups 的启用、dormant 与 façade 投影。
- `godot-gameplay-mirror`
  - presentation binding snapshot/delta、pending confirm/reject、资源缺失和 revision resync。
- `gameplay-patch-runtime`
  - profile source、pinned revision、upgrade/reconcile 和 capability proposal boundary。
- `adventure-basic`
  - 购买后装备长剑、身体阻断、储物戒完整闭环。
- `gameplay-foundation-all`

证据必须包含 committed transaction batch、失败时零事件、grant/modifier/access source explanation、Godot binding runtime probe 和 replay 对比。只验证槽位 UI 或场景节点存在不构成 authority 完成证据。
