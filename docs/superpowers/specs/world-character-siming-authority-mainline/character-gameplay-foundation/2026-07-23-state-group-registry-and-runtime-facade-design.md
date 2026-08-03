# State Group Registry And Character Game Runtime Façade Design

Status: `minimum-core-implemented; lifecycle-and-consumer-views-planned`

Date: `2026-07-23`

## Purpose

定义角色游戏状态组如何被注册、验证、动态装配、物化、禁用和投影，以及 `CharacterGameRuntimeState` 如何把独立领域读模型组合成稳定、带版本、可裁剪的 façade。

目标不是建立一个永久增长的 `CharacterDynamicState` 或巨型角色对象，而是让角色只拥有当前世界、archetype 与玩法包真正适用的状态组，并为 Mind Frame、Godot、调试与 authority settlement 提供一致读取面。

## 2026-08-01 Implementation Status

`backend/app/gameplay/runtime_state.py` now implements the lowest-risk
read-composition core: immutable version-addressable definitions, deterministic dependency and
conflict validation, immutable snapshot envelopes/checksums, and an
event-derived lifecycle read projection for materialized/enabled/dormant/
disabled groups. A trusted backend-only service can validate an explicit
assembly context and append materialize/enable/dormant/disable events through
the existing atomic Gameplay batch writer; the facade composes only enabled
groups. A versioned declarative catalog can compile actor archetype, world
revision, and patch revision inputs into that trusted context without reading
Godot or cognition state. It does not yet persist/load policy from world or
patch activation, rebuild projections across process lifetime, provide
privacy-policy persistence/loading, view transport/consumer capability
negotiation, client prediction, or Godot transport. A backend-only sync service
can create checksummed full snapshots and exact-base deltas, but it owns no
transport or consumer resnapshot workflow. The current immutable view projector
can only delete existing top-level payload fields for non-authority consumers,
requires debug-principal allowlisting, and fails closed for an allowed group
lacking a policy. `Phase3StateComposer` can now compose already-owned resource,
body, status-tag, and effective-stat read projections into enabled facade
groups only; it has no event-store or command dependency. `Phase3CheckpointReplay`
can rebuild its lifecycle/resource/body/tag checkpoint plus tail to the same
read-only façade checksum as a full rebuild. It is in-memory only and does not
claim checkpoint persistence, migration, or delivery. The complete design below
remains normative for those unimplemented stages.
`project_godot_runtime_state` now serializes only an already policy-filtered
Godot view into a `gameplay_runtime_state.godot.v1` envelope. The local consumer
and bus plumbing reject authority/private/physics fields, but no backend route
or live Godot delivery proof exists yet. Any future route must authorize the
actor/session scope, use an after-commit source, and resnapshot on exact-base
delta or checksum failure; it may not expose the authority façade.

When more than one definition is registered for a group, an assembly caller
must pin its selected version; history replay resolves the exact version carried
by each lifecycle event. The first Patch resource migration also records a
separate `gameplay.state_group.migrated` lifecycle transition only after its
typed resource-domain fact is planned for the same authority batch. That
metadata transition is not a generic group-payload write API.

## Scope

本规格覆盖：

- `StateGroupDefinition` 与 `StateGroupRegistry`；
- 状态组依赖、冲突、适用条件与生命周期；
- 世界配置、角色 archetype、patch revision 与权限共同决定的动态装配；
- 状态组 enable/disable request 的后端权威处理；
- `CharacterGameRuntimeState` façade、revision vector、snapshot 和 delta；
- 面向 Godot、Mind Frame 与 authority 的不同投影视图；
- disable、dormant、rematerialize 与 rebuild 语义。

## Non-goals

- 不定义每个具体状态组的领域字段；
- 不允许 façade 成为写模型或统一 aggregate root；
- 不定义 Gameplay Patch Rule IR；
- 不定义物品、产权、关系或 Siming 图内部 schema；
- 不允许 Godot 自主启用权威状态组；
- 不在首批支持任意第三方状态组代码。

## Dependencies

- `2026-07-23-foundation-invariants-and-domain-boundaries-design.md`
- `2026-07-23-event-sourcing-and-authority-settlement-design.md`
- `2026-07-23-persistence-replay-migration-and-hot-reload-design.md`
- `2026-07-23-resource-status-body-and-effective-stats-design.md`
- gameplay patch、Godot mirror 与 privacy 子规格（同一 spec tree）

## Terminology

- **registered**：定义已通过 registry 校验，但不代表任何角色拥有实例。
- **eligible**：世界、archetype、patch、feature policy 与权限允许该角色装配。
- **enabled**：后端配置已确认该状态组参与 command、projection 与同步。
- **materialized**：状态组事件流或初始事件已建立，可构建 projection。
- **dormant**：停止接受新业务 command，但历史事件与只读投影按策略保留。
- **disabled**：不出现在普通 façade；是否保留 dormant projection 由 definition 声明。
- **view**：同一权威投影经 privacy、salience 和 consumer policy 裁剪后的读取面。

## StateGroupDefinition Model

```text
StateGroupDefinition
  group_id: stable namespaced id
  definition_version: semver
  projection_schema_id
  projection_schema_version
  command_types[]
  event_types[]
  owner_domain
  aggregate_strategy
  dependencies[]: StateGroupDependency
  conflicts[]: StateGroupConflict
  eligibility_policy_ref
  initialization_policy_ref
  disable_policy: reject_if_nonempty | dormant | archive_projection
  persistence_policy: event_sourced
  sync_policy: none | snapshot | snapshot_and_delta
  prediction_policy: forbidden | presentation_only | reversible_local
  privacy_policy_ref
  mind_frame_projection_ref?
  godot_projection_ref?
  rebuild_projection_ref
  source_patch_id
  source_patch_revision
```

`group_id` 必须使用命名空间，例如 `core.resource`、`core.status_tags`、`adventure.body_runtime`。同一个 `group_id + definition_version` 的内容必须不可变；修改定义需要新版本。

### Dependency model

```text
StateGroupDependency
  required_group_id
  version_range
  mode: hard | projection_only

StateGroupConflict
  other_group_id
  reason_code
  resolution: reject_enable
```

首批不允许“按加载顺序覆盖”。硬依赖形成有向无环图；循环依赖使 patch/config revision 无法激活。

## Registry Interfaces

```text
register_definition(definition) -> RegistrationResult
validate_registry(candidate_revision) -> RegistryValidationReport
resolve_definition(group_id, version) -> StateGroupDefinition
resolve_load_order(enabled_groups) -> ordered group ids
list_eligible_groups(actor_ref, world_revision, patch_revision) -> EligibilityProjection
explain_eligibility(actor_ref, group_id) -> EligibilityExplanation
```

注册过程只改变候选 registry revision。只有完整 schema、依赖、冲突、capability、migration 和 verification metadata 均通过后，candidate revision 才能被原子激活。

## Dynamic Assembly

装配输入是：

```text
StateAssemblyContext
  actor_ref
  actor_archetype_ref
  world_config_revision
  active_patch_set_revision
  feature_policy_revision
  authority_principal
  requested_group_ids[]?
```

解析顺序固定：

1. 从 world config 得到允许的 group set；
2. 应用 actor archetype 的 required/allowed/forbidden 条件；
3. 解析 active patch definitions 与版本；
4. 展开 hard dependencies；
5. 检查 conflicts、privacy 与 authority policy；
6. 生成 `StateAssemblyPlan`；
7. 通过 authority settlement 原子提交 materialization/enable events；
8. rebuild 受影响投影并发布新的 façade revision。

```text
StateAssemblyPlan
  plan_id
  actor_ref
  registry_revision
  config_revision
  groups_to_materialize[]
  groups_to_enable[]
  groups_to_disable[]
  retained_dormant_groups[]
  dependency_order[]
  required_migrations[]
  expected_revisions
  explanation
```

普通人没有修炼组不是“空字段”，而是该组不在 `enabled_state_groups`。非战斗场景可以禁用战斗组，但不能删除其历史事件。

## State Group Commands And Events

```text
RequestStateGroupEnable
RequestStateGroupDisable
MaterializeStateGroup
EnableStateGroup
DisableStateGroup
RebuildStateGroupProjection
RebindStateGroupSource
```

Godot、debug tooling 或玩法系统只能发送前两个 request。后四个命令由 backend authority 在校验装配计划后发起。

核心生命周期事件：

```text
StateGroupMaterialized
StateGroupEnabled
StateGroupDisabled
StateGroupEnteredDormancy
StateGroupProjectionRebuilt
StateAssemblyRevisionAdvanced
StateGroupSourceRebound
```

`StateGroupMaterialized` 必须记录 initialization policy、source patch revision 与初始事件引用；不能直接插入一份无来源 snapshot。

`StateGroupSourceRebound` 是受限的 stateful Patch identity migration event。
它记录 `actor_ref`、`group_id`、`definition_version`、前后
`source_patch_revision`、`migration_kind=identity_rebind` 和 manifest-pinned
`migration_digest`。它只能在 group 已 materialized 且未 disabled、definition
version 不变、previous source 与当前 record 一致时保持现有 lifecycle state 并
转移 source revision。它不改写历史 event、不变换 projection payload、不撤销
grant/modifier。任何数据变换、definition version 变化或持续效果处理必须通过
独立 migration/revoke/compensation command，不得伪装为 rebind。

## CharacterGameRuntimeState Façade

```text
CharacterGameRuntimeState
  actor_ref
  facade_schema_version
  facade_revision
  source_revision_vector
  registry_revision
  world_config_revision
  active_patch_set_revision
  generated_at
  enabled_state_groups[]: StateGroupDescriptor
  groups: map<group_id, StateGroupProjectionEnvelope>
```

```text
StateGroupDescriptor
  group_id
  definition_version
  projection_schema_version
  lifecycle_state
  visibility_state: visible | redacted | unavailable
  sync_policy
  prediction_policy
  source_patch_revision

StateGroupProjectionEnvelope
  group_id
  projection_revision
  source_revision_vector
  payload
  explanation_ref?
```

`groups` 只包含当前 view 可见且已启用的状态组。被隐去的组可在 descriptor 中标记为 `redacted`，但当“该组存在”本身也敏感时必须完全省略。

### Recommended first composition

首批 façade 可组合但不强制全有：

```text
identity
mental
resources
status_tags
body_runtime
inventory
ownership
equipment
skills
ability_affordances
relationships
effective_stats
```

这些是 view aliases，不是 façade 可直接修改的字段。每项都来自独立 projection provider。

## Façade Read Interfaces

```text
get_authority_view(actor_ref, selector, expected_min_revision?)
get_godot_view(actor_ref, client_capabilities, since_revision?)
get_mind_frame_view(actor_ref, cognition_context)
get_debug_view(actor_ref, principal, include_explanations)
```

- authority view 可读取 settlement 所需的完整、授权投影；
- Godot view 只包含显示、局部计算和允许预测所需字段；
- Mind Frame view 按角色实际感知、自知和可用记忆过滤，不因 backend 知道而自动暴露；
- debug view 仍受 privacy scope，不存在无条件“显示全部”。

## Snapshot And Delta Contract

完整 snapshot：

```text
CharacterGameRuntimeSnapshot
  actor_ref
  facade_revision
  source_revision_vector
  schema_capabilities
  enabled_state_groups
  groups
  snapshot_checksum
```

增量：

```text
CharacterGameRuntimeDelta
  actor_ref
  base_facade_revision
  target_facade_revision
  target_source_revision_vector
  target_schema_capabilities
  target_enabled_state_groups
  changed_group_envelopes[]
  removed_group_ids[]
  confirmed_prediction_ids[]
  rejected_predictions[]
  target_snapshot_checksum
```

当前实现的后端只读同步切片生成稳定的完整 snapshot，并只接受 checksum 完整且
`base_facade_revision` 精确匹配的 delta。delta 携带 target 的 revision vector、
capability、enabled-group set 与 checksum，因此应用端可以重建后验证完整 target；
变更组与移除组不得重叠。该切片没有 transport、WebSocket/Godot mirror、客户端
prediction 或 resnapshot 请求实现。未来 consumer 遇到乱序、缺口、未知 schema 或
checksum 错误时必须请求完整 snapshot，不能尽力拼接。

## Disable And Rematerialization

- `reject_if_nonempty`：存在领域定义的 unresolved obligations 时拒绝禁用；例如装备容器非空。
- `dormant`：停止新业务 command，保留只读 projection 和历史恢复能力。
- `archive_projection`：普通 façade 不再提供 projection，但事件仍可重建。
- 再启用时必须根据现行 definition/version 执行 replay/upcast，不得把旧 snapshot 当作新真相。
- disable 不撤销历史影响。需要撤销持续效果时，settlement 必须先追加明确的 revoke/compensation event。

## Authority Invariants

1. 只有 backend authority 能改变 enabled/materialized lifecycle state。
2. registry definition 不持有角色状态，façade 不持有写权限。
3. 装配结果固定到 registry、world config 和 patch set revision。
4. 相同输入 revision 必须产生相同 assembly plan 与 dependency order。
5. enable/disable 与必要的 grant/revoke 必须在一个原子事件批次中提交。
6. 未启用组的 command 必须被拒绝，不能隐式创建默认状态。
7. façade 的每个 group projection 都能指出来源 revision vector。
8. consumer-specific view 只能删除或降精度，不能创造新权威字段。
9. Godot 本地开关只影响本地 UI/表现；权威 group 开关必须等待 backend confirmation。
10. façade 内 `mental` 仅投影既有 mind runtime，不吞并其 store 或 lifecycle。

## Failure Semantics

| Error code | 条件 | 是否重试 | 恢复动作 |
| --- | --- | --- | --- |
| `state_group_definition_invalid` | schema/metadata 不完整 | 否 | 修复 definition 并发布新 candidate revision |
| `state_group_dependency_missing` | hard dependency 不存在 | 否 | 安装/启用依赖 |
| `state_group_dependency_cycle` | 依赖成环 | 否 | 修改定义，registry 不激活 |
| `state_group_conflict` | 冲突组同时启用 | 否 | 选择兼容配置 |
| `state_group_not_eligible` | archetype/world/policy 不允许 | 否 | 查看 eligibility explanation |
| `state_group_not_enabled` | 对 disabled 组发业务命令 | 条件性 | 请求启用后重试 |
| `state_group_disable_blocked` | unresolved obligation | 条件性 | 先完成转移/撤销命令 |
| `facade_revision_conflict` | delta base 不匹配 | 是 | 请求完整 snapshot |
| `projection_schema_unsupported` | consumer 不支持版本 | 条件性 | capability negotiation 或升级客户端 |
| `privacy_projection_failed` | 无法安全裁剪 | 否 | fail closed 并修复 projection |

任何失败都不得让 registry/config revision 与 actor lifecycle event stream 发生半更新。

## Acceptance Criteria

1. 两个不同 archetype 在同一世界可得到不同的 enabled group set。
2. 未注册、依赖缺失、循环依赖与冲突状态组均在激活前被拒绝。
3. Godot enable request 在 backend 确认前不改变权威 façade。
4. enable、必要物化和初始化事件原子提交；失败时无状态组半启用。
5. disable policy 的三种路径都有成功与失败测试，历史事件始终保留。
6. authority、Godot、Mind Frame 和 debug view 对同一 actor 产生正确的不同裁剪结果。
7. façade 能精确说明每个 group 的 definition、projection 与 source revision。
8. delta 缺口、乱序与不支持 schema 均触发 resnapshot，不产生静默状态分叉。
9. 删除 checkpoint 后完整 replay 能恢复相同 enabled group set 和 façade checksum。
10. implementation API 不暴露 `facade.update(...)` 或等价的直接写路径。

## Harness Mapping

### Current review gate

- `python scripts/verification/harness.py --profile docs`

### Required implementation profiles

- `gameplay-foundation-contract`
  - registry definition schema；
  - command/snapshot/delta envelope；
  - consumer capability negotiation。
- `gameplay-state-groups`
  - 当前验证不可变 definitions、依赖/冲突拒绝、确定性加载顺序、lifecycle event
    read projection、explicit-context authority batch、最小只读 façade 与
    policy-filtered consumer views；
  - 当前也证明后端只读完整 snapshot、exact-base delta、capability 拒绝、移除组
    重建和 target checksum 验证；
  - 后续扩展到 archetype/world/patch 动态装配、persistent rebuild、consumer
    view transport/capability negotiation、prediction 与 Godot mirror。
- `gameplay-event-replay`
  - materialization event replay；
  - checkpoint 与完整重放等价。
- `godot-gameplay-mirror`
  - request/confirm；
  - delta 缺口 resnapshot；
  - prediction confirm/reject。
- `gameplay-foundation-all`

`gameplay-state-groups` 已注册并仅证明上述 read-only 核心。其余验收项仍须在实现后扩展该 profile，不能由当前绿报告推断完成。
