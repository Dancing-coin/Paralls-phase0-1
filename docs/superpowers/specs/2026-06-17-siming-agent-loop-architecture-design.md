# 司命 Agent Loop 架构设计

Status: awaiting-user-review

## 问题

当前司命文档其实有两层视角：

- `docs/phase1/core/01-运行时核心/司命设计文档.md` 是主源头，定义的是完整司命本体：一个运行在 `L2` 的全局叙事智能体，具备五大子系统、高层催化、四原则、优先级治理和运行时主循环。
- `docs/phase1/core/01-运行时核心/司命/02-Phase1公平裁判型司命增强方案.md`、`04-Intervention Policy Engine 规则表.md`、`05-Godot Execution Feasibility Layer 接口契约.md`、`19-司命接入事件总线后端设计.md` 是工程切片，负责把完整司命收敛成能实现、能测试、能 replay、能接入权威事件总线的运行时边界。

下一步设计要做的不是把司命压成一个被动事件处理器，也不是把它放开成一个无限制 LLM 工具 Agent，而是明确：**司命应作为一个受严格工程护栏约束的叙事 Agent Loop**。

## 目标

把司命设计成一个：

```text
目标驱动
事件驱动
策略约束
多智能体协作
可审计可回放
```

的叙事编排循环系统。

本设计覆盖完整未来态的“单局 / 单房间”司命 Agent Loop，并为跨局记忆、命运种子和长期演化保留明确接口。跨局能力只定义接入位置，不要求第一阶段实现。

## 非目标

- 不设计通用 LangChain / ReAct 式自主工具 Agent。
- 不允许 LLM 直接发布 authority event。
- 不允许 LLM 直接调用 ESM、Character、L3 或 Godot API。
- 不替代 ESM 的物理权威。
- 不替代角色智能体的自主决策。
- 不替代视觉事实边界或 AuthorityEventBus。
- 不让 read model、dashboard、memory 或 model output 成为世界真值。
- 不把本 spec 扩展成 implementation plan。
- 不要求第一阶段实现跨局长期演化。

## 设计源头

主源头：

- `docs/phase1/core/01-运行时核心/司命设计文档.md`

工程切片：

- `docs/phase1/core/01-运行时核心/司命/02-Phase1公平裁判型司命增强方案.md`
- `docs/phase1/core/01-运行时核心/司命/04-Intervention Policy Engine 规则表.md`
- `docs/phase1/core/01-运行时核心/司命/05-Godot Execution Feasibility Layer 接口契约.md`
- `docs/phase1/core/01-运行时核心/司命/19-司命接入事件总线后端设计.md`
- `docs/superpowers/specs/2026-06-15-siming-phase1-llm-authority-bus-runtime-design.md`

## 架构选择

采用：

```text
SimingOrchestrator + 五子系统端口 + 工程护栏端口
```

不采用的方案：

- 单体 `SimingAgentLoop`：启动简单，但会把 observe、state、planning、guard、dispatch、model routing、audit 全塞进一个大核心。
- 直接多 Agent runtime：更接近远期分布式司命，但在领域对象和生命周期稳定前过早拆分，容易让系统散掉。

`SimingOrchestrator` 只负责循环调度和生命周期。五大子系统负责领域判断。工程护栏端口负责确定性边界。

## 核心定位

司命是叙事运行时总导演，不是直接执行者。

通用 Agent Loop 结构：

```text
Observe
  -> State
  -> Reason / Plan
  -> Guard
  -> Act
  -> Observe Result
  -> Loop
```

映射到司命领域：

```text
AuthorityEvent / ESM / Character / L1 / L3 输入
  -> ObservePipeline
  -> FactCore / KnowledgeGraph / BalanceSystem / NarrativeState
  -> GoalStack + ConflictGenerator + ModelRouter
  -> InterventionCandidate
  -> Fact veto + PolicyGuard + ExecutionFeasibility
  -> InterventionDecision
  -> InterventionExecutor
  -> siming.* 高层事件
  -> 下游回流结果
  -> Audit / Replay / State correction
```

一句话：

> 司命持续观察世界，维护事实与叙事状态，基于目标栈规划候选干预，再经过事实、策略、可执行性和审计护栏，只通过高层事件影响角色、环境和信息流。

## 层级目标栈

司命使用层级目标栈。高层目标约束低层目标：

1. **命运主题 / 本局核心张力**：这一局到底围绕什么主题和命运压力展开。
2. **戏剧推进 / 防止停滞**：让冲突、悬念、揭示、转折和收束持续发生。
3. **公平可玩 / 参与窗口**：保证玩家和角色有合理参与机会，避免信息垄断、角色边缘化和线索卡死。
4. **最小干预 / 自然发生**：优先选择弱的、局部的、可解释的催化。
5. **可审计可回放**：每次行动和不行动都必须能解释、能 replay、能纠错。

这使司命既不是“戏剧最大化机器”，也不是“只做公平裁判”。它可以主动思考如何影响故事线，但每次行动都要被完整目标栈裁决。

## 核心组件

### `SimingOrchestrator`

职责：

- 驱动 Agent Loop。
- 管理 event-triggered tick、scheduled tick、phase tick。
- 把任务路由到优先级 lane。
- 调用五大子系统端口。
- 汇总子系统输出并形成决策。
- 不直接改世界真值。
- 不直接改 ESM 状态。
- 不直接改角色状态。
- 不直接改 Godot 表现状态。

状态：必须存在。

### `GoalStack`

职责：

- 表示本局命运主题、戏剧压力、公平可玩需求、最小干预原则和审计要求。
- 当目标冲突时提供优先级。
- 为 planning 提供权重，不直接产生动作。

状态：完整设计中必须存在；第一阶段可以先用固定配置实现。

### `ObservePipeline`

职责：

- 消费司命有资格观察的事件。
- 把原始事件和结构化事件归一化成司命输入对象。
- 保留 source、causation、correlation、phase、timing 元数据。
- 拒绝或忽略司命无资格消费的事件。

输入包括：

- world fact
- ESM result
- constraint state
- visual fact
- character behavior result
- knowledge propagation change
- room phase signal

状态：必须存在。

### `FactCorePort`

职责：

- 维护 `T0-T3` 事实边界。
- 追踪已成立事实、已拒绝事实和锁定事实。
- 检测矛盾。
- veto 会泄露未知信息或改写锁定真相的候选。

它守护真相，不负责让戏更好看。

状态：必须存在；可以从窄的 fact-lock 模型开始。

### `KnowledgeGraphPort`

职责：

- 维护“谁知道什么”。
- 维护“谁知道别人知道什么”。
- 表达会话接入、偷听、共享、误解、隐私风险、成员资格。
- 给 planning 和 guard 提供结构化知识摘要。

它只能基于 L1 / ESM / event facts 推断社会关系和知识状态，不得虚构原始空间事实或声学事实。

状态：预留但应尽早定义接口；完整图谱深度可以渐进实现。

### `BalanceSystemPort`

职责：

- 检测信息垄断。
- 检测参与饥饿。
- 检测私密通道锁死。
- 检测怀疑过热。
- 检测证据瓶颈。
- 产出 planning 可使用的局势压力信号。

状态：必须存在。

### `ConflictGeneratorPort`

职责：

- 枚举冲突机会。
- 识别次生事件候选。
- 识别环境催化窗口。
- 识别阶段收束和结局机会。
- 估计叙事价值和风险。

状态：完整司命必须存在；第一阶段可以从有限候选生成器开始。

### `ModelRouterPort`

职责：

- 把推理任务路由给规则、小模型、大模型或专门子智能体。
- 执行 latency budget 和 priority lane 约束。
- 只返回 candidate-level 输出。

可选 route：

- rule route：硬边界和确定性过滤。
- small-model route：快速分类、风险打分、候选排序。
- large-model route：复杂叙事判断、多角色动机解释、冲突机会枚举、催化方案候选。
- specialist route：未来的 Fact Auditor、Conflict Scout、Knowledge Agent、Narrative Planner、Ending Agent。

状态：必须作为端口存在；具体 route 可逐步增加。

### `InterventionPlanner`

职责：

- 把机会、模型输出和子系统建议转成 `InterventionCandidate`。
- 选择 proposed band：
  - `impulse`
  - `opportunity`
  - `fact_reveal`
  - `environment_request`
  - `none`
- 保留候选理由、预期叙事效果、风险标签和需要的下游路径。

状态：必须存在。

### `PolicyGuard`

职责：

- 执行四原则：间接性、不可见性、逻辑自洽性、公平性。
- 保护角色自主性。
- 防止改写锁定事实。
- 防止绕过 ESM。
- 降级或拒绝不安全候选。

状态：必须存在。

### `ExecutionFeasibilityPort`

职责：

- 判断候选能否在当前引擎和房间状态里自然落地。
- 选择路径：
  - `character_input_path`
  - `environment_change_path`
  - `visual_fact_path`
  - `l3_highlight_path`
  - `no_action`
- 对同一个 candidate + context 返回确定性 decision。

状态：必须存在。

### `InterventionExecutorPort`

职责：

- 通过 AuthorityEventBus 发布高层 `siming.*` 事件。
- 不发布物理成功事实。
- 不直接调用 ESM、Character、L3 或 Godot。
- 保留 causation、correlation、idempotency、TTL、priority 和 audit 引用。

状态：必须存在。

### `AuditReplayPort`

职责：

- 记录观察、候选、veto、降级、dispatch、ack、timeout、rejection、no_action 和 correction。
- 支持按 `correlation_id`、`causation_id`、`event_id` replay。
- 解释司命为什么行动，也解释为什么没选其他行动。

状态：必须存在。

### `LongTermMemoryPort`

职责：

- 预留跨局玩家风格画像。
- 预留 recurring theme memory。
- 预留 destiny seed library。
- 预留未解决的 archetype pattern。
- 预留 pacing profile。
- 预留跨局 safety notes。

长期记忆可以影响：

- 新局主题建议。
- 命运主题权重。
- 冲突种子选择。
- 节奏偏好。
- 安全和体验约束。

长期记忆不能影响：

- 当前局锁定事实。
- 当前局物理结果。
- 角色即时心理真值。
- ESM 成功事实。

状态：预留端口。

## 优先级 Lane

司命不能只有一个 FIFO 队列。

```text
P0 Hard Guard Lane
  事实冲突、锁定真相、关键安全、即时 veto
  只走规则，不等待 LLM

P1 State Maintenance Lane
  事实入库、知识更新、ESM / Character / VisualFact 回流
  快速、可重放、可并发

P2 Deliberation Lane
  戏剧推进、冲突机会、定制化催化
  可以调用 ModelRouter

P3 Atmosphere / Optional Lane
  低价值提示、氛围、延后增强
  可降级、可丢弃、可延迟
```

`P0/P1` 不得被 `P2` 模型调用阻塞。系统高负载时 `P3` 可以丢弃。

## Tick 触发

司命有三类 tick：

- **Event-triggered tick**：关键 AuthorityEvent、ESM 结果、角色行为、视觉事实或约束变化触发。
- **Scheduled tick**：周期性检查节奏、参与度、信息瓶颈和 cooldown。
- **Phase tick**：阶段切换、案件升级、接近结局或房间关闭时触发。

因此司命是事件驱动的，但允许周期性和阶段级思考。

## 行动边界

允许的高层输出：

- `siming.impulse`
- `siming.opportunity`
- `siming.fact_reveal`
- `siming.environment_request`
- `siming.visual_observability_request`
- `siming.presentation_highlight_request`
- `siming.no_action_recorded`

禁止输出：

- 直接 `world_fact` 成功结果。
- 直接 ESM 状态 mutation。
- 直接角色移动、台词或心理真值。
- 直接 Godot 动画、transform 或骨骼命令。
- 直接创建未成立事实。
- 绕过 AuthorityEventBus。

## 下游协作

### Character Runtime

接收：

- `impulse`
- `opportunity`
- `fact_reveal`

角色仍保持自主。角色可以返回 ack、result、ignore、reject 或 behavior event。司命可以观察并重新规划，但不能强制执行。

### ESM

接收：

- `environment_request`

ESM 判断物理、空间和规则约束是否允许该请求。ESM 返回 accept、reject、constraint 或 world fact result。司命不得把 rejection 改写成 success。

### VisualFact / Perception Boundary

接收：

- `visual_observability_request`

它只能放大已成立事实的可见性，不能创造事实。

### L3 / Godot Presentation

接收：

- `presentation_highlight_request`

它选择表现策略和降级方式，但不成为世界真值权威。

### AuthorityEventBus

所有跨系统输入输出都必须经过总线。总线负责保留 causation、correlation、priority、TTL、durability 和 replay 链。

## 模型与子智能体输出契约

模型和子智能体输出在影响主循环前必须先归一化。

输入结构：

```text
SimingReasoningContext
  room_id
  phase
  goal_stack
  fact_state_summary
  knowledge_state_summary
  balance_state
  narrative_pressure
  recent_events
  recent_interventions
  forbidden_actions
  available_paths
  latency_budget
  priority_lane
```

输出结构：

```text
InterventionCandidate
  candidate_id
  reason
  proposed_band
  target_actor_ids
  target_object_ids
  target_environment_ids
  established_fact_refs
  expected_narrative_effect
  risk_tags
  confidence
  required_downstream_path
```

禁止模型输出：

- authority event
- final selected decision
- physical success claim
- Character belief truth
- ESM mutation
- Godot command

所有模型输出必须经过：

```text
CandidateNormalizer
  -> FactCorePort
  -> PolicyGuard
  -> ExecutionFeasibilityPort
  -> AuditReplayPort
```

## 状态模型

### Working State

单轮 tick 临时状态：

- current event batch
- state snapshot
- reasoning context
- candidate set
- decision set
- dispatch plan

### Runtime State

单局 / 单房间状态：

- fact state
- knowledge state
- balance state
- narrative state
- intervention state
- priority lane state
- audit cursor

### Read Models

Read model 用来解释 loop，不成为权威。

- Siming dashboard read model
- Narrative read model
- Audit replay model

原则：

```text
Memory informs planning.
Memory never overwrites truth.
Read models explain decisions.
Read models never become authority.
```

## 错误处理与降级

| 情况 | 行为 |
| --- | --- |
| LLM timeout | 使用规则候选、小模型候选或 `no_action`；audit 写 `llm_timeout` / `degraded`。 |
| Invalid model output | 在 normalization 阶段拒绝；不进入 act；audit 写 `invalid_candidate`。 |
| Fact conflict | FactCore veto；audit 写 `fact_veto`。 |
| Policy violation | reject 或 downgrade；audit 写 `policy_rejected` / `downgraded`。 |
| Execution infeasible | 选择 fallback path 或 `no_action`；audit 写 `feasibility_rejected`。 |
| ESM rejection | 不改写成成功；重新规划或 `no_action`；audit 写 `esm_rejected`。 |
| Character ignored impulse | 当作自然反馈；不强制角色；audit 写 `character_ignored`。 |
| Queue overload | 保留 P0/P1，降级 P2，丢弃或延迟 P3；audit 写 `load_shed` / `delayed`。 |

## 测试与验收

### Model / Schema Tests

- goal stack
- state snapshot
- intervention candidate
- intervention decision
- audit record

### Loop Unit Tests

- event batch -> state update
- state -> candidate generation
- candidate -> policy decision
- decision -> dispatch event
- result event -> audit correction

### Boundary Tests

- LLM 不能 publish event。
- 司命不能写 world fact success。
- `environment_request` 成功只能来自 ESM。
- Character input 不能强制 belief 或 dialogue。
- Visual path 只能引用 established fact。

### Replay Tests

- 同一事件链得到同类 decision。
- `no_action` 也有 audit。
- late result 只追加 correction。
- duplicate dispatch 被抑制。

### Load / Priority Tests

- P0 不被 P2 阻塞。
- P3 可以丢弃。
- LLM timeout 不阻塞 FactCore。
- 并发事件保持确定性 ordering。

### Narrative Scenario Tests

- information monopoly -> `fact_reveal` / `opportunity`
- participation starvation -> `opportunity`
- private channel lock -> `environment_request` / `opportunity`
- suspicion runaway -> low `impulse` / `fact_reveal`
- balanced state -> `no_action`

## 验收标准

完整司命 Agent Loop 架构成立时，系统应能证明：

1. 持续消费有权限消费的 authority events。
2. 维护可查询的 runtime state。
3. 基于 goal stack 和当前状态生成 candidates。
4. 每个 candidate 都经过 fact、policy、feasibility、audit 护栏。
5. 只通过高层事件影响 Character、ESM、VisualFact、L3。
6. 能处理 rejection、timeout、no-action、duplicate、late-result。
7. 能 replay 为什么行动、为什么不行动。
8. 未实现子系统有稳定端口，不需要重写主 loop。

## 实施备注

- 第一份 implementation plan 不应尝试一次实现完整未来态。
- `SimingOrchestrator`、`GoalStack`、`ObservePipeline`、`FactCorePort`、`BalanceSystemPort`、`ModelRouterPort`、`PolicyGuard`、`ExecutionFeasibilityPort`、`InterventionExecutorPort`、`AuditReplayPort` 应作为第一阶段主骨架。
- `KnowledgeGraphPort`、`ConflictGeneratorPort`、specialist sub-agents、P0-P3 distributed scheduling、`LongTermMemoryPort` 应先定义稳定端口，即使最初由 deterministic / stub 实现支撑。
- 当前已经实现的 LLM route router 应归入 `ModelRouterPort`。
- 现有 Phase 1 工程切片文档负责约束实现安全；本 spec 是更高层的司命 Agent Loop 架构蓝图。
