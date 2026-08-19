# Gameplay Patch Rule IR And Capabilities Design

Status: `minimum-governed-runtime-and-lifecycle-slice-implemented; broader-lifecycle-planned`

Date: `2026-07-23`

## 2026-08-02 Implementation Status

The first governed runtime slice is implemented and focused-test verified.
`GameplayPatchManifest` is immutable at the registry boundary and carries a
canonical content digest; only configured trusted authors can install it.
Candidate installation rejects digest tampering, missing or cyclic patch
dependencies, ambiguous dependency resolution, and incompatible event-schema
identities without mutating the candidate registry. Installation does not
activate behavior; a separate in-memory active patch-set selection is required.
Candidate manifests and the selected active-set identity can now be saved in a
versioned JSON snapshot with atomic replacement and restored only after their
trusted-author, digest, dependency, schema, and recomputed active-set revisions
all validate. Registered capability handlers remain process-owned code, so no
callable is serialized or restored from a patch snapshot.

The initial `GameplayRuleEvaluator` consumes only explicit frozen projection
inputs and returns typed `EffectProposal` values. It has no event-store,
settlement, Godot, network, filesystem, or service-locator parameter. Its
limited initial IR supports deterministic trigger matching, equality/existence
conditions, effect templates, declared capability calls, condition/proposal/
capability-call budgets, and canonical input/output digests. Capability
registration rejects non-deterministic or side-effectful/I/O handlers; a
handler must be requested by the manifest and its call site, and can return
only intersection-authorized effect types. Handler error, unauthorized effect,
or exceeded budget fails before any settlement path exists.

`GameplayPatchLifecycleAuthorityService` is the implemented minimal
control-plane authority slice. It validates the immutable candidate before it
appends `gameplay.patch.candidate_installed`; it then supports a complete
active-set `enable` or `disable` command only after the corresponding
authority-only Gameplay event batch commits. The in-memory registry changes
only after that append succeeds. Commands pin the expected registry and active
patch-set revisions, validate a canonical command digest and authority
principal, and use event-store idempotency. A stale revision, storage rejection
or unsupported disable fails before registry cutover.

A bounded stateful enable/disable closure is now implemented for a patch's declared
state groups. The caller supplies an explicit, trusted, unique actor-context
set. Enable contexts are pinned to the target active-patch-set revision;
disable contexts are pinned to the current source revision. Disable is allowed
only when every affected group is uniquely removed from the active set and its
existing lifecycle record has that current source revision.
The non-mutating state-group planner validates each actor and returns the
required lifecycle event specifications; the Patch authority binds all of those
events and the active-set lifecycle events into one `append_batch` before
registry cutover. Missing, duplicate, mismatched-target, ineligible, or
policy-expanded contexts reject before any state-group or Patch event is
written. Disable appends only the state-group `disabled` lifecycle event and
does not revoke historical facts or persistent domain effects. Actor discovery,
policy-catalog loading, shared ownership, grant/modifier compensation, and
data-transform stateful migration are intentionally outside this closure.

Rule-only same-patch revision cutover is also implemented. In addition, a
compatible stateful same-patch revision may atomically upgrade or rollback when
both manifests declare the same state-group set and the target declares an
`identity_rebind` for every group at its unchanged definition version. Every
explicit actor then appends `gameplay.state_group.rebound` with the Patch
lifecycle event and new active-set revision in one batch. This preserves state
and changes only its source revision.

The first bounded data-transform upgrade is now also implemented: a target
manifest may declare `resource_bounds_clamp` for the single `core.resources`
group. It pins old/new state-group and resource definition versions, named
input/output event schema identities, migration digest, trusted migrator code
digest and `forward_fix_only` rollback mode. The coordinator rebuilds the
pinned resource projection, then atomically appends the typed
`gameplay.resource.bounds_migrated` domain fact,
`gameplay.state_group.migrated`, Patch upgrade lifecycle event and active-set
cutover. The sole policy lowers a resource maximum with explicit loss and
rejects outstanding reservations. Historical registry lookup is by group ID
plus exact definition version. This slice is not generic migration: it has no
arbitrary payload operation, does not support multi-Patch replacement, and
explicitly rejects rollback because lost value cannot be recovered safely.

The implemented lifecycle projector deterministically rebuilds installed
candidates and the active patch set from committed control-plane events against
the trusted registry. It rejects a missing/tampered candidate, out-of-order
activation, or mismatched active-set revision; it never re-evaluates Rule IR.

This is not yet a complete Rule IR language, trusted capability handler-artifact
loading, general effect-proposal-to-domain settlement conversion, state-group
revocation beyond its direct lifecycle transition, grant/modifier lifecycle effects, data-transform stateful migration beyond the bounded resource clamp,
cross-version reader compatibility, replay artifact retention, privacy projection, or live Godot
delivery. The implemented settlement mapping is deliberately one
effect only: `resource.consume` is revalidated against the actor's current
resource projection and appended with `gameplay.patch.rule_settled` in one
authority batch. Inventory, ownership, equipment, economy and arbitrary effect
types remain outside this adapter and fail before any write.

## Purpose

定义可扩展玩法进入 Character Gameplay Foundation 的唯一受治理路径：版本化 `GameplayPatchManifest` 声明依赖、状态组、schema、规则、capability、迁移和验证；确定性、受预算的 Rule IR 读取固定 revision 的投影并只产生 typed effect proposal；复杂逻辑只能调用 manifest 明确授权、系统已经注册且受信任的 capability handler。

首批目标是支持仓库内部和明确受信任作者安全扩展玩法，而不是提供第三方任意脚本沙箱。任何 patch 都不能直接写 event store、projection、Godot node 或 world truth。

玩法包内容边界和 manifest 适配合同见：
`2026-08-17-package-content-and-cross-domain-binding-matrix-design.md` 与
`2026-08-17-package-contract-closure-and-manifest-adapter-design.md`。
这两份设计把 `PackageDefinition`、`PackageOutcomeDeclaration` 和
`BindingRequest` 视为 `GameplayPatchManifest` 内的不可变数据段，而不是
第二个可执行 package model、registry 或 runtime。

## Scope

本规格覆盖：

- gameplay patch package、manifest、definition namespace 与 registry revision；
- patch 依赖、冲突、替换、兼容性和 author trust policy；
- Rule IR trigger、typed condition、effect template、capability call 与预算；
- capability registry、handler 输入输出、权限和执行限制；
- typed effect proposal 到 authority settlement 的接口；
- install、enable、disable、upgrade、rollback、hot reload 和 replay 生命周期；
- 活跃事务的 revision pinning；
- schema、rule、modifier、grant 与 handler 冲突的显式解析；
- 失败隔离、审计 trace 和 planned harness evidence。

## Non-goals

本规格不提供：

- 任意第三方 Python、GDScript、JavaScript、WASM 或原生代码沙箱；
- patch 对 event append API、数据库连接、网络、文件系统、环境变量或 Godot scene tree 的直接访问；
- 通过加载顺序、文件名顺序或字典遍历顺序覆盖规则；
- 运行时原位修改已激活 definition 或 handler code；
- 由 Rule IR 自己决定 transaction commit；
- 允许模型生成未注册 effect type 或 capability 并直接执行；
- 删除或重写 patch 已产生的历史事件；
- 用 rollback 强行读取当前 reader 无法解释的历史事件；
- 第一阶段的公开 marketplace、签名分发基础设施或多租户不可信作者平台。

## Dependencies

本规格依赖：

- `2026-07-23-character-gameplay-foundation-master-design.md`
- `2026-07-23-foundation-invariants-and-domain-boundaries-design.md`
- `2026-07-23-state-group-registry-and-runtime-facade-design.md`
- `2026-07-23-event-sourcing-and-authority-settlement-design.md`
- `2026-07-23-resource-status-body-and-effective-stats-design.md`
- `2026-07-23-skill-ability-graph-and-affordance-design.md`
- `2026-07-23-persistence-replay-migration-and-hot-reload-design.md`
- `2026-07-23-verification-and-acceptance-matrix-design.md`

领域 patch 还依赖其 manifest 明确声明的 inventory、equipment、economy、ownership、relationship 或其他 state-group contracts。未声明依赖不能通过运行时偶然可见的 service locator 被使用。

## Trust And Authoring Boundary

首批只接受：

- repository-owned package；
- 经项目治理明确列入 trusted author registry 的 package；
- code digest、schema digest 和 capability set 可审计的 immutable revision。

`trusted` 不是“可绕过 settlement”。受信任 handler 仍必须遵守 schema、预算、capability scope、proposal-only 和审计规则。

不可信第三方内容只能使用未来另行设计的 sandbox 或纯数据子集。本规格不得被解释为允许把第三方脚本放入 backend 进程直接执行。

## 模型接口

```text
GameplayPatchPackage
  package_id
  package_version
  content_digest
  manifest
  schemas[]
  definitions[]
  rule_ir_documents[]
  capability_bindings[]
  upcasters[]
  projection_migrations[]
  verification_metadata
```

上面的逻辑模型只描述 manifest 的组成，不授权独立的 package install 或
active-revision 生命周期。可执行安装、启用、停用和 revision pinning 仍由
`GameplayPatchManifest` / `GameplayPatchRegistry` 既有控制面负责；
`GameplayPackageManifest` 仍是 reference/legacy 描述，除非另有明确批准的
只读 adapter，不得并行扩展。

已安装 revision 不可原位覆盖。任何内容 byte 或语义变化都必须产生新的 package version/content digest。

## GameplayPatchManifest

```text
GameplayPatchManifest
  manifest_schema_version
  patch_id
  patch_version
  patch_revision_id
  content_digest
  author_id
  trust_policy_ref
  engine_contract_range
  dependencies[]
  conflicts[]
  replaces[]
  state_groups[]
  command_schemas[]
  event_schemas[]
  projection_schemas[]
  definitions[]
  rules[]
  requested_capabilities[]
  granted_effect_types[]
  modifier_policies[]
  ability_grant_policies[]
  godot_bindings[]
  privacy_declarations[]
  migration_plan_refs[]
  replay_reader_refs[]
  disable_policy
  rollback_policy
  verification_profiles[]
```

### Dependency declaration

```text
PatchDependency
  patch_id | contract_id | state_group_id | capability_id
  version_range
  required: true | false
  reason
```

依赖必须构成可验证 DAG。循环依赖、缺失 required dependency、version range 无交集或隐式 service dependency 会拒绝 candidate。

### Conflict declaration

```text
PatchConflict
  target_ref
  conflict_kind: schema | definition | rule | modifier | grant | capability | ownership
  policy: reject | coexist | compose | replace
  resolver_id?
  precedence_key?
  compatibility_evidence_ref?
```

`replace` 只在 manifest 显式声明 `replaces`、被替代对象允许替换且 migration/replay compatibility 通过时成立。首批不允许对 core-owned schema 或 authority policy 做隐式 override。

## Registry And Revision Model

```text
GameplayPatchRegistryRevision
  registry_revision
  candidate_patch_revisions[]
  validated_definition_index
  capability_resolution
  conflict_resolution
  schema_digest
  created_at
```

```text
ActivePatchSetRevision
  active_patch_set_revision
  patch_revisions[]
  registry_revision
  world_config_revision
  policy_revision
  activation_event_id
  previous_revision?
```

candidate registry 和 active patch set 是不同对象。`install` 只建立 candidate；只有完整验证通过并经 authority activation 后才成为新事务可见的 active revision。

## Rule IR Model

### Rule definition

```text
RuleDefinition
  rule_id
  rule_version
  source_patch_revision
  trigger
  subject_selector
  typed_reads[]
  condition
  proposal_templates[]
  capability_calls[]
  conflict_group?
  conflict_policy
  evaluation_budget
  privacy_scope
  explanation_template
```

Rule IR 是声明式、无副作用、确定性的中间表示。解释器只接收 immutable evaluation context，输出 proposal、diagnostic 和 explanation trace。

### Trigger

首批 trigger 类型：

```text
command_precondition
command_effect
domain_event_observed
state_transition_candidate
scheduled_authority_tick
projection_query
```

`domain_event_observed` 规则不能修改已经提交的原事件。需要后续权威变化时，它只能提出新的 command/effect proposal，并由独立 settlement 产生新 transaction。

### Typed condition nodes

首批允许：

```text
all(children[])
any(children[])
not(child)
compare(left_ref, operator, typed_literal_or_ref)
exists(typed_ref)
contains(collection_ref, typed_value)
matches_tag(entity_ref, registered_tag_id)
revision_equals(aggregate_ref, revision)
graph_reachable(graph_ref, from_ref, to_ref, edge_kinds[], max_depth)
```

所有 ref 必须在 manifest 的 `typed_reads` 中声明，并绑定 schema/version。禁止：

- 任意源码字符串、`eval`、反射或动态 import；
- 无上限 loop、递归、图遍历或集合展开；
- 网络、文件、进程、环境变量和 wall clock 读取；
- 未排序 map/set 的遍历结果参与语义；
- 修改 evaluation context；
- 直接调用 event store 或 domain repository。

### Proposal templates

Rule IR 只能实例化已注册 effect schema：

```text
EffectProposal
  proposal_id
  effect_type
  effect_version
  target_aggregate_ref
  payload
  expected_revision
  precondition_refs[]
  reservation_refs[]
  source_rule_ref
  source_patch_revision
  causation_id
  correlation_id
  privacy_scope
  explanation_refs[]
```

proposal 不是事件，也不是 commit promise。settlement 必须再次验证 effect type、target ownership、permission、revision、resource reservation、cross-domain invariants 和 event mapping。

## Determinism Contract

同一 Rule IR revision、capability code digest、evaluation input、pinned revisions 和 authority tick 必须产生相同 canonical output digest。

确定性要求：

1. rule 按 `(conflict_group, precedence_key, rule_id, rule_version)` canonical 排序；
2. collection 输入在 schema 定义的 key 下排序；
3. decimal scale、rounding、timezone 和 string normalization 固定；
4. 时间读取只使用 context 注入的 authority tick/calendar revision；
5. 随机性默认禁止；确需随机的领域必须使用 manifest 声明的 deterministic RNG capability 和 transaction seed，并记录 seed ref；
6. capability handler version 与 code digest 固定到 patch revision；
7. unknown field、unknown effect 或 unknown condition node fail closed；
8. explanation trace 的非领域时间 metadata 不参与领域 digest。

## Evaluation Budget

```text
RuleEvaluationBudget
  max_rule_count
  max_condition_nodes
  max_condition_depth
  max_collection_items
  max_graph_nodes_visited
  max_effect_proposals
  max_capability_calls
  max_capability_output_bytes
  max_diagnostic_entries
  wall_timeout_ms
```

逻辑预算是确定性语义的一部分；wall timeout 是安全熔断，不能作为成功路径的业务分支。超过任一预算即整次 rule evaluation 失败，所有未提交 proposal 作废。不得截断 proposal 列表后继续 settlement。

world policy 可以收紧预算，patch 不能提高系统上限。预算值、实际消耗和停止位置必须进入 trace。

## Capability Registry

### Registered capability

```text
RegisteredCapability
  capability_id
  capability_version
  handler_code_digest
  owner
  trust_level
  input_schema_id/version
  output_schema_id/version
  allowed_callers[]
  allowed_read_scopes[]
  allowed_effect_types[]
  deterministic: true | false
  side_effect_free: true
  network_access: false
  filesystem_access: false
  execution_budget
  compatibility_range
```

首批 authority settlement 路径只允许 `deterministic=true` 且 `side_effect_free=true` 的 capability。非确定性或外部 I/O capability 必须进入未来独立的异步 orchestration 合同，不能混入原子结算。

### Manifest request

```text
RequestedCapability
  capability_id
  version_range
  call_sites[]
  input_binding_policy
  requested_effect_types[]
  reason
```

安装校验同时检查：

- capability 已注册且版本唯一匹配；
- patch author/trust policy 允许请求；
- 每个 call site 在 manifest 中声明；
- input/output schema 兼容；
- handler 允许的 effect type 是 patch grant 与 settlement policy 的交集；
- handler budget 不超过系统和 patch budget。

### Handler interface

```text
invoke_capability(
  capability_ref,
  validated_input,
  immutable_context,
  execution_budget,
) -> CapabilityResult

CapabilityResult
  status: proposed | no_op | rejected
  effect_proposals[]
  diagnostics[]
  explanation_refs[]
  budget_usage
  output_digest
```

handler 不接收数据库 session、event append port、mutable domain entity、Godot bridge 或通用 service locator。handler 抛异常、超时、越界、返回 schema-invalid payload 或未授权 effect 时，当前 settlement 在 commit 前失败且零权威写入。

## Rule Evaluation Interface

```text
EvaluateRulesRequest
  evaluation_id
  trigger
  command_or_event_ref
  subject_refs[]
  immutable_projection_inputs
  authority_tick
  transaction_seed_ref?
  pinned_registry_revision
  pinned_active_patch_set_revision
  pinned_world_config_revision
  pinned_policy_revision
```

```text
RuleEvaluationResult
  evaluation_id
  status: proposed | no_op | rejected
  matched_rule_refs[]
  rejected_rule_refs[]
  effect_proposals[]
  capability_invocations[]
  conflict_resolution_trace[]
  budget_usage
  input_digest
  output_digest
  explanation_refs[]
```

Rule runtime 无 commit API。`RuleEvaluationResult` 交回 authority settlement 后才可能转换为 domain events。

## Conflict Resolution

冲突在 candidate activation 前和 transaction evaluation 时分别处理。

### Static conflicts

- 相同 schema ID/version 不同 digest：拒绝；
- 相同 definition ID/version 不同语义：拒绝；
- 多个 patch 宣称同一 state group/domain ownership：拒绝；
- capability version 匹配不唯一：拒绝；
- modifier exclusive group 无 resolver：拒绝；
- `replace` 缺少显式 target/compatibility/migration：拒绝。

### Runtime proposal conflicts

```text
ProposalConflict
  conflict_key
  proposal_refs[]
  resolver_policy: reject | merge_commutative | choose_declared_precedence | domain_resolver
  resolver_version
```

只有 schema 声明可交换且结合的 effects 才允许 `merge_commutative`。`choose_declared_precedence` 使用 manifest 中稳定 precedence key；不得使用 patch 加载顺序。经济扣款、产权转移、item location、exclusive equipment slot 等默认进入 domain resolver 或拒绝，不能通用 last-write-wins。

## Commands And Lifecycle Events

### Control-plane commands

```text
InstallGameplayPatchCandidate
ValidateGameplayPatchCandidate
EnableGameplayPatch
DisableGameplayPatch
UpgradeGameplayPatch
RollbackGameplayPatch
RemoveGameplayPatchCandidate
```

这些 command 需要 authority/admin scope、idempotency key、expected registry/patch-set revision 和审计 source。

### Lifecycle records/events

```text
GameplayPatchCandidateInstalled
GameplayPatchCandidateValidated
GameplayPatchCandidateRejected
ActivePatchSetRevisionActivated
GameplayPatchEnabled
GameplayPatchDisableStarted
GameplayPatchDisabled
GameplayPatchUpgradeActivated
GameplayPatchRollbackActivated
GameplayPatchActivationFailed
```

candidate 校验记录属于 registry/control-plane audit。影响 gameplay state group、grant、modifier 或 policy 的 enable/disable/upgrade/rollback 必须通过 authority settlement 追加相应 gameplay events，不能只切一个进程内 boolean。

## Patch Lifecycle

### Install

```text
package intake
-> verify content digest and trusted-author policy
-> parse manifest and schemas
-> validate dependencies and conflicts
-> validate Rule IR and budgets
-> resolve requested capabilities
-> validate event readers/upcasters/migrations
-> register immutable candidate revision
```

install 不影响 active transactions，也不让规则参与新 command。

### Enable

```text
validated candidate
-> shadow registry composition
-> implementation/harness gate
-> prepare state-group materialization and grants
-> authority settlement for enable effects
-> atomically activate new ActivePatchSetRevision
-> only new transactions observe it
```

如果 state materialization、grant activation 或 registry cutover 任一步失败，active revision 保持不变；不能出现规则已启用但状态组未物化的半状态。

### Disable

disable 必须声明每个资源的策略：

```text
state groups: dormant | read_only | archive | reject_disable_when_nonempty
active grants/modifiers: revoke | expire | preserve_read_only
definitions: unavailable_for_new_commands, retained_for_replay
events/readers/upcasters: retained
Godot bindings: remove_after_authoritative_delta
```

流程：

```text
pin current active revision
-> validate disable policy and nonempty constraints
-> propose grant/modifier revocation or compensation
-> commit one atomic event batch
-> activate new patch-set revision without the patch
-> emit projection/Godot deltas
```

disable 不删除历史事件、已学习能力、item、产权或合法持久事实。由 patch 定义但仍存在的历史实体必须有 dormant/legacy reader 策略。

### Upgrade

```text
install new candidate revision
-> dependency/schema/capability validation
-> upcaster and migration validation
-> shadow full replay
-> before/after fixture comparison
-> prepare atomic cutover
-> activate new ActivePatchSetRevision
```

每个 settlement 开始时固定：

```text
registry_revision
active_patch_set_revision
world_config_revision
policy_revision
capability handler code digests
```

upgrade 期间已开始事务继续使用旧 revision 和旧 handler，新事务使用新 revision。禁止在同一事务中热替换 rule、handler、modifier 或 schema。

### Rollback

rollback 创建新的 active patch-set revision，重新选择一个兼容的旧规则 revision，并按需要追加 forward compensation/reconfiguration events。它不删除 upgrade 后事件。

若旧 reader 无法解释 upgrade 后历史事件，返回 `patch_rollback_incompatible`；必须使用 forward fix 或兼容 reader，不能跳过历史事件强行降级。

### Replay

event replay 重放已提交 events，而不是重新运行历史 Rule IR 决定过去发生了什么。历史 event 必须保留 `source_patch_revision`、schema identity 和 causation refs。

需要验证规则确定性时使用独立 command/evaluation fixture：以记录的 pinned inputs、Rule IR revision 和 capability digest 重新求值，对比 canonical output digest。projection replay 与 rule re-evaluation 是两类证据，不能混为一谈。

## Data And Command Event Flow

### Normal settlement

```text
structured command
-> schema/identity/permission/idempotency validation
-> pin registry/patch/world/policy revisions
-> select canonical rules for trigger
-> evaluate typed conditions under budget
-> invoke only manifest-authorized trusted capabilities
-> collect typed effect proposals
-> resolve explicit conflicts
-> domain preconditions and reservations
-> map accepted proposals to domain events
-> atomically append event batch
-> projections/outbox/Godot mirror
```

### Post-event reaction

```text
committed domain event
-> outbox delivery to event-observed rules
-> rule evaluation produces new proposals
-> new command/settlement with new transaction_id
-> new event batch
```

event-observed reaction 必须有深度/causation budget 和重复检测，避免规则互相触发形成无限链。

## Authority Invariants

1. patch、Rule IR 和 capability handler 只能产生 typed effect proposal，不能直接写任何权威 store。
2. authority settlement 是 proposal 变成 domain event 的唯一入口。
3. Rule IR 对固定输入、definitions 和 revisions 必须确定性输出。
4. 每次 evaluation 都受节点、深度、集合、图遍历、proposal、capability、输出和时间预算约束。
5. 复杂逻辑只能调用 manifest 声明、registry 唯一解析、系统授权的受信任 handler。
6. 首批不执行任意第三方脚本；trusted author 也不能绕过 capability 和 settlement 边界。
7. 已激活 patch revision immutable；任何变化发布新 revision。
8. 活跃事务始终使用开始时 pinned revisions 和 handler digests。
9. install/enable/disable/upgrade/rollback 不重写或删除历史事件。
10. patch 冲突必须显式拒绝或由版本化 resolver 解决，不能靠加载顺序、last-write-wins 或 map 顺序。
11. handler 失败发生在 commit 前时，transaction 零提交；commit 后 projection/outbox 失败不得伪装成未提交。
12. privacy scope 从 typed read、handler input、proposal、event 到 projection 全链路保留。
13. replay 使用历史 event reader/upcaster；规则重新求值只作为确定性验证，不改写历史。
14. patch disable 不得误删不属于该 patch 的 learned ability、ownership、item 或其他来源 grant。

## Failure Semantics

| Error code | Stage | Authority effect | Recovery |
| --- | --- | --- | --- |
| `patch_author_untrusted` | install | candidate not installed | 使用受信任 author/review 流程 |
| `patch_digest_mismatch` | install | candidate rejected | 重新打包 immutable revision |
| `patch_manifest_invalid` | parse/schema | candidate rejected | 修复 manifest/schema |
| `patch_dependency_missing` | dependency | candidate disabled | 安装兼容依赖 |
| `patch_dependency_cycle` | dependency | candidate rejected | 打破依赖环 |
| `patch_conflict_unresolved` | composition | active revision retained | 声明显式 conflict/resolver |
| `patch_schema_collision` | registry | active revision retained | 更换 ID/version 或合法 replace |
| `rule_ir_node_unknown` | validation | candidate rejected | 使用已注册 typed node |
| `rule_ir_type_mismatch` | validation/evaluation | no proposals committed | 修复 typed refs/schema |
| `rule_budget_exceeded` | evaluation | settlement rejected, zero events | 降低复杂度或在政策内调整预算 |
| `rule_reaction_depth_exceeded` | post-event reaction | new reaction rejected | 修复循环触发规则 |
| `effect_type_unauthorized` | proposal validation | settlement rejected, zero events | 在 manifest/policy 中合法声明 |
| `effect_proposal_schema_invalid` | proposal validation | settlement rejected, zero events | 修复 template/handler output |
| `capability_not_registered` | install/evaluation | candidate rejected or transaction rejected | 注册兼容 capability |
| `capability_not_manifest_authorized` | evaluation | settlement rejected, zero events | 声明并通过授权 |
| `capability_version_ambiguous` | resolution | candidate rejected | 收紧唯一 version range |
| `capability_timeout` | handler | settlement rejected, zero events | 优化 handler/预算后重试 |
| `capability_handler_failed` | handler | settlement rejected, zero events | 修复并发布新 immutable revision |
| `capability_output_invalid` | handler output | settlement rejected, zero events | 修复 schema/handler |
| `patch_enable_settlement_failed` | enable | old active revision retained | 修复 state/grant preconditions |
| `patch_disable_blocked_nonempty` | disable | patch remains active | 迁移/清空或选择允许策略 |
| `patch_upgrade_verification_failed` | upgrade | old active revision retained | 修复 candidate 并重新 shadow 验证 |
| `patch_revision_changed` | transaction start/retry | none | 使用 pinned revision 完成或刷新重试 |
| `patch_rollback_incompatible` | rollback | current active revision retained | forward fix/兼容 reader |
| `patch_replay_definition_missing` | replay readiness | write readiness blocked | 恢复历史 reader/definition artifact |

失败结果使用 foundation failure envelope，并补充 `patch_id/revision`、`rule_ref`、`capability_ref`、budget usage、failed node/path 与 recovery action。敏感 handler input 按 privacy scope 脱敏。

## Acceptance Criteria

1. manifest 缺少 required dependency、存在循环、schema collision 或 ownership 冲突时不能激活。
2. 相同 Rule IR、输入、authority tick、patch revision 和 handler digest 重复执行得到相同 proposal 与 explanation digest。
3. Rule IR 无 event append、repository、network、filesystem、wall clock 或 Godot 写入口。
4. 超过 condition depth、graph visit、proposal count、capability count 或 output bytes 任一预算时整次 evaluation 失败且零事件提交。
5. 未在 manifest 声明或未在系统 registry 注册的 capability 无法调用。
6. handler 超时、抛异常、返回未知 effect 或 schema-invalid output 时 settlement 零提交。
7. 所有 handler 只返回 typed proposal；settlement 对 target ownership、revision、permission 和 reservation 再校验。
8. 两个 patch 的规则、modifier、grant 或 schema 冲突不会因加载顺序得到不同结果；未显式解析则 activation 被拒绝。
9. `install` 不改变 active behavior，`enable` 只有完整 materialization/cutover 成功后才影响新事务。
10. disable 后不再产生该 patch 的新业务事件，相关 grant/modifier 按策略撤销，但历史事件和无关 learned state 保留。
11. upgrade 时旧活跃事务完成于旧 revision，新事务使用新 revision，单个 transaction 不混用 handler digest。
12. rollback 创建新 patch-set revision且不删除 upgrade 后事件；不兼容 rollback 明确拒绝。
13. 删除 checkpoint 后仍可用历史 event schema/upcaster 完整 replay；无需重新执行 Rule IR 才能恢复过去事实。
14. recorded evaluation fixture 可重新求值并验证 Rule IR/capability deterministic digest。
15. privacy-restricted input 不出现在未授权 trace、Godot delta 或公开错误详情。
16. `adventure-basic` 能通过 manifest 注册 sword skill/action、purchase/equip rule、storage-ring policy 与必要 capability，并通过 enable/disable/upgrade fixture。
17. 不存在把任意第三方脚本作为首批 patch handler 直接加载进 backend 的实现路径。

## Harness Mapping

### Implemented evidence

- `python scripts/verification/harness.py --profile gameplay-patch-runtime`
  - immutable candidate and active-set validation;
  - deterministic proposal-only Rule IR and capability gates;
  - authority-ledger candidate install and the limited complete-active-set
    enable/disable cutover;
  - the constrained `resource.consume` proposal-to-event settlement mapping.

This evidence does not prove the broader lifecycle requirements below.

### Required implementation profiles

- `gameplay-foundation-contract`
  - manifest、Rule IR、effect proposal、capability、lifecycle 与 error schemas。
- `gameplay-event-replay`
  - source patch revision、historical readers、disable/upgrade/rollback event replay。
- `gameplay-state-groups`
  - patch-driven registration、materialization、dormant/read-only lifecycle。
- `gameplay-patch-runtime`
  - dependency/conflict validation；
  - deterministic Rule IR；
  - all budget fault injections；
  - capability authorization、timeout、exception、invalid output；
  - expand the implemented install/enable/disable slice to patch-owned
    materialization/revocation, upgrade/rollback, and durable recovery；
  - active transaction revision pinning；
  - loading-order permutation tests。
- `gameplay-possession-equipment`
  - patch grant/modifier disable compensation 和 storage-ring policy。
- `gameplay-economy-authority`
  - typed purchase/transfer proposals 与 atomic settlement。
- `godot-gameplay-mirror`
  - patch revision metadata、binding enable/disable delta 和 resync。
- `adventure-basic`
  - reference manifest 从空 registry 安装、启用、运行、升级、禁用和 replay。
- aggregate: `gameplay-foundation-all`

Harness 证据必须记录 package/content digest、registry/patch-set revisions、handler code digests、input/output digests、budget usage、conflict resolution、event batch、failure injection 和 replay result，并存入 `.harness/verification/`。
