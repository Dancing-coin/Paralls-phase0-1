# Relationship Graph Boundaries Design

Status: `awaiting-user-review`

Date: `2026-07-23`

## Purpose

定义角色之间客观社会事实与 actor-private 主观关系的双层模型，使契约、债务、组织身份等可由 authority 结算，同时允许信任、敌意、恐惧、秘密和误解按角色视角独立演化。

## Scope

- `AuthorityRelationshipGraph` 的客观关系事实。
- 每个 actor 独立的 `ActorPrivateRelationshipGraph`。
- dossier seed、世界事件、记忆证据、经济契约和 Mind Frame 的连接边界。
- 权限过滤后的组合关系投影。
- 关系事件、生命周期、冲突、解释和重放约束。
- 与能力图和 Siming 图共享的治理值对象。

## Non-goals

- 不构建通用 `GraphNode/GraphEdge` 图运行时或统一图数据库。
- 不把所有文本记忆转换成关系边。
- 不让情绪数值自动创建婚姻、债务、雇佣等客观事实。
- 不让客观契约直接覆盖角色主观信任、误解或恐惧。
- 不在首批实现完整关系图 runtime；首批只冻结接口并保留集成边界。
- 不向 Siming 或其他 actor 暴露 actor-private 原始关系数据。

## Dependencies

- `2026-07-23-foundation-invariants-and-domain-boundaries-design.md`
- `2026-07-23-event-sourcing-and-authority-settlement-design.md`
- `2026-07-23-ownership-economy-and-transaction-design.md`
- `2026-07-23-skill-ability-graph-and-affordance-design.md`
- `2026-07-23-siming-perspective-knowledge-graph-contract-design.md`
- 现有 dossier、actor-private memory、Mind Frame 和 visibility projection。
- 现有 authority event、conversation resolution 和 world result。

## Shared Governance Values

关系图、能力图和司命图只共享以下值对象及其语义，不共享节点基类、边基类、查询引擎或存储：

```text
GraphEvidenceRef
SourceLineage
PrivacyScope
AuthorityScope
LifecycleState
ConflictRef
ExplanationPayload
```

建议字段：

```json
{
  "evidence_ref": {"ref_type": "authority_event", "ref_id": "evt-01", "revision": 4},
  "source_lineage": {"producer": "economy_settlement", "causation_id": "cmd-01"},
  "privacy_scope": "actor_private:char_a",
  "authority_scope": "subjective_projection",
  "lifecycle_state": "active",
  "conflict_refs": [],
  "explanation": {"reason_codes": ["observed_broken_promise"], "source_refs": ["evt-01"]}
}
```

这些值对象统一治理问题，不统一领域语义。关系的 subject/object、能力的 prerequisite、司命的 story dependency 仍使用各自 schema。

## Objective Relationship Facts

`AuthorityRelationshipGraph` 表达需要世界或制度权威确认的关系：

- 亲属、婚姻、监护等法定或世界设定事实。
- 组织成员、职位、阵营归属和代表权。
- 雇佣、租用、师徒契约、服务义务和指挥权。
- 债权债务、担保、承诺和交易形成的约束。
- 产权相关主体关系，但资产权利真相仍由 Ownership Ledger 持有。

核心记录：

```text
AuthorityRelationshipFact
  relationship_fact_id
  relation_type
  subject_ref
  object_ref
  qualifier
  authority_scope
  effective_from
  effective_until
  lifecycle_state
  source_refs
  transaction_id
  revision
```

规则：

- 事实边只能由 authority settlement、受信任迁移或明确的世界初始化事件产生。
- 债务金额、资产份额等规范数值只引用所属领域 aggregate，不复制成关系图真相。
- 终止关系通过新事件将 lifecycle 变为 `terminated` 或 `expired`，不删除历史边。
- 同一时段互斥关系必须由领域 policy 判定；图存储不能依赖最后写入获胜。

## Actor-private Subjective Relationships

每个 actor 拥有独立关系投影，其 scope 固定为 `actor_private:<actor_id>`：

```text
ActorPrivateRelationshipState
  owner_actor_id
  target_ref
  dimensions
    trust
    hostility
    fear
    respect
    intimacy
    obligation_felt
    suspicion
  labels
  believed_relationships
  known_secrets
  misunderstandings
  evidence_refs
  freshness
  revision
```

规则：

- 维度是 actor 对目标的主观读模型，不要求对称。A 信任 B 不代表 B 信任 A。
- `believed_relationships` 可以与 authority 事实冲突，冲突以 `ConflictRef` 保存而非自动纠正。
- `known_secrets` 只引用 memory/claim 标识和可见摘要，不把秘密正文复制到关系图。
- 主观变化必须来自 actor 实际可见的 percept、记忆、公开沟通、被授权披露或内在推理结果。
- 系统可以衰减 confidence/freshness，但不能仅因时间流逝伪造“已忘记”事件；遗忘由 memory policy 产出明确证据。

## Commands And Events

### Objective Commands

```text
relationship.establish_authority_fact
relationship.amend_authority_fact
relationship.terminate_authority_fact
```

这些命令必须经过 authority settlement。典型事件：

```text
relationship.authority_fact_established
relationship.authority_fact_amended
relationship.authority_fact_terminated
relationship.authority_fact_expired
```

### Private Projection Inputs

主观图不接受其他 actor 或客户端直接设置维度。它消费：

```text
relationship.private_evidence_recorded
relationship.private_interpretation_updated
relationship.private_label_added
relationship.private_label_removed
relationship.private_belief_revised
```

事件必须包含 `owner_actor_id`，并在 actor-private stream 内持久化。原始感知与记忆仍由原领域持有，关系事件只引用证据。

### Dossier Seed

dossier 中的初始关系通过一次性 materialization 转成有来源的 bootstrap event：

- 客观 seed 只有在 world authority 明确认可时进入 authority graph。
- 主观 seed 进入相应 actor-private stream。
- profile hot reload 不得静默覆盖运行中关系；必须生成 migration proposal 或后续修正事件。

## Projection Interfaces

### Authority Query

```text
get_authority_relationships(subject_ref, relation_types, at_revision)
has_authority_relation(subject_ref, object_ref, relation_type)
explain_authority_relation(relationship_fact_id)
```

### Actor-private Query

```text
get_private_relationship(owner_actor_id, target_ref, audience)
get_private_relationship_summary(owner_actor_id, target_ref, mind_frame_policy)
explain_private_dimension(owner_actor_id, target_ref, dimension)
```

调用者必须同时满足 owner identity 和 audience policy。后端内部 service 身份也不能默认读取全部 actor-private 图。

### Composed Actor View

Mind Frame 使用 `RelationshipPerspectiveFacade` 组合：

```text
actor-visible authority facts
+ actor-private subjective state
+ explicit uncertainty/conflict markers
-> visibility-filtered relationship factor
```

组合规则：

- 客观事实与主观判断保留来源标签，不合并为一个无来源数值。
- 角色不知道的 authority fact 不进入其 Mind Frame。
- “角色认为欠债”与“authority 账本存在债务”可同时存在并明确冲突。
- Godot 玩家视图只能读取玩家被授权看到的 projection，不默认等于角色 Mind Frame。

## Data Flow

```text
authority settlement / percept / memory / dossier seed
-> domain-specific relationship event
-> objective or actor-private event stream
-> independent relationship projection
-> RelationshipPerspectiveFacade
-> Mind Frame / authorized UI / rule condition
```

Siming 只能看到：

- 公共或 authority-visible 客观关系事实。
- 角色主动外化后的 statement/behavior event。
- 经专门 facade 允许披露的 actor perspective 摘要。

Siming 不能读取 `ActorPrivateRelationshipState` 或其原始 memory evidence。

## Authority And Privacy Invariants

1. 客观关系事实由 authority 领域确定；actor-private 图不能创建或撤销客观事实。
2. 主观关系属于 owner actor 私有认知；客观事实不能强制覆盖其误解或感受。
3. 关系双向、对称或传递性只能由明确 relation policy 声明，不能由图结构猜测。
4. 债务、产权、合同金额的真相归所属领域；关系图只保存引用和角色连接。
5. actor-private 证据不得进入公共 trace、Godot 普通镜像或 Siming 原始输入。
6. 图之间只共享治理值对象，不引入通用图 runtime。
7. 所有边都必须可追溯到 source refs，且生命周期变化可重放。

## Failure Semantics

| Failure | Required result |
|---|---|
| objective command lacks authority | `relationship_authority_denied`，无事件 |
| unknown subject/object | `relationship_endpoint_not_found`，无悬空边 |
| conflicting exclusive fact | `relationship_fact_conflict`，返回 conflict refs |
| private write targets another owner | `actor_private_scope_violation`，安全审计 |
| evidence not visible to actor | `relationship_evidence_not_visible`，不更新主观图 |
| referenced contract missing | objective proposal rejected, no partial relation write |
| projection evidence missing | projection marked degraded; event stream retained |
| unknown event version | rebuild/upcast gate fails; no silent skip |

## Acceptance Criteria

1. 同一对 actor 能同时存在客观雇佣事实、A 对 B 的信任和 B 对 A 的敌意，且三者独立重放。
2. A 对 B 的信任变化不会改变 B 的主观图，也不会创建客观关系。
3. 债务结算可创建 authority relation ref，但债务金额只从 Ownership/Economy 领域读取。
4. 角色对某关系的误解可与 authority fact 并存，Mind Frame 明确显示 belief 和 known fact 的来源差异。
5. dossier seed materialization 可重放且 hot reload 不覆盖运行中状态。
6. 未授权调用者、其他 actor、Godot 普通客户端和 Siming 均不能读取 actor-private 原始关系图。
7. 终止关系保留历史来源，任意 revision 查询结果确定。
8. 关系图、能力图和司命图没有共享通用 node/edge runtime 依赖。

## Harness Mapping

该领域不进入首批 runtime 闭环，但接口和隔离测试纳入：

- 主要 profile：`gameplay-foundation-contract`
- 安全 profile：`gameplay-foundation-all` 中的 authority/privacy checks
- 后续专用 profile：`relationship-graph-runtime`

首批 contract fixture 必须验证双层 schema、scope gate、冲突保留和无通用图 runtime 依赖。后续 runtime profile 再验证完整事件重放、Mind Frame 组合和跨域债务引用。
