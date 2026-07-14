# 角色心智核心完成状态

状态: `current-truth`

更新时间: `2026-07-13`

## 这份文档回答什么

这份文档只回答两件事：

1. 现在仓库里所谓“完整角色心智核心完成”到底指什么。
2. 当前智能体已经实现到了什么程度，哪些是真的已经完成，哪些还没有。

这份文档是中文状态说明。

设计总定义仍以：

- `docs/superpowers/specs/2026-06-29-complete-character-mind-core-design.md`

为最高设计真值。

## 现在的“完整”到底是什么意思

这里的“完整”不是指整个终局产品全部完成。

这里的“完整”特指：

- **角色心智核心已经完成**

它的边界是：

- `L1` 感知
- 长期人格/身份档案
- 五池记忆
- dynamic state
- `L2` 理解与认知更新
- `L3` 目标系统与规划
- 控制仲裁
- 观测、追踪、验证、回放
- 面向未来完整具身执行的 `L4` 契约

它不等于：

- 最终产品全部完成
- 最终重执行层全部完成
- 最终动画/绑定/表情/具身系统全部完成
- 最终多场景长期社会运行全部完成

所以当前准确说法是：

- **角色心智核心完成**
- **整机终局产品未完成**

## 现在可以宣称 100% 的范围

现在可以宣称 100% 的范围是：

- 这个仓库里定义的“完整角色心智核心”

不可以宣称 100% 的范围是：

- 整个终局角色智能体产品
- 完整最终具身生命体

## 完整角色心智核心的完成条件

在当前仓库里，只有当下面这些条件同时成立时，才算“角色心智核心完成”。

### 1. 长期角色核心稳定存在

角色有稳定的长期档案真值，并与短期运行态分离。

至少包括：

- identity core
- origin seed
- life memory backbone
- virtue/value layer
- `personality_layer.big_five`
- `personality_layer.facets`
- legacy `trait_vector_layer` migration input
- generated `personality_projection`
- capability/constraint layer
- style/expression bias layer
- conversation personality layer
- `need_hierarchy_layer`
- `temperament_response_layer`

并且继续明确分层：

- authored profile truth 仍是长期角色主档案
- `long_term_personality_drift_layer` 只是被系统承认的长期沉淀层
- 运行时即时状态不能反向伪装成 authored profile truth
- 行为消费面使用 `personality_projection`，不把 Big Five、legacy traits 和
  conversation/temperament raw overlap 并列加权

### 2. `L1` 是完整的角色私有感知入口

不是只接一个事件壳，而是有角色私有世界快照。

覆盖：

- 视觉
- 听觉
- 气味
- 热/氛围
- 触觉/接近
- 自身体感
- Siming 对注意/警觉/分心的高层压力

并且保留：

- clarity
- certainty
- anomaly
- unresolved signal
- attention target
- recent world changes
- recent constraints

### 3. 五池记忆真实存在

必须同时存在：

1. Event Memory
2. Observation Memory
3. Knowledge Memory
4. Social Memory
5. Higher-Order Memory

其中 Higher-Order Memory 是“完整心智核心”的强制条件，不是可选增强。

### 4. dynamic state 是独立一层

dynamic state 不能被糊进别的层里。

当前至少包括两层运行态：

- 独立的 `NeedTensionState`
- 仍然独立存在的 `CharacterDynamicState`

其中 `CharacterDynamicState` 当前按三组语义组织：

- affect group
- tension group
- motivation group

覆盖例如：

- vigilance
- distraction
- affect valence
- stress load
- social pressure
- masking pressure
- motivation stack
- unresolved conflicts

### 5. `L2` 是真实认知更新层

`L2` 不是只出一段总结文本。

它必须能产出并写回：

- belief deltas
- social deltas
- higher-order deltas
- `dynamic_state_delta`
- goal hints
- reasoning trace summary

而且它要统一处理：

- social evidence
- world evidence
- body evidence
- Siming pressure evidence

并且现在这条链已经更明确：

- `L2 -> dynamic_state_delta`
- `dynamic_state_delta -> runtime dynamic state writeback`
- `runtime state / outcome evidence -> long-term drift candidate chain`
- 长期候选只有经过 gate 才能沉淀进 `long_term_personality_drift_layer`

### 6. 目标系统是正式一层

目标系统必须包含：

- long-term goal
- mid-term strategy
- immediate goal
- supporting goals
- blockers
- goal sources

并且运行时必须保存：

- active goal frame
- current goal state
- previous state
- history tail
- transition kind
- transition reason tags
- reorganization
- repair/recovery semantics

### 7. `L3` 是真实规划层

`L3` 不只是 demo 反应器。

它必须有：

- goal activator
- candidate generation
- constraint projection
- triple filter
- priority ranking
- intent selection

并且候选动作空间必须足够宽，不只会“看一下/说一句”。

### 8. 控制模式是同一种角色物种

当前角色不是“AI 角色”和“玩家壳”两套物种。

而是同一个角色运行时，按控制模式分流：

- `agent_full_auto`
- `player_priority_assisted`
- `away_conservative_takeover`
- `scripted_override`

### 9. 执行层可以轻，但 `L4` 契约必须完整

执行下游现在可以不做重实现。

但上游必须已经能给出完整 `L4` 契约，至少覆盖：

- speech
- face
- body
- social-spatial
- physiology

### 10. 不能破坏现有 smoke path

心智核心完成不能以破坏当前可运行验证链为代价。

至少要保住：

- backend full test
- character agent execution verifier
- observatory verifier
- strict `Phase 0` verifier

## 当前智能体到底是什么

当前智能体不是“一个 prompt 套一个模型”的薄壳。

它现在是一个 **可运行的角色心智运行时**。

它的真实链路是：

```text
CharacterPerceivedEvent / SelfBodyPerceivedEvent / siming_output
-> CharacterAgentRuntime
-> L1 private snapshot
-> timeline + five-pool memory + dynamic state
-> L2 interpretation / cognition update
-> L3 planning / goal system / triple filter
-> L4 execution plan
-> websocket delivery
-> CharacterReplica shared actor ingress
-> KnightRoleSkin light embodiment
```

也就是说，它现在已经能做到：

- 感知事实
- 用角色私有视角理解事实
- 形成 belief/social/higher-order/dynamic-state 更新
- 激活当前目标框架
- 规划当前动作和建议
- 保持跨回合连续性
- 把当前心智状态暴露到 observability 和 director observatory
- 把执行结果继续写回 memory / timeline / state

## 分层实现现状

### 长期档案

已完成为角色长期真值层的一部分。

当前已进入 runtime 消费，不再只是静态摆设。

当前已明确包含：

- `personality_layer.big_five`
- `personality_layer.facets`
- legacy `trait_vector_layer`，仅作为迁移/兼容输入
- `personality_projection`，作为行为面对外的去重人格投影
- `need_hierarchy_layer`
- `temperament_response_layer`

并继续与下列层分开：

- `NeedTensionState`
- `CharacterDynamicState`
- `long_term_personality_drift_layer`

人格边界：

- Big Five/facets 是新的低层人格基础。
- 旧 `trait_vector_layer` 继续加载，以支持迁移期 profile 兼容，但不作为新
  L2/L3/L4 scoring 的 raw behavior input。
- `PersonalityProjectionResolver` 负责把人格、values、temperament、
  conversation style、capability context 和 legacy hints 投影成
  `social_approach_bias`、`empathic_attunement`、`conflict_deescalation_bias`
  等去重偏置。
- duplicate-weight guard 要求行为层不要把 `agreeableness`、`empathy`、
  `mediation_tendency` 等重叠字段重复相加。
- MBTI 不作为数值运行基础；当前不实现 MBTI 数值层。

CharacterDossier runtime connection 状态：

- `CharacterDossier` schema wrapper 已实现；它包住现有 `CharacterProfile`，
  并保留 legacy `CharacterProfile` YAML loader 兼容路径。
- 已实现 `identity_profile`、`embodiment_profile`、`authority_profile`、
  `private_truth_profile`、`relationship_seed_profile`、
  `capability_seed_profile` 的 first-pass runtime contracts。
- 已实现 visibility-filtered dossier projection；`L2/L3/L4` 只消费过滤后
  summaries / constraints，不消费 raw dossier、raw secret content 或
  `author_only` truth。
- 已实现 shadow `CharacterMindFrame` dossier cards：
  `identity_context`、`embodiment_context`、`authority_context`、
  `private_truth_context`、`relationship_seed_context`、
  `capability_seed_affordance`。
- 已实现 L2/L3/L4 view-level dossier summaries，保持 additive/shadow，不改
  现有行为选择。
- 已实现 relationship/capability seed candidate bundle；它只输出
  initialization candidates，不写 runtime memory store、relationship graph
  或 character skill state。
- 已实现 dossier hot reload invalidation contract；它只返回 projection
  invalidations 和 new dossier instance，不覆盖 `NeedTensionState`、
  `CharacterDynamicState`、`BodyRuntimeState`、goal、memory、relationship
  graph 或 skill state。

仍留给后续独立 spec：

- 完整 `BodyRuntimeState` 与身体运行态结算。
- `RelationshipGraph` 存储、图算法与 read model。
- `AbilityGraph` 与完整 `CharacterSkillSystem` 集成。
- runtime hot reload service / file watcher / authoring tools。
- subjective belief、other-actor belief 与 player-facing reveal policy。
- authoring validation 与 legacy profile migration tooling。

### `L1` 感知层

已完成为真实角色私有感知层。

当前支持：

- visible / audible / unresolved signals
- recent world changes
- recent constraints
- self-body hints
- vigilance / distraction
- olfactory / thermal / tactile 进入角色私有快照

### 五池记忆

已完成。

当前有 typed 记录对象与 typed bundle：

- `CharacterEventMemoryRecord`
- `CharacterObservationMemoryRecord`
- `CharacterKnowledgeMemoryRecord`
- `CharacterSocialMemoryRecord`
- `CharacterHigherOrderMemoryRecord`
- `CharacterMemoryRecordBundle`

而且这些不再只是旁路 API，已经进入：

- `L2`
- `L3`
- observability

### dynamic state

已完成为独立运行态层。

当前有：

- typed model
- `NeedTensionState` typed model
- store
- merge semantics
- runtime exposure
- working-memory integration
- observability carry-through

当前语义也已经拆清：

- `NeedTensionState` 保存需求压力、近期满足/受挫趋势与主导需求
- `CharacterDynamicState` 拆为 affect / tension / motivation 三组
- `affect_state` 当前覆盖 14 个即时情绪维度：`fear`、`anger`、`shame`、`sadness`、`relief`、`curiosity`、`affection`、`joy`、`calm`、`trust`、`gratitude`、`pride`、`confidence`、`hope`
- 压力不是情绪字段：需求压力留在 `NeedTensionState`，运行时/慢性张力留在 `tension_state`
- 长期 drift 不直接写回 authored profile truth

### 分层心智因子投影

当前角色心智核心仍以 `L1 -> L2 -> L3 -> L4` 为主链。

`CharacterMindFrame` 是新增的 shadow contract，用于把长期档案、记忆证据、
运行态、可供性、认知工作区和回写候选分层表达。它不是新的心智中枢，也不替代
`L2/L3`。

边界：

- authored dossier truth 由 `CharacterDossier` 表达；长期心理/行为 baseline
  仍由 nested `CharacterProfile` 表达，长期 drift 保持为独立 drift overlay /
  effective-profile 路径。
- memory evidence 仍由五池记忆表达。
- social relationship network 仍属于 social memory，可在后续图谱化投影。
- runtime state 仍由 `NeedTensionState`、`CharacterDynamicState`、goal state 和 unresolved tension 表达。
- dossier projection、`CharacterMindFrame` 当前只作为 shadow read model，
  不改变既有决策行为。

后续补全阶段：

- projection services 将 dossier/profile、memory、relationship、need、dynamic state、goal、tension 和 supervision 转成只读 cards。
- affordance adapter 只暴露 skill/action/environment/equipment/physical feasibility summaries，不暴露 skill registry。
- `MindDeltaLedger` 统一包裹 L2/L3/L4/settlement/writeback 候选，但 persistence 仍由 writeback policy 和原 store 边界决定。
- graph-backed memory 只作为 memory-evidence projection，可增强 knowledge/social/higher-order reads，不成为 cognition owner。

### `L2` 理解层

已完成为统一认知更新层。

当前不只是输出 summary，而是输出：

- belief deltas
- social deltas
- higher-order deltas
- `dynamic_state_delta`
- goal hints
- reasoning trace summary

并且 local/offline cognition 已统一进 `CharacterCognitionEngine`。

同时新增了明确的 needs/affect/drift 运行时链：

- `effective_profile = authored profile truth + long_term_personality_drift_layer`
- `NeedTensionEngine` 先更新 `NeedTensionState`
- `AffectEngine` 再导出 `dynamic_state_delta`，其中需求满足会进入 `relief/calm/trust/gratitude/pride/confidence/hope/joy` 等正面 affect
- `L2` 消费 `NeedTensionState` 与 `CharacterDynamicState`
- 长期 drift 候选链只从 runtime evidence 累积，不直接把瞬时状态写回主档案

### 目标系统

已完成。

当前已经具备：

- typed `CharacterGoalHint`
- typed `CharacterActiveGoalFrame`
- typed `CharacterGoalStateRecord`
- persisted current state
- previous state
- history tail
- transition kinds
- transition reason tags
- `repairing`
- `recovering`

### `L3` 规划层

已完成为真实规划层。

当前已经不是窄动作集，而是支持例如：

- observe
- inspect_object
- ask_probe
- share_info
- speak_public
- speak_private
- withhold
- pause
- defer
- self_protect
- follow_target
- seek_private_distance
- break_contact
- withdraw
- approach

并且 `L3` 现在真实消费：

- profile
- `personality_projection` 中的去重人格偏置
- knowledge state
- higher-order memory
- dynamic state
- active goal frame
- typed five-pool memory bundle

### 控制仲裁

已完成。

当前最关键的事实是：

- `char_c` 不是没脑子的玩家壳
- `char_c` 是 `player_priority_assisted`
- 仍然跑 `L1/L2/L3`
- 只是执行上不强行替玩家接管

### `L4` 契约与轻执行

按当前目标，已完成。

这里的“完成”是指：

- `L4` 上游契约已经足够完整
- 当前执行层仍保持轻实现
- shared actor ingress 没被破坏
- 后续重具身实现不需要重做 `L1-L3`

## 当前它不是什么

它现在还不是：

- 最终整机完成态
- 完整重具身执行系统
- 最终 FACS/SACS/Binder/Mixer 全实现
- 长期多场景社会仿真终局形态

所以不能说：

- “整个角色智能体产品已经 100% 完成”

但可以说：

- “角色心智核心已经 100% 完成”

## 当前完成证据

既有 harness 证据：

- `.harness/verification/phase0-report.md` -> `Overall: True`
- `.harness/verification/character-agent-execution-report.md` -> `overall_character_agent_execution_passed=True`
- `.harness/verification/character-director-observatory-report.md` -> `overall_character_director_observatory_passed=True`

本次 needs/affect/drift 变更的聚焦验证入口和已执行证明：

- `pytest backend/tests/test_character_profile_needs_schema.py -v`
- `pytest backend/tests/test_need_tension_engine.py -v`
- `pytest backend/tests/test_affect_engine.py -v`
- `pytest backend/tests/test_character_runtime_needs_affect_flow.py -v`
- `pytest backend/tests/test_personality_drift_gate.py -v`
- `pytest backend/tests/test_character_agent_l3_planning.py -v`
- focused suite with L3 planning coverage -> `83 passed`
- `python scripts/verification/harness.py --profile docs` -> `overall_docs_passed=True`

这意味着：

- 心智核心没有停留在设计层
- 它已经通过了当前聚焦 backend proof
- 既有 harness evidence 仍记录 runtime smoke proof
- 既有 harness evidence 仍记录 observability proof

## 最准确的一句话

现在这个仓库里的智能体，最准确的定义是：

- **完整角色心智核心**
- **轻执行层**
- **shared actor ingress 兼容**
- **可观测、可验证、可回放**

如果要再压缩成一句话，就是：

- **它已经是完整的角色心智核心实现，但还不是终局整机产品。**
