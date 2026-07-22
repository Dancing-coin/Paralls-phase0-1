# Siming Perspective Knowledge Graph Contract Design

Status: `awaiting-user-review`

Date: `2026-07-23`

## Purpose

定义司命 Perspective/Knowledge Graph 的完整领域契约，使司命未来能够追踪“谁可能看见了什么、哪些声明由什么证据支持、哪些剧情节点依赖哪些事实、哪里存在证据冲突”，同时保持司命的高层催化者边界。

本 spec 完整冻结模型、输入、查询、隐私和 authority 契约，但该图谱 runtime 不进入 `adventure-basic` 首批实现闭环。

## Scope

- `Actor`、`Perspective`、`Fact`、`Percept`、`KnowledgeClaim`、`ModalityEvidence`、`StoryBeat`、`Intervention` 的领域定义。
- 观察、错过、声明持有、证据支持/冲突、剧情依赖和干预目标等关系。
- 允许输入、禁止输入、来源追踪和压缩摘要边界。
- 与现有 Siming Global Situation、authority bus、public fact、actor perspective facade 的连接。
- 图谱生命周期、冲突解释、查询、重放和迁移要求。
- 首批只冻结契约时所需的 contract tests。

## Non-goals

- 不在首批实现图数据库、ingest worker、长期压缩服务或完整查询引擎。
- 不替换 `SimingRuntime`、Global Situation Layer、authority event bus 或现有 read model。
- 不把司命图谱定义成世界真相源。
- 不读取 actor-private 原始记忆、私有多模态 cache、hidden state 或 chain-of-thought。
- 不让司命直接修改 world truth、关系图、角色状态或低层动作。
- 不建立跨关系图、能力图和司命图的通用 Graph Core。
- 不把 VLA/advisory 结果提升为已确认事实。

## Dependencies

- `2026-07-23-foundation-invariants-and-domain-boundaries-design.md`
- `2026-07-23-event-sourcing-and-authority-settlement-design.md`
- `2026-07-23-relationship-graph-boundaries-design.md`
- `2026-07-23-persistence-replay-migration-and-hot-reload-design.md`
- `docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-02-current-project-siming-global-situation-layer-design.md`
- `docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-05-current-project-multi-actor-private-perspective-reconciliation-design.md`
- 现有 `AuthorityEvent`、L1 fact/percept、`world_result`、Siming evidence chain 和 intervention candidate。

## Position In The Runtime

```text
public facts / authority results / Siming percepts
+ multi-actor public perspective receipts
+ explicitly disclosed actor statements
+ advisory modality evidence
-> Siming graph ingest contract
-> Siming Perspective/Knowledge projections
-> Global Situation / story assessment / intervention candidate enrichment
-> existing policy and feasibility gates
-> high-level Siming event
-> authority settlement when world write is requested
```

图谱输出是解释和候选生成输入，不是 authority settlement 结果。

## Shared Governance Values

司命图与关系图、能力图只共享：

```text
GraphEvidenceRef
SourceLineage
PrivacyScope
AuthorityScope
LifecycleState
ConflictRef
ExplanationPayload
```

司命图独立定义节点、关系、索引和查询。不得因为字段相似而引入通用 `GraphNode`、`GraphEdge` 或共享 traversal runtime。

## Domain Entities

### `Actor`

图内 actor reference，不复制角色档案：

```text
actor_ref
actor_kind
public_identity_ref
lifecycle_state
source_refs
```

匿名、伪装或身份不确定时，使用 evidence-backed provisional ref，并通过 identity resolution 事件关联；不能直接合并节点。

### `Perspective`

表示某主体在特定时空、传感与权限条件下的观察窗口：

```text
perspective_id
holder_ref
capture_root_id
scene_id / zone_id
time_window
modality_scope
visibility_policy_ref
context_ref
lifecycle_state
source_refs
```

`Perspective` 说明“该视角具备什么观察条件”，不自动证明 holder 实际知道全部可见事实。

### `Fact`

```text
fact_id
fact_type
subject_ref
predicate
object_or_value
authority_scope
valid_time
confidence
lifecycle_state
source_refs
```

事实必须区分：

- `authority_confirmed`
- `public_observed`
- `siming_inferred`
- `advisory_candidate`

只有前两类可作为强事实依据；推断和 advisory 必须保留不确定性，不能被序列化成无标记真值。

### `Percept`

表示经现有 actor/public/Siming 感知链生产的观察结果引用：

```text
percept_id
perspective_id
fact_candidate_refs
capture_ref
freshness
confidence
privacy_scope
source_refs
```

图谱不拥有原始图像、音频或角色私有 percept payload；只保留允许范围内的标识、摘要和 evidence refs。

### `KnowledgeClaim`

表示“某主体公开表达、被允许披露或由司命自身形成的声明”，而不是直接读取角色脑内真值：

```text
claim_id
claimant_ref
claim_content
epistemic_mode
about_fact_refs
expressed_at
privacy_scope
confidence
lifecycle_state
source_refs
```

`epistemic_mode` 至少包括 `asserts`、`suspects`、`denies`、`misunderstands`、`unknown`。角色未外化的 belief 不得创建 Siming `KnowledgeClaim`。

### `ModalityEvidence`

```text
modality_evidence_id
modality
capture_ref
provider_ref
advisory
confidence
freshness
supports_refs
conflicts_with_refs
source_refs
```

所有 VLA/模型推断默认 `advisory=true`。它可以支持调查、冲突标记和 intervention candidate，不能直接结算世界事实。

### `StoryBeat`

```text
story_beat_id
status
required_fact_patterns
participation_constraints
visibility_constraints
fairness_policy_ref
dependency_refs
source_refs
```

状态至少包括 `candidate`、`open`、`blocked`、`resolved`、`abandoned`。StoryBeat 是导演态势读模型，不允许改写角色目标或世界状态。

### `Intervention`

```text
intervention_ref
candidate_type
target_refs
story_beat_refs
evidence_refs
policy_ref
feasibility_ref
dispatch_event_ref
settlement_result_ref
lifecycle_state
```

图谱记录候选、派发和结果之间的因果链；不绕过现有 Siming policy/feasibility/authority 链。

## Domain Relations

必须使用领域专有关系类型：

```text
Perspective --observed--> Percept
Perspective --missed--> Fact
Percept --suggests--> Fact
Actor --expressed--> KnowledgeClaim
KnowledgeClaim --about--> Fact
ModalityEvidence --supports--> Fact | KnowledgeClaim
ModalityEvidence --conflicts_with--> Fact | KnowledgeClaim
StoryBeat --depends_on--> Fact | KnowledgeClaim
StoryBeat --involves--> Actor
Intervention --targets--> Actor | StoryBeat | PerspectiveGap
Intervention --responds_to--> Fact | ConflictRef | StoryBeat
```

`missed` 只有在观察窗口、可见性和 delivery/receipt 证据足够时才能产生；“没有 percept 记录”本身不证明 actor 错过了事实。

## Input Contract

### Allowed Inputs

- public fact event 和 authority-confirmed world result。
- Siming 自身独立的 `siming_mm:*` context 及其 advisory evidence。
- 多 actor 公共 patch 和不含角色私有 payload 的观察回执。
- 现有 `SimingGlobalSituationLayer` 输出及其 evidence refs。
- 角色主动说出、公开执行或通过正式 facade 明确披露的 perspective summary。
- policy 明确允许的关系客观事实和 Gameplay Foundation projection 摘要。

### Forbidden Inputs

- `character_mm:*` cache、角色私有 capture 或 inference history。
- `CharacterPrivateWorldSnapshot` 原始 payload。
- actor-private memory、关系图、秘密正文、hidden state 和 chain-of-thought。
- 未经 facade 和 disclosure policy 的 Mind Frame 内容。
- Godot 本地预测、UI 状态或未确认表现事件。

### Facaded Actor Perspective

允许的 actor perspective facade 必须返回：

```text
disclosure_id
actor_id
disclosure_kind
public_or_targeted_summary
privacy_scope
authorized_audience
source_refs
expires_at
```

它代表角色已经外化或 policy 允许披露的内容，不是司命读取角色私有图的后门。

## Ingest And Event Contracts

后续 runtime 应消费版本化事件，而不是直接 mutate graph：

```text
siming_graph.perspective_registered
siming_graph.percept_linked
siming_graph.fact_registered
siming_graph.claim_expressed
siming_graph.evidence_linked
siming_graph.conflict_registered
siming_graph.story_beat_updated
siming_graph.intervention_linked
siming_graph.node_superseded
```

所有 ingest event 至少包含：

```text
event_id / event_version
transaction_id / causation_id / correlation_id
source_ref / privacy_scope / authority_scope
payload
```

重复 evidence ref 按 idempotency key 去重。纠错通过 supersede/conflict 事件完成，不修改历史节点。

## Query Contract

后续最小查询面：

```text
who_observed(fact_id, at_time, policy)
who_missed(fact_id, at_time, policy)
claims_about(fact_id, audience_policy)
evidence_for(node_or_relation_id)
conflicts_for(node_or_relation_id)
open_story_beats(scene_id, policy)
explain_intervention(intervention_ref)
```

每个查询返回：

```text
result
as_of_revision
source_refs
uncertainty
conflicts
privacy_redactions
explanation
```

查询不能因调用者权限不足而泄露“存在一个秘密节点”；被裁剪内容应按 policy 返回 `not_visible` 或聚合计数，具体策略需防侧信道。

## Compression And Context Rules

- 压缩摘要是可重建 projection，不是新真相源。
- 摘要必须记录 covered revisions、source refs、privacy scope 和生成 policy。
- 不同 actor 或不同 privacy scope 的摘要不能混合缓存。
- summary 过期后只能标记 stale 或重建，不能用新证据静默改写旧摘要。
- 给模型的上下文只包含当前任务所需、调用者可见、带来源和不确定性标记的数据。

## Authority And Privacy Invariants

1. Siming 图是证据化态势读模型，不是 world-truth authority。
2. Siming 只能发高层 catalyst/intervention candidate；低层动作和世界写入仍走现有 authority settlement。
3. actor-private 原始记忆和关系状态永不作为图谱输入。
4. 角色“知道什么”只有在公开表达、正式披露或可验证 delivery receipt 下才能进入 Siming claim/perspective；不能由全知后端推断。
5. advisory modality evidence 永远保留 advisory 和 confidence 标记。
6. 证据冲突必须并存，不用最后写入覆盖。
7. 图谱与其他领域只共享治理值对象，不共享通用图 runtime。

## Failure Semantics

| Failure | Required result |
|---|---|
| actor-private input detected | `siming_graph_private_input_rejected`，不 ingest，安全审计 |
| unknown source/evidence | `siming_graph_evidence_unresolved`，节点不激活 |
| advisory presented as authority fact | `siming_graph_authority_scope_violation` |
| invalid missed inference | `siming_graph_insufficient_observation_evidence` |
| duplicate ingest | 返回原 ingest result，不重复边 |
| conflict | 建立 `ConflictRef`，保留双方，不自动裁决 |
| privacy query denied | `not_visible`，不泄露节点内容或存在性 |
| unknown event version | projection rebuild fails closed |
| intervention write attempt | 拒绝 direct write，要求走 Siming dispatch + authority path |

## Acceptance Criteria

首批 contract freeze 必须证明：

1. 八类实体及领域关系有独立 schema、version 和 privacy/authority scope。
2. allowed/forbidden input fixture 能拒绝 `character_mm:*`、private snapshot 和 actor-private relationship payload。
3. 公开声明可形成 `KnowledgeClaim`，未外化 private belief 不会形成 claim。
4. advisory evidence 与 authority fact 在 schema 和查询结果中不可混淆。
5. 所有 query contract 返回 source、uncertainty、conflict 和 redaction 元数据。
6. intervention 只能引用现有 dispatch/settlement 链，不能直接写 world truth。
7. schema/import 检查证明没有引入共享 Graph Core。
8. 文件和 README 明确标记该 runtime 不属于首批 `adventure-basic` 实现。

后续 runtime 实施完成时还必须证明：

9. 从空事件流重放得到相同图谱 projection。
10. 压缩摘要与底层可见证据一致且不同 privacy scope 不串缓存。
11. who-observed/who-missed 在证据不足时不会产生伪确定答案。
12. 图谱增强 Siming candidate 后，policy/feasibility/authority 门禁仍然有效。

## Harness Mapping

- 首批 contract profile：`gameplay-foundation-contract`
- 首批 privacy/security checks：`gameplay-foundation-all`
- 后续 runtime profile：`siming-perspective-knowledge-graph`

首批证据覆盖 schema、input rejection、privacy redaction、authority scope 和 dependency boundary。图谱 ingest/query/replay/summary 的运行证据属于后续 profile，不得在首批完成报告中伪称已实现。
