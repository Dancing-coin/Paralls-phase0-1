# Heavenly Graph Semantic Foundation Design

- 日期：`2026-08-23`
- 状态：`user-approved`
- 范围：只修复 Heavenly Graph 本体，不修改角色智能体内部功能，不修改司命运行时决策逻辑
- 上位设计：`2026-07-11-current-project-siming-heavenly-knowledge-graph-and-story-node-design.md`
- 实现基线：`HeavenlyGraphPort`、`InMemoryHeavenlyGraphAdapter`、`SQLiteHeavenlyGraphAdapter`

## 1. 目标

本阶段把当前 Heavenly Graph 从“节点、关系、时间和事务存储基础”提升为可供角色和司命安全接入的语义图谱底座。

完成后，图谱必须能够表达、查询、校正和恢复：

- 世界事实和因果来源；
- 角色视角与知识状态引用；
- 一次行为回合的来源链；
- 故事节点、义务、吸引子和资源能力引用；
- 分支、永久关闭、修订和派生关系；
- reader scope、privacy、provenance 和 policy revision。

本阶段不让图谱执行角色行为或司命策略。图谱只提供规范存储、查询、校正、事务和回放能力。

## 2. 当前基线与问题

当前已经存在：

- `HeavenlyGraphScope`；
- `GraphValidity`；
- `GraphProvenance`；
- typed node/relation；
- `HeavenlyGraphWriteBatch`；
- valid-time / recorded-time 查询；
- revision chain；
- idempotency；
- referential integrity；
- checkpoint；
- deterministic InMemory contract；
- SQLite durable adapter。

当前仍缺少：

1. 语义节点和关系类型没有统一命名与能力声明；
2. 查询没有 reader principal、visibility scope、policy revision 和 source vector；
3. 没有一等的 causal path、conflict set、revision vector 查询对象；
4. correction/retraction/redaction 只有通用 revision 语义，没有统一生命周期；
5. branch 只有隔离，没有 fork、diff、replay 和永久关闭语义；
6. graph write batch 没有面向语义投影的 proposal/admission 约束；
7. checkpoint 没有携带完整 source vector、scope digest 和 policy revision；
8. 行为回合、故事节点和资源能力仍主要由消费者自行定义，无法保证跨系统一致。

## 3. 术语和所有权

### 3.0 Canonical Owner 与 World Truth Layer

`owner` 不是一个统一的“世界真相层模块”，而是某一类规范状态的唯一责任主体。

- `Canonical Owner`：对一类状态拥有唯一规范写入、校验和结算权的领域主体；
- `Domain Authority`：Canonical Owner 的运行时入口，负责验证命令、接受或拒绝变化，并提交领域事件；
- `World Truth Layer`：各 Canonical Owner 已提交的事实事件及其可重建投影组成的事实平面，不是单独的 owner；
- `Heavenly Graph`：消费已提交事实并保存关系、派生、冲突、分支和查询视图的知识层，不是事实 owner。

第一版的 owner 例子如下：

| 规范状态 | Canonical Owner / Authority |
| --- | --- |
| 对象、环境和物理交互结果 | ESM / 对应 World Authority |
| inventory 位置 | Inventory Authority |
| 产权归属 | Ownership Authority |
| 账户和经济结算 | Economy Authority |
| 身体资源与生存状态 | Body / Survival Authority |
| 角色主观记忆与心智状态 | Character Core |
| 故事线、叙事义务和收敛策略 | Siming 自有叙事状态 |

这些 owner 的已提交事件共同构成 `World Truth Layer`。图谱只能引用和组织这些 committed facts，不能把派生关系、模型 proposal 或摘要提升为领域事实。

统一写入链为：

```text
command / observation
  -> Domain Authority validation
  -> committed domain event
  -> World Truth Layer
  -> Heavenly Graph projection
```

因此以下主体都不是“全部世界状态”的通用 owner：

- Heavenly Graph 不是世界真相 owner；
- Siming 不是世界事实 owner；
- ESM 不是所有玩法状态的 owner；
- World Truth Layer 不是一个可以直接写入的模块。

### 3.1 图谱不是世界 Authority

各领域 Canonical Owner 仍然决定事实是否成立。图谱保存：

- owner-confirmed fact 的引用；
- 受治理的派生关系；
- 可审计的 proposal、correction 和 projection；
- 查询和恢复所需的版本信息。

图谱不得凭空创建世界事实，不得把模型输出或摘要伪装成 authority fact。角色 Core 只拥有角色主观记忆和心智状态；Siming 只拥有其叙事状态、义务和收敛策略，二者都不能越权写入其他领域事实。

### 3.2 三类记录

每个语义记录必须标记 `record_kind`：

- `fact`：来自 owner/authority 的事实引用；
- `projection`：由固定投影器从事实和授权视图派生；
- `proposal`：等待 owner 或策略验证的候选。

`proposal` 不得被查询层默认当成 `fact`，`projection` 必须保留来源向量和派生规则版本。

### 3.3 Reader scope

底座支持以下 scope：

- `public`；
- `actor_private`；
- `siming_internal`；
- `authority_only`；
- `branch_only`。

本阶段只实现 scope 校验和过滤，不决定角色或司命具体能读哪些业务字段。消费者必须传入 reader principal 和 allowed scopes。

## 4. 语义模型

### 4.1 公共语义元数据

所有 node/relation 必须携带或可推导：

```yaml
record_kind: fact | projection | proposal
visibility_scope: public | actor_private | siming_internal | authority_only | branch_only
derivation_kind: authority | projection | inference | correction | retraction | redaction
source_event_refs: []
source_revision_vector: {}
policy_revision: string
scope_digest: string
redaction_reason: string | null
```

现有 `GraphProvenance` 保留 source/causation/correlation/producer/actor 字段；新增字段必须扩展为兼容的 typed model，不允许在 `attributes` 中形成无约束的第二套 provenance。

### 4.2 统一行为回合引用

图谱底座只定义行为回合引用，不实现角色行为逻辑：

```yaml
turn_id: string
actor_id: string | null
correlation_id: string
causation_id: string
stage: context | interpretation | goal | intent | execution | settlement | evaluation | policy
source_refs: []
```

行为回合节点可以连接角色、世界事实、authority result 和 policy candidate，但底座不负责生成这些阶段。

### 4.3 领域节点类型

冻结第一版注册表：

- `world_fact`
- `causal_event`
- `actor_view`
- `actor_memory_ref`
- `behavior_turn`
- `storyline_thread`
- `story_node_blueprint`
- `story_node_instance`
- `narrative_obligation`
- `narrative_attractor`
- `resource_capability`
- `intervention_outcome`
- `branch_marker`
- `policy_candidate`

节点的领域 payload 仍由消费者 typed model 定义，但必须先通过 node type registry 校验 `record_kind`、namespace、allowed scopes 和 required provenance。

### 4.4 领域关系类型

冻结第一版关系注册表：

- `caused_by`
- `enabled_by`
- `prevented_by`
- `observed_as`
- `believed_as`
- `knows_about`
- `contradicts`
- `supersedes`
- `retracts`
- `derived_from`
- `part_of_turn`
- `opens_obligation`
- `transforms_obligation`
- `targets_attractor`
- `requires_capability`
- `realized_by`
- `closes_branch_node`
- `forked_from`

关系类型必须声明是否允许跨 namespace、是否允许 proposal、是否允许 branch-only，以及是否需要 source vector。

## 5. 查询契约

### 5.1 所有查询的共同上下文

所有语义查询必须携带：

```yaml
reader_principal: string
allowed_visibility_scopes: []
world_id: string
session_id: string
story_branch_id: string
valid_at: int
recorded_at: int | null
policy_revision: string
```

缺少 reader principal、scope、branch 或时间的语义查询必须 fail closed。底层兼容查询可以保留给现有合同测试，但消费者接入不得使用隐式全局查询。

### 5.2 查询类型

第一阶段实现以下 typed query：

- `NodeLookupQuery`：按 node id/type/source/record kind 查找；
- `RelationLookupQuery`：按 relation type/source/target 查找；
- `CausalPathQuery`：限定深度、关系类型和时间窗口的因果路径；
- `PerspectiveQuery`：按 reader scope、actor ref 和 visibility 查找视角投影；
- `ConflictSetQuery`：返回同一 subject/property 的并存冲突记录；
- `BehaviorTurnQuery`：按 turn/correlation/actor/stage 重建行为回合引用；
- `BranchDiffQuery`：比较两个 branch 的节点、关系、关闭标记和 source vector；
- `SourceImpactQuery`：查询某 source revision 被哪些派生节点引用。

查询结果必须包含：

- nodes；
- relations；
- selected refs；
- source revision vector；
- policy revision；
- scope digest；
- `truncated`；
- `incomplete_reason`。

### 5.3 有界查询

所有多跳查询必须显式提供：

- `max_depth`；
- `node_limit`；
- `relation_limit`；
- `max_paths`。

达到任意边界必须返回 `truncated=true`，不得静默丢弃结果或伪装成完整上下文。

## 6. 写入、校正与冲突

### 6.1 Typed proposal admission

图谱写入入口分为：

1. `AuthorityFactWrite`：owner-confirmed fact；
2. `ProjectionWrite`：固定投影器派生；
3. `ProposalWrite`：等待 validator 的候选。

`LLM`、角色内部推理和司命策略只能产生 `ProposalWrite`，不能直接调用底层 `write_batch`。

Admission 必须检查：

- namespace 和 owner；
- record kind；
- provenance；
- valid/recorded time；
- branch scope；
- relation endpoints；
- source vector；
- policy revision；
- visibility scope；
- idempotency key；
- revision predecessor。

### 6.2 Correction lifecycle

事实更正不删除历史：

```text
active
 -> superseded
 -> retracted | corrected
```

新的 correction/retraction 节点或关系必须引用原记录，并保留原 source/ref。查询默认返回当前有效视图，但 audit/replay 可以读取完整历史链。

### 6.3 Conflict coexistence

相同 subject/property 的冲突记录必须并存，并通过 `contradicts` 连接。查询层提供：

- all claims；
- current eligible claims；
- conflict set；
- authority-confirmed claim。

图谱底层不得自行把冲突合并成单一值。

## 7. 事务、版本和恢复

### 7.1 Atomic semantic batch

一个 batch 内的 node/relation、source vector 和 checkpoint tail 必须原子提交。失败不得产生半个语义投影。

### 7.2 Revision vector

每个 scope 维护可比较的 revision vector，至少按：

- node stream；
- relation stream；
- source stream；
- policy stream；
- branch stream。

读集携带 expected vector。发生 stale read 时返回结构化 conflict，不做部分合并。

### 7.3 Checkpoint and replay

checkpoint 必须携带：

- scope；
- valid/recorded time；
- node/relation refs；
- source revision vector；
- policy revision；
- scope digest；
- schema version；
- deterministic replay digest。

checkpoint 只能加速派生状态重建，不能替代原始事实和 replay tail。

### 7.4 Branch lifecycle

实现：

```text
production
 -> forked
 -> branch_work
 -> evaluated
 -> discarded | admitted_as_new_branch
```

branch-only 节点和关系不得写入 production scope。玩家关闭的节点必须追加 `closes_branch_node` 标记；原节点实例不可复活，只能在新因果条件下产生新的实例。

## 8. 适配器一致性

`InMemoryHeavenlyGraphAdapter` 和 `SQLiteHeavenlyGraphAdapter` 必须共享同一份语义合同测试，至少覆盖：

- typed registry validation；
- reader scope filtering；
- valid/recorded time；
- revision conflict；
- idempotent replay；
- atomic batch；
- correction and conflict coexistence；
- causal path bounds；
- branch isolation/fork/diff；
- checkpoint digest and replay equivalence；
- stale read rejection。

SQLite 是当前运行时 adapter；专用图数据库选型不属于本阶段。

## 9. 故障和降级

- 图谱不可用：底座返回 `graph_unavailable` 或 `graph_degraded`，不得返回伪造完整结果；
- 查询超界：返回 `truncated` 和边界原因；
- scope 不足：返回 `visibility_denied`，不泄漏节点存在性；
- stale read：返回 `stale_read_set`，不得部分写入；
- correction 链断裂：拒绝写入并返回 `invalid_revision_chain`；
- orphan relation：拒绝 batch；
- branch source vector 不匹配：拒绝 merge/admission。

本阶段不设计角色或司命 fallback 行为，只定义图谱底座的结构化失败结果。

## 10. 明确非目标

本阶段不修改：

- `CharacterAgentRuntime` 的 L1/L2/L3/L4 行为；
- 角色 prompt、人格、需求、情绪或 policy engine；
- 角色 session、goal、dynamic state 的持久化策略；
- `SimingRuntime.tick(...)`；
- story orchestrator 的节点选择；
- narrative obligation 的业务转换；
- resource reuse 的评分；
- online LLM；
- Godot runtime；
- 任何外部图数据库依赖。

## 11. 验收标准

### 必须通过的底座合同

1. 同一 semantic batch 在 InMemory 与 SQLite 结果一致；
2. 同一事实可以有多个 provenance 和视角 projection；
3. 双时态查询只返回有效记录；
4. scope 不足时 fail closed 且不泄漏存在性；
5. correction/retraction 保留历史并重建当前视图；
6. conflict set 可以并存、查询和回放；
7. causal path 和 subgraph 达到边界时明确 truncated；
8. revision vector 可检测 stale read；
9. checkpoint + tail replay 与 full replay 等价；
10. branch fork/diff/discard 不污染 production；
11. orphan relation、非法 owner、非法 namespace、错误 predecessor 全部拒绝；
12. 图谱不可用时不伪造完整故事或事实结果。

### 阶段产物

- semantic node/relation registry；
- reader/query context models；
- causal/conflict/turn/branch query contracts；
- correction/retraction lifecycle；
- revision vector and checkpoint digest；
- InMemory/SQLite parity tests；
- graph foundation verification profile；
- 本 spec 对应的 implementation plan。

## 12. 后续接入顺序

完成本阶段并通过用户验收后，才进入：

1. 角色私有图谱的语义召回和连续性接入；
2. 司命六域、故事线、义务、资源和多角色视角接入；
3. 角色与司命的统一行为/故事回合查询；
4. 在线 LLM 与 Godot 运行时证明。

本阶段不因后续消费者暂未实现而扩大底座职责。
