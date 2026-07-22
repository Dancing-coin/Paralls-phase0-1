# Resource, Status, Body Runtime And Effective Stats Design

Status: `awaiting-user-review`

Date: `2026-07-23`

## Purpose

定义首批角色游戏数值底盘：可配置资源条、可溯源状态标签、身体运行态和只读有效属性投影。该底盘既能支撑 UI 与 Godot 表现，也能为技能 affordance、负重、装备、战斗和后续修炼 patch 提供一致输入。

本规格不把心理状态并入身体数值，也不预置一个所有项目和角色都必须拥有的状态全集。

## Scope

- `ResourceDefinition`、角色资源实例与资源 command/event；
- `StatusTagDefinition`、状态实例、叠加、持续期、互斥与移除；
- `BodyRuntimeState` 中的需求、伤势、功能、姿态和平衡；
- `Modifier`、`EffectiveStatsProjection` 与解释链；
- 四类状态组之间的确定性结算顺序；
- Godot/Mind Frame 所需的受限投影；
- 首批 adventure-basic 的身体和能力阻断用例。

## Non-goals

- 不定义完整战斗、医疗、生存或修炼内容；
- 不规定所有游戏必须使用 health、mana 或 hunger；
- 不把 `CharacterDynamicState`、情绪、需要张力或关系评价迁入本领域；
- 不允许 UI、Godot 或 patch 直接写 `effective_stats`；
- 不定义装备、能力图和负重容器的内部模型；
- 不支持未受控脚本自定义任意 modifier 执行代码。

## Dependencies

- `2026-07-23-foundation-invariants-and-domain-boundaries-design.md`
- `2026-07-23-state-group-registry-and-runtime-facade-design.md`
- `2026-07-23-event-sourcing-and-authority-settlement-design.md`
- equipment、ability affordance、inventory/encumbrance 与 gameplay patch 子规格（同一 spec tree）

## State Group Registration

首批定义四个独立组：

| Group ID | 权威输入 | 输出 |
| --- | --- | --- |
| `core.resources` | resource events | `ResourceStateProjection` |
| `core.status_tags` | tag lifecycle events | `StatusTagStateProjection` |
| `core.body_runtime` | body need/injury/function events | `BodyRuntimeStateProjection` |
| `core.effective_stats` | authored baseline + modifier sources | `EffectiveStatsProjection` |

`core.effective_stats` 是 `projection_only` 依赖组，不接受直接业务写 command。每个玩法包注册实际 resource/tag/stat definitions；角色只物化适用定义。

## Resource Model

### Definition

```text
ResourceDefinition
  resource_id: namespaced stable id
  definition_version
  numeric_type: integer | decimal
  min_policy
  max_policy
  initial_value_policy
  overflow_policy: clamp | reject | convert(effect_ref)
  depletion_policy_ref?
  regeneration_policy_ref?
  reservation_supported: boolean
  visibility_policy_ref
  ui_binding_hint?
  source_patch_revision
```

### Runtime projection

```text
ResourceEntry
  resource_id
  current
  effective_min
  effective_max
  reserved
  available
  regeneration_rate?
  lifecycle_state
  revision
  source_refs[]

ResourceStateProjection
  actor_ref
  entries: map<resource_id, ResourceEntry>
  projection_revision
  source_revision_vector
```

`available = current - reserved` 是投影结果。reservation 只能在 settlement 内部存在或以明确的短生命周期事件表达；不得在事务失败后残留幽灵预留。

### Commands and events

```text
AdjustResource(resource_id, delta, reason_ref)
SetResourceByPolicy(resource_id, target, authority_reason)
ReserveResource(resource_id, amount, reservation_ref)
ConsumeReservation(reservation_ref)
ReleaseReservation(reservation_ref)

ResourceMaterialized
ResourceAdjusted
ResourceReservationCreated
ResourceReservationConsumed
ResourceReservationReleased
ResourceBoundaryReached
```

普通玩法效果应使用 `AdjustResource`，不能使用无来源绝对赋值。`SetResourceByPolicy` 只用于初始化、迁移、管理员修复等明确 authority scope，并仍产生事件。

## Status Tag Model

### Definition

```text
StatusTagDefinition
  tag_id
  definition_version
  stack_policy: unique | stack_count | stack_intensity | independent_sources
  max_stacks?
  duration_policy: permanent | timed | source_bound | condition_bound
  refresh_policy: ignore | refresh | extend | replace
  exclusivity_group?
  conflict_priority?
  dispel_categories[]
  modifier_templates[]
  affordance_blocks[]
  visibility_policy_ref
  presentation_binding_ref?
  source_patch_revision
```

### Instance

```text
StatusTagInstance
  tag_instance_id
  tag_id
  target_actor_ref
  source_ref
  source_event_id
  applied_at
  expires_at?
  stack_count
  intensity
  lifecycle_state: active | suspended | expired | removed
  removal_reason?
```

每个 active effect 都必须有 source。`poisoned`、`stunned`、`overloaded`、`silenced` 等不能仅以无来源布尔字段存在。

### Commands and events

```text
ApplyStatusTag
RefreshStatusTag
RemoveStatusTag
DispelStatusTags
ExpireStatusTags

StatusTagApplied
StatusTagRefreshed
StatusTagStackChanged
StatusTagRemoved
StatusTagExpired
StatusTagApplicationRejected
```

定时过期由权威 scheduler 产生显式 `ExpireStatusTags` command。projector 不得仅根据本机当前时间把 tag 静默删除，否则 replay 会不确定。

## Body Runtime Model

`BodyRuntimeState` 描述角色此刻身体事实和功能结果，不复制完整骨骼动画姿态，也不承载心理情绪。

```text
BodyRuntimeStateProjection
  actor_ref
  needs: map<need_id, BodyNeedState>
  injuries: map<injury_id, InjuryState>
  functions: map<function_id, FunctionalCapacity>
  posture
  balance
  locomotion_mode
  contact_summary
  recovery_states[]
  projection_revision
  source_revision_vector
```

### Body needs

```text
BodyNeedState
  need_id: fatigue | pain | hunger | thirst | sleep_pressure | temperature | ...
  value
  band: nominal | strained | critical
  trend
  source_refs[]
```

need ID 仍由 patch 注册。band 由 definition threshold 投影得出，不应作为可独立修改的第二真相。

### Injury

```text
InjuryState
  injury_id
  body_region_ref
  injury_type
  severity
  functional_impacts[]
  bleeding_rate?
  pain_contribution?
  treatment_state
  source_event_id
  lifecycle_state
```

### Functional capacity

```text
FunctionalCapacity
  function_id: grip.right | locomotion.run | vision.left | balance | ...
  capacity_ratio
  status: available | impaired | unavailable
  contributing_source_refs[]
  explanation
```

功能状态是伤势、装备限制、姿态、tag 和环境约束的派生投影。能力 resolver 应读取 `FunctionalCapacity`，而不是硬编码读取某个 injury name。

### Commands and events

```text
ApplyInjury
TreatInjury
AdvanceBodyNeed
ChangePosture
RecordBodyRecovery

InjuryApplied
InjuryTreatmentRecorded
InjuryRecovered
BodyNeedAdvanced
PostureChanged
FunctionalCapacityInputsChanged
```

`FunctionalCapacityChanged` 可以作为 projection notification，但不能成为绕过 injury/tag 来源的独立权威赋值事件。

## Effective Stats And Modifier Model

### Baseline

baseline 来自 authored profile、archetype 或被权威接受的长期成长事件。短期 tag、装备和环境不能改写 baseline。

```text
StatBaseline
  stat_id
  value
  source_ref
  source_revision
```

### Modifier

```text
Modifier
  modifier_id
  stat_id
  operation: additive | multiplicative | override | clamp_min | clamp_max
  value
  priority
  stacking_key?
  stacking_policy: stack | highest | lowest | exclusive | replace_same_source
  condition_ref?
  source_ref
  source_event_id
  source_patch_revision
  lifecycle_state
```

modifier 必须由已注册 definition 模板或受信任 handler 的 typed proposal 创建。`priority` 只在规范允许的位置解决同类顺序，不能用任意 priority 掩盖冲突。

### Resolution order

```text
authored/growth baseline
  + accepted additive modifiers
  * accepted multiplicative modifiers
  -> conditional modifiers whose predicates are true
  -> compatible override policy
  -> clamp_min / clamp_max
  = effective value
```

为避免浮点与遍历顺序漂移：

- decimal scale 与 rounding mode 由 stat definition 固定；
- 同层 modifier 按 `(priority, stacking_key, source_ref, modifier_id)` canonical sort；
- exclusive/override 冲突无法按 definition 唯一裁决时，拒绝产生 projection 并报告配置错误；
- 相同输入 revision vector 必须产生相同数值和 explanation digest。

### Projection and explanation

```text
EffectiveStatEntry
  stat_id
  baseline
  effective_value
  accepted_modifiers[]
  rejected_modifiers[]
  clamp_trace[]
  explanation_digest

EffectiveStatsProjection
  actor_ref
  entries
  projection_revision
  source_revision_vector
```

`rejected_modifiers` 必须说明 `condition_false`、`lower_priority`、`exclusive_conflict`、`source_inactive` 等稳定 reason code。

## Cross-group Evaluation

一次 gameplay command 的读取顺序为：

1. 读取 pinned resource/status/body/inventory/equipment revisions；
2. 解析 active tags 与 source-bound lifecycle；
3. 从 body facts 计算 functional capacities；
4. 聚合 baseline 与 modifier sources；
5. 构建 effective stats；
6. ability affordance resolver 读取 resources、tags、functions、equipment 与 effective stats；
7. settlement 校验成本和阻断后才产生事件。

例：角色“已掌握剑术”但右臂骨折：稳定能力图不变；`grip.right=unavailable`；affordance 返回 `required_body_function_unavailable`；settlement 不消耗耐力，也不删除永久剑术 grant。

## Consumer Projections

### Godot view

可包含：

- 允许显示的 resource current/max/band；
- visible tag、stack、duration；
- animation/presentation 所需 body band 与 function summary；
- UI 所需 effective stat 值与简化解释；
- prediction policy 和 revision。

不得包含隐藏伤势来源、actor-private 心理状态或未发现的异常。

### Mind Frame view

角色只读取可自知、被感知或已进入记忆的身体/资源信息。隐藏毒素可以只表现为模糊不适，不因 backend 有 `poisoned` 事件而自动成为角色明确知识。

## Authority Invariants

1. 每个 resource/tag/body fact 都由事件产生并具有 source lineage。
2. resource current 永远满足 definition 的边界或明确 overflow conversion 结果。
3. reservation 与消费在同一 settlement 语义内闭合，失败不残留 reservation。
4. tag 过期由权威 command/event 表达，不能由客户端时钟删除。
5. injury 是事实输入，functional capacity 是派生投影；不得反向覆盖 injury。
6. effective stat 只读且可从 baseline + active modifiers 重建。
7. 装备、tag、环境和 buff grant 被撤销后，其 modifier 必须可靠失活。
8. 精神动态状态继续归 character mind，不与 body need 同字段双写。
9. Godot 可以预测资源条动画，但不能确认消费或伤势事实。
10. 未启用的 resource/tag/body definition 不以零值出现在 façade。

## Failure Semantics

| Error code | 条件 | Commit | 恢复 |
| --- | --- | --- | --- |
| `resource_not_registered` | 未注册 resource | none | 启用对应 patch/definition |
| `resource_insufficient` | available 小于成本 | none | 选择替代动作/恢复资源 |
| `resource_boundary_violation` | overflow policy 为 reject | none | 修正 delta |
| `reservation_conflict` | reservation revision 冲突 | none | 刷新重提 |
| `status_tag_conflict` | exclusivity 无唯一裁决 | none | 解决规则冲突 |
| `status_tag_source_invalid` | source 不存在或未授权 | none | 修复 effect proposal |
| `body_function_unavailable` | 动作需要的功能不可用 | none | 选择替代动作/治疗 |
| `body_transition_invalid` | posture/recovery 转移非法 | none | 满足前置条件 |
| `modifier_conflict_unresolved` | override/exclusive 冲突 | projection isolated | 修复 definition 后 rebuild |
| `numeric_resolution_error` | scale/overflow/NaN 等错误 | none or projection isolated | 修复输入/schema |

所有业务拒绝必须返回 blocked source refs；Godot 收到预测拒绝时按 prediction ID 回滚。

## Acceptance Criteria

1. 同一 registry 可注册 health、stamina 等资源，但角色只实例化适用集合。
2. 资源增加、消耗、预留、释放、耗尽和 overflow 各有成功/失败测试。
3. tag 的 unique、stack、refresh、exclusive、dispel、source-bound 与 timed expiration 可确定性重放。
4. scheduler 重复提交同一过期 command 不会重复移除或产生重复效果。
5. injury 改变 functional capacity，恢复后 capacity 可回升，永久技能 grant 不受影响。
6. baseline、加法、乘法、条件、override 与 clamp 的 canonical 顺序有 golden tests。
7. 调换 modifier 输入枚举顺序不改变 effective result 和 explanation digest。
8. 撤销装备/tag source 后所有关联 modifier 均失活，无残留加成。
9. Godot view 与 Mind Frame view 对隐藏身体事实执行不同且正确的裁剪。
10. 从空事件流 replay 得到与在线运行一致的 resource/tag/body/effective stats checksum。
11. 耐力不足或右臂功能不可用时，动作 settlement 零事件提交且返回结构化原因。

## Harness Mapping

### Current review gate

- `python scripts/verification/harness.py --profile docs`

### Required implementation profiles

- `gameplay-foundation-contract`
  - definition、command、event 与 projection schema。
- `gameplay-state-groups`
  - 按角色动态注册/物化资源、tag、body 组。
- `gameplay-event-replay`
  - timed expiry、injury recovery 和 modifier replay 确定性。
- `gameplay-possession-equipment`
  - 装备 grant/revoke 与 modifier 清理；
  - 负重输入对 stats/status 的影响。
- `adventure-basic`
  - 耐力不足；
  - 右臂受伤阻断剑术；
  - 恢复后无需重新学习即可执行。
- `godot-gameplay-mirror`
  - resource bar、visible tags、body presentation delta 与预测回滚。
- `gameplay-foundation-all`
