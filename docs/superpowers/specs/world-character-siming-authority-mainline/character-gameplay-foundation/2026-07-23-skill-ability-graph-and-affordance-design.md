# Skill, Ability Graph, And Affordance Design

Status: `minimum-core-implemented; broader-graph-planned`

Date: `2026-07-23`

## 2026-08-02 Implementation Status

The initial backend-only core is implemented and profile-verified. It has a
small versioned definition registry, event-derived learned-skill and grant
projection, and a read-only affordance resolver that combines stable skill
state with current resource/body projections. It proves that injury blocks an
action without deleting learned skill truth. It does not implement promotion,
restrictions command APIs, equipment/inventory/environment/permission
predicates, persistence, transport, or Godot mirror delivery.

## Purpose

定义 Character Gameplay Foundation 的技能、动作、能力授予、学习证据与即时可用性模型，使系统能同时回答两个不同问题：

1. 角色长期学会了什么、被什么来源授予了什么；
2. 在当前身体、资源、装备、环境、权限与目标条件下，角色此刻能够尝试什么。

本规格把稳定能力图与即时 `AbilityAffordanceProjection` 明确分离。技能服务、character mind、VLA 或其他规划器可以提供路径排序和风险建议，但最终能否执行、是否扣费以及产生哪些事件，只能由 backend authority settlement 决定。

## Scope

本规格覆盖：

- skill、action、skill path、prerequisite 与 grant 的版本化定义；
- 角色已学习能力、外部授予能力与限制的事件溯源投影；
- 学习、训练、使用结果和师承等成长证据；
- dossier capability seed 到权威技能状态的受控物化；
- 装备、buff、契约或 authority grant 的可撤销生命周期；
- 当前 affordance 的查询、阻断原因、预计成本和解释链；
- skill evaluation advisory 到 authority settlement 的边界；
- 与 body、resources、equipment、inventory、relationships、world authority、character mind 和 Godot mirror 的接口；
- 首批 `adventure-basic` 剑术场景需要的实现合同。

## Non-goals

本规格不定义：

- 大型生产技能库、完整战斗招式库或完整修炼体系；
- 由模型自行创造并持久化未知技能或 action definition；
- 将能力图、关系图和 Siming 图谱合并为通用图数据库；
- 让 skill evaluator、L3/L4、VLA、Godot 或 Rule IR 直接写权威状态；
- 把一次成功使用自动等同为永久学习或自动升阶；
- 把临时装备/buff grant 转换成永久学习；
- 在 affordance 查询阶段实际扣除资源、改变 cooldown 或追加领域事件；
- 以客户端本地时间、未固定随机数或网络查询决定权威技能结果。

## Dependencies

本规格依赖：

- `2026-07-23-character-gameplay-foundation-master-design.md`
- `2026-07-23-foundation-invariants-and-domain-boundaries-design.md`
- `2026-07-23-state-group-registry-and-runtime-facade-design.md`
- `2026-07-23-event-sourcing-and-authority-settlement-design.md`
- `2026-07-23-resource-status-body-and-effective-stats-design.md`
- `2026-07-23-inventory-container-and-encumbrance-design.md`
- `2026-07-23-equipment-runtime-design.md`
- `2026-07-23-ownership-economy-and-transaction-design.md`
- `2026-07-23-gameplay-patch-rule-ir-and-capabilities-design.md`

兼容既有 `backend/app/character_agent/skills/` 中的 `SkillDefinition`、`ActionDefinition`、`SkillActionBinding`、`CharacterSkillState`、`SkillEvaluationResult` 和 `SkillEvidence` 语义。现有服务是 advisory 基础，不是本规格所定义的持久权威技能领域；迁移时应适配或扩展现有模型，而不是并行建立第二套同名运行时。

## Core Separation

### Stable ability graph

稳定能力图表达角色相对长期、可审计的能力结构：

- 已物化的 authored baseline；
- 通过学习/晋升事件获得的永久或长期 mastery；
- 当前仍有效的装备、buff、契约、剧情或 authority grant；
- skill 到 action 的路径与显式 prerequisite；
- grant、restriction、learning evidence 和 definition revision 的来源。

“稳定”表示它不会因一次耐力不足、右臂受伤、目标离开范围或当前沉默状态而丢失节点。它仍可因 `AbilityLearned`、`AbilityGrantActivated`、`AbilityGrantRevoked`、`SkillRankPromoted` 等权威事件而改变。

### Momentary affordance

即时 affordance 是可重建读模型，组合：

```text
stable ability graph
+ body functions and injuries
+ resources and reservations
+ status tags and cooldown state
+ active equipment and accessible tools
+ inventory/container accessibility
+ effective stats and modifiers
+ target/environment facts
+ relationship/legal permissions
+ world and authority policy
+ pinned registry/patch revisions
-> current action path availability
```

affordance 不改变稳定能力图。角色可以“已掌握剑术”同时“当前不能挥剑”。阻断解除后，能力无需重新学习即可恢复可用。

## State Group Registration

首批注册两个不同状态组：

```text
skills
  authority_owner: actor_gameplay.skill_domain
  persistence: event_sourced
  prediction: forbidden
  default_privacy: actor_private | authority

ability_affordances
  authority_owner: derived_projection
  persistence: rebuildable_projection
  prediction: read_hint_only
  default_privacy: consumer_filtered
```

`skills` 保存权威事件投影；`ability_affordances` 只保存派生结果和依赖 revision vector。consumer 不得把 affordance 中的 `available=true` 持久化为技能事实。

## 模型接口

### Skill definition

```text
SkillDefinition
  skill_id
  definition_version
  display_key
  domains[]
  rank_scale_id
  learnability: natural | trained | granted | locked
  visibility_policy
  risk_tags[]
  source_patch_revision
```

### Action definition

```text
ActionDefinition
  action_id
  definition_version
  kind: composite | primitive
  target_types[]
  settlement_categories[]
  cost_schema_refs[]
  cooldown_schema_ref?
  realization_keys[]
  privacy_policy
  source_patch_revision
```

### Skill path definition

```text
SkillPathDefinition
  path_id
  definition_version
  skill_id
  action_id
  required_rank
  prerequisite_clauses[]
  cost_proposal_templates[]
  outcome_policy_ref
  learning_policy_ref
  strategy_tags[]
  deterministic_tie_break_key
  source_patch_revision
```

`prerequisite_clauses` 是 typed refs，只能读取 manifest 声明的 projection fields 或调用允许的 capability。不得嵌入任意代码、动态表达式或对 store 的查询句柄。

### Ability edge definition

能力图首批支持以下显式 edge kind：

```text
skill_unlocks_action
skill_supports_action
skill_requires_skill
action_requires_body_function
action_requires_equipment_trait
action_requires_resource
action_requires_permission
grant_provides_skill
grant_provides_action
restriction_blocks_skill
restriction_blocks_action
```

edge identity 为稳定 ID，并记录 definition version 与 source patch revision。循环 `requires`、悬空节点或同一 edge ID 语义冲突会阻止 patch 激活；不能靠注册或加载顺序决定最终图。

## Actor Ability Models

### Learned ability state

```text
LearnedAbilityState
  actor_ref
  skill_id
  rank
  proficiency
  confidence
  learned_at_event_id
  promotion_event_ids[]
  accepted_evidence_refs[]
  restrictions[]
  visibility_scope
  projection_revision
```

`rank/proficiency/confidence` 的变化必须来自事件。projection 不得因为 evaluator 给出更高估计而直接修改这些字段。

### Ability grant

```text
AbilityGrant
  grant_id
  actor_ref
  grants[]: skill_ref | action_ref | path_ref
  grant_kind: authored | learned | equipment | buff | contract | authority | scripted
  permanence: permanent | durable | revocable | leased
  source_ref
  source_patch_revision
  activation_event_id
  expiry_condition?
  revocation_policy
  status: active | revoked | expired | dormant
  visibility_scope
```

规则：

- `learned + permanent` 表示角色自身长期掌握；
- `equipment` 与 `buff` 必须是 `revocable` 或 `leased`；
- grant 的存在不修改 `LearnedAbilityState`；
- 同一技能同时由学习与装备授予时，撤下装备只撤销对应 `grant_id`，不能删除学习状态；
- grant 来源失效时必须追加 revoke/expire event，不能只在内存中过滤；
- patch disable 时，属于该 patch 的活跃 grant 按同一 settlement 原子撤销或进入明确的 dormant 策略。

### Ability restriction

```text
AbilityRestriction
  restriction_id
  actor_ref
  target_skill_ids[]
  target_action_ids[]
  restriction_kind
  severity: advisory | blocking
  source_ref
  activation_event_id
  removal_event_id?
  visibility_scope
```

长期封印、法律禁制或剧情 restriction 可以进入稳定图。当前受伤、资源不足等高频条件仍作为 affordance 输入，不为每次查询制造 graph mutation。

## Learning Evidence Model

```text
LearningEvidence
  evidence_id
  actor_ref
  skill_id
  action_id?
  path_id?
  source_settlement_id
  source_event_ids[]
  evidence_kind: authored_seed | training | successful_use | instructed | breakthrough | correction
  outcome_band
  primary_failure_domain
  quality_weight
  policy_revision
  accepted: true | false
  rejection_reason?
  occurred_at_authority_tick
  privacy_scope
```

学习证据必须事件溯源：

1. character mind 或 skill evaluator 可产生 `SkillEvidenceCandidate` advisory；
2. evidence policy 以已提交 settlement 结果、训练记录或授权 authored seed 验证候选；
3. 接受后追加 `LearningEvidenceRecorded`；
4. promotion policy 只读取已接受证据；
5. 达到规则时提出 `PromoteSkillRank`，再次经过 authority settlement；
6. 成功追加 `SkillRankPromoted`，失败则不改变 learned state。

既有 `character_skill_evidence_candidate_event` 继续是候选入口，不自动成为 gameplay event truth。默认首批 `promotion_enabled=false`；`adventure-basic` 可以通过 authored materialization 或显式 training fixture 建立剑术，不依赖自动升级。

## Ability Graph Projection

```text
AbilityGraphProjection
  actor_ref
  graph_schema_version
  definition_registry_revision
  active_patch_set_revision
  projection_revision
  source_revision_vector
  skill_nodes[]
  action_nodes[]
  path_nodes[]
  edges[]
  learned_states[]
  active_grants[]
  active_restrictions[]
  evidence_summary_refs[]
  unresolved_definition_refs[]
```

图投影只包含该 actor 被授权读取的内容。隐藏能力可以在 authority view 中存在，但在 Godot/public view 中只输出允许的摘要或完全省略。缺失字段不能被 consumer 解释成“角色不会”。

## Affordance Interface

### Query

```text
ResolveAbilityAffordanceRequest
  request_id
  actor_ref
  action_id?
  target_refs[]
  strategy_preferences[]
  expected_revision_vector?
  consumer_scope
  authority_tick
  registry_revision
  active_patch_set_revision
```

```text
AbilityAffordanceProjection
  request_id
  actor_ref
  action_id
  evaluated_at_authority_tick
  source_revision_vector
  definition_registry_revision
  active_patch_set_revision
  path_results[]
  selected_advisory_path_id?
  overall_status: available | blocked | unknown | unauthorized
  blocker_codes[]
  cost_estimates[]
  reservation_requirements[]
  risk_notes[]
  explanation_refs[]
  valid_until_revision_change
```

每个 `path_result` 至少包含：

```text
path_id
status
met_requirements[]
failed_requirements[]
unknown_requirements[]
cost_proposals[]
modifier_explanation_refs[]
source_grant_refs[]
```

affordance 中的 cost 只是 estimate/proposal。只有 settlement 成功的原子事件批次才能提交资源扣除。

### Read APIs

```text
get_ability_graph(actor_ref, view_scope, at_revision?) -> AbilityGraphProjection
resolve_affordance(request) -> AbilityAffordanceProjection
explain_ability_source(actor_ref, skill_or_action_ref, view_scope) -> AbilitySourceExplanation
list_available_actions(actor_ref, context_ref, view_scope) -> AbilityAffordanceSummary
list_learning_evidence(actor_ref, skill_id, view_scope) -> LearningEvidenceProjection
```

这些 API 均为读取或 advisory，不持有 event append 权限。

## Commands And Events

### Commands

```text
MaterializeAuthoredAbilitySeed
RecordLearningEvidence
LearnAbility
PromoteSkillRank
ActivateAbilityGrant
RevokeAbilityGrant
ApplyAbilityRestriction
RemoveAbilityRestriction
AttemptAbilityAction
```

所有 command 使用 foundation command envelope，包含 `command_id`、`idempotency_key`、`expected_revisions`、`source_ref`、`causation_id` 与 `correlation_id`。

### Events

```text
AuthoredAbilitySeedMaterialized
LearningEvidenceRecorded
LearningEvidenceRejected
AbilityLearned
SkillRankPromoted
AbilityGrantActivated
AbilityGrantRevoked
AbilityGrantExpired
AbilityRestrictionApplied
AbilityRestrictionRemoved
AbilityActionAttempted
AbilityActionSettled
AbilityActionRejected
```

失败前置条件默认不产生 gameplay event。`LearningEvidenceRejected` 与 `AbilityActionRejected` 仅在产品明确要求权威记录拒绝事实时追加；普通 API 拒绝通过 settlement result/audit trace 表达，不能为了“记录失败”引入部分资源写入。

## Data And Command Event Flows

### Authored seed materialization

```text
dossier capability seed candidate
-> validate definition and source lineage
-> MaterializeAuthoredAbilitySeed
-> authority settlement
-> AuthoredAbilitySeedMaterialized + AbilityGrantActivated/AbilityLearned
-> rebuild AbilityGraphProjection
```

dossier seed 本身保持 `candidate_only`。未经过 materialization event 的 seed 不得被当作运行时已学会能力。

### Ability query and action execution

```text
L3/L4, UI or gameplay rule requests action
-> resolve stable graph paths
-> evaluate current body/resource/equipment/environment/policy inputs
-> return SkillEvaluationAdvisory + AbilityAffordanceProjection
-> caller submits AttemptAbilityAction with selected or alternative path
-> settlement pins all revisions and re-evaluates preconditions
-> reserve costs
-> run typed rule/capability proposals
-> validate effect proposals
-> atomically append cost + action + effect events
-> update projections and Godot mirror
```

查询结果可能在提交前过期，因此 settlement 必须重评。不能因为 UI 刚显示 `available` 就跳过 revision、资源、目标或权限检查。

### Learning from a settlement

```text
committed AbilityActionSettled
-> evidence candidate generation
-> learning policy validation
-> LearningEvidenceRecorded
-> promotion threshold evaluation
-> optional PromoteSkillRank command
-> SkillRankPromoted or typed rejection
```

一次失败也可以成为训练证据，但是否可接受、权重和可晋升性由 pinned learning policy 决定，不能由模型自由解释。

### Equipment or buff grant lifecycle

```text
equipment/buff activation settlement
-> AbilityGrantActivated(source_ref = equipment/buff instance)
-> graph projection exposes active grant
-> affordance may become available

equipment/buff removal settlement
-> AbilityGrantRevoked(same grant_id/source_ref)
-> graph projection removes only that active grant
-> learned ability, evidence and unrelated grants remain
```

## Deterministic Affordance Resolution

resolver 必须遵循固定步骤：

1. 固定 registry、patch、policy、world config、actor aggregate 与 target revisions；
2. 读取 action definition 和所有 path，按 canonical `path_id` 排序；
3. 解析 actor learned state、active grants 与 stable restrictions；
4. 校验目标类型、权限、body functions、equipment traits、inventory accessibility；
5. 读取 resource available amount，扣除已存在 reservation 后生成 cost proposal；
6. 读取 status、cooldown、environment 与 effective-stat explanations；
7. 将失败分为 `blocking`、`unknown`、`advisory_risk`；
8. 对 viable paths 使用版本化 scoring policy 排序；
9. 相同得分以 `deterministic_tie_break_key` 和 `path_id` 解决；
10. 输出依赖 revision vector 与 explanation refs。

resolver 不得读取 wall clock、未固化随机数、网络或 map 未定义遍历顺序。时间相关条件使用 authority tick/calendar revision。任何未知必需输入默认为 `unknown/blocked`，不能猜测为可用。

## Advisory And Settlement Boundary

`CharacterSkillService.evaluate_action`、L3/L4、VLA、LLM、Godot UI 与 gameplay rule 可以：

- 提出 action/path；
- 对 viable path 排序；
- 说明预计成本、风险与替代方案；
- 生成学习 evidence candidate。

它们不能：

- 宣告动作已成功；
- 扣除资源或开始 cooldown；
- 提升技能 rank；
- 追加 gameplay event；
- 绕过 equipment、body、permission 或 revision precondition；
- 将预测或模型置信度转换为 authority truth。

settlement 返回的 `selected_path_id` 可以与 advisory 不同，但必须记录原因，例如 advisory path 在重评时过期、资源已被占用或权限 revision 已变化。

## Authority Invariants

1. 稳定能力图与即时 affordance 是不同状态组、不同 revision 和不同生命周期。
2. 学会技能不保证此刻可执行；当前受阻不删除学习状态。
3. 学习、晋升、grant 与 restriction 的权威变化必须来自 immutable events。
4. 装备、buff、契约和 scripted grant 可撤销，且永远不自动等同于永久学习。
5. skill evaluator、character mind、VLA、Rule IR 和 Godot 都是 advisory/proposal producer，不拥有 settlement。
6. affordance 查询不扣费、不追加事件、不确认 cooldown。
7. action settlement 必须重新校验 pinned revisions，不能信任过期 affordance。
8. 成本事件、action outcome 与领域 effects 在一个 transaction batch 中原子提交。
9. 学习证据必须引用已提交 settlement/event 或经授权的 authored/training source。
10. definition、edge、path 与 scoring 冲突必须显式拒绝或按声明策略解析，不能靠加载顺序。
11. 隐藏能力、证据和限制遵守 privacy scope，不因图查询而泄漏。
12. replay 同一事件与固定 definitions 必须得到相同能力图、affordance fixture 和 explanation digest。

## Failure Semantics

| Error code | Stage | Authority effect | Recovery |
| --- | --- | --- | --- |
| `skill_definition_unknown` | definition lookup | none | 启用/安装正确 definition revision |
| `ability_graph_reference_invalid` | graph validation | candidate rejected | 修复悬空或错误 edge |
| `ability_graph_cycle_invalid` | graph validation | candidate rejected | 移除非法 requires cycle |
| `ability_seed_not_materialized` | command validation | none | 提交显式 materialization command |
| `ability_not_granted` | affordance/settlement | none | 学习或激活合法 grant |
| `required_rank_not_met` | affordance/settlement | none | 选择其他 path 或完成训练 |
| `required_body_function_unavailable` | affordance/settlement | none | 恢复身体功能或选择替代 action |
| `required_equipment_missing` | affordance/settlement | none | 装备满足 trait 的物品 |
| `resource_insufficient` | reservation | none | 刷新资源或降低成本 |
| `ability_permission_denied` | policy | none | 获取授权；响应不得泄漏受保护细节 |
| `affordance_input_unknown` | projection | none | 请求缺失 projection/snapshot |
| `affordance_revision_stale` | settlement | none | 刷新后显式重试 |
| `ability_grant_source_inactive` | grant validation | none | 修复来源或撤销 grant |
| `ability_grant_revoke_conflict` | settlement | none | 用当前 revision 重试 |
| `learning_evidence_invalid` | evidence validation | none | 修复 settlement/source refs |
| `learning_promotion_not_allowed` | promotion policy | none | 满足 policy 或保留证据待后续 |
| `skill_path_conflict_unresolved` | registry activation | active revision retained | 声明明确 conflict/replace policy |
| `ability_settlement_rejected` | settlement | zero event batch | 展示结构化 blocker 与替代 path |

所有失败使用 foundation failure envelope。若 action batch 已提交而后续 projection 失败，结果必须报告 `committed=true` 与 projection degraded，不能谎报动作未发生。

## Acceptance Criteria

1. 角色掌握剑术时，右臂受伤只使挥剑 affordance 返回 `required_body_function_unavailable`，稳定 learned state 保持不变。
2. 伤势恢复后，无需再次学习或重授予，挥剑 affordance 自动恢复。
3. 耐力不足的动作不产生任何 stamina cost 或 action-success event。
4. affordance 查询本身不会改变 resource、cooldown、skill rank 或 event stream revision。
5. settlement 能拒绝查询后发生的 stale revision，并要求刷新重试。
6. 装备剑带来的 action grant 在卸装时撤销；角色自身学习的剑术与学习证据不受影响。
7. buff grant 到期只撤销自身 `grant_id`，不会撤销相同 action 的其他来源。
8. dossier capability seed 在 materialization 前保持 candidate-only；materialization 后能从事件重放恢复。
9. 学习证据可追溯到 committed settlement/event，伪造或悬空 source ref 被拒绝。
10. 自动 promotion 默认关闭；启用时也必须通过 policy 与 authority settlement。
11. evaluator 推荐 path 与 settlement 最终 path/拒绝结果都保留解释链，且 advisory 不能越过 authority。
12. 同一 revision vector、definitions 与 authority tick 重复解析得到相同 path 顺序、blocker 和 digest。
13. 隐藏能力不会出现在无权限 Godot/public projection 中。
14. graph 的悬空引用、非法循环、重复 ID 语义冲突和加载顺序依赖均阻止 patch activation。
15. `adventure-basic` 的购买、装备、受伤阻断、资源不足、恢复和卸装场景在在线执行与 full replay 后一致。

## Harness Mapping

### Current review gate

- `python scripts/verification/harness.py --profile docs`
- `python scripts/verification/harness.py --profile all`

在 `awaiting-user-review` 阶段，以上只证明文档纪律，不证明能力领域已实现。

### Required implementation profiles

- `gameplay-foundation-contract`
  - skill/action/path/grant/evidence/affordance schema；
  - privacy、revision 与 failure envelope。
- `gameplay-event-replay`
  - learned state、grant、restriction 与 evidence replay；
  - full/checkpointed projection digest 等价。
- `gameplay-state-groups`
  - `skills` 与 `ability_affordances` 分组、动态装配和只读 façade。
- `gameplay-possession-equipment`
  - equipment grant 激活、卸装撤销、多来源 grant 保留。
- `gameplay-patch-runtime`
  - ability definitions、graph conflicts、pinned scoring/learning policy。
- `gameplay-economy-authority`
  - cost reservation 与 action/effect batch 原子性。
- `godot-gameplay-mirror`
  - affordance delta、隐藏字段过滤、预测拒绝与刷新。
- `adventure-basic`
  - 剑术掌握与伤势/耐力阻断的完整场景。
- aggregate: `gameplay-foundation-all`

实现证据必须保留 command、event batch、source revision vector、active patch revision、graph/affordance digest、blocker explanation 和 replay result。
