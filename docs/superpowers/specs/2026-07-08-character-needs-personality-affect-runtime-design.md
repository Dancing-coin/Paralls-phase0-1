# 角色需求层、性格展开层与情绪状态运行时设计

状态：implemented-and-verified

本文定义当前项目中“完整的人”所需的三组新增能力：

1. 结构化需求层
2. 详细性格展开层
3. 多时间尺度情绪/张力层

并给出它们与现有 `CharacterProfile`、`CharacterAgentRuntime`、`dynamic_state`
和长期人格沉淀机制之间的接口方式。

## 1. 背景

当前项目已经具备：

- 结构化角色档案：`identity_core`、`trait_vector_layer`、
  `conversation_personality_layer` 等
- 角色运行时读取档案并进入 `L2/L3`
- `dynamic_state` 运行时状态与 `dynamic_state_delta` 更新链
- working memory、unresolved tension、goal state 等配套状态

当前缺口是：

- “需求”还没有成为显式结构层
- “性格”已存在，但缺少足够细的应激/反应展开层
- “情绪状态”已有雏形，但尚未明确拆分为即时情绪、中期张力、长期沉淀
- 长期变化没有正式的人格沉淀路径

## 2. 设计目标

本设计要满足：

1. 需求层为角色运行时提供稳定的中约束，不直接压过 authority、红线、
   supervision 或显式剧情约束
2. 性格不仅表现为 trait 数值，还要表现为冲突风格、应激模式、信任动力学和表达偏置
3. 情绪状态需要和人格相关，并区分至少三种时间尺度：
   - 即时情绪
   - 中期张力
   - 长期人格沉淀
4. authored profile 继续作为角色真相源
5. 只有长期、跨场景、经证据确认的稳定变化才允许回写到档案的长期沉淀层

## 3. 非目标

本设计不包含：

- 让短期情绪直接重写 authored profile 主字段
- 用单一 LLM 隐式推断替代结构化需求/情绪模型
- 直接把“人格变化”变成完全自动、频繁、自我改写的黑箱系统
- 在本阶段改写 ESM、System L6 或 Godot 表现层的主职责

## 4. 核心原则

### 4.1 需求是中约束

需求层可以：

- 改变 L2 对事件的意义解释
- 改变 L3 对目标和策略的排序
- 改变情绪变化速度和张力积累方式

需求层不可以：

- 覆盖 authority 结算
- 覆盖红线/禁忌
- 覆盖 supervision 约束
- 在没有足够情境支持时直接决定动作

### 4.2 人格、情绪、长期变化必须分层

- 静态人格档案：角色长期稳定真相
- 即时情绪：秒到分钟级波动
- 中期张力：场景级、阶段级累积
- 长期人格沉淀：跨场景、跨多轮、经验证的稳定变化

### 4.3 authored truth 与 runtime evolution 分离

- base profile 不被短期状态直接改写
- 长期变化进入单独的 `long_term_personality_drift_layer`
- 运行时使用 `effective_profile = base profile + drift layer`

## 5. 结构化档案扩展

在现有 `CharacterProfile` 基础上新增三层。

### 5.1 `need_hierarchy_layer`

作用：

- 定义角色长期需求权重
- 定义需求受挫/满足时的敏感度
- 定义主要驱动力和满足/受挫通道

建议字段：

- `base_weights`
- `deprivation_sensitivity`
- `satisfaction_sensitivity`
- `dominant_drives`
- `satisfaction_channels`
- `frustration_channels`

### 5.2 `temperament_response_layer`

作用：

- 定义角色稳定反应风格与应激模式

建议字段：

- `baseline_temperament`
- `conflict_style`
- `defense_patterns`
- `trust_dynamics`
- `expression_bias`

### 5.3 `long_term_personality_drift_layer`

作用：

- 存储被系统承认的长期人格沉淀
- 不直接覆盖 authored 主档案层

建议字段：

- `stable_shifts`
- `reinforced_patterns`
- `weakened_patterns`
- `need_reweights`
- `trust_reweights`
- `expression_reweights`
- `drift_policy`

## 6. 运行时状态层扩展

### 6.1 `NeedTensionState`

独立于 `CharacterDynamicState`。

作用：

- 保存各需求当前压力
- 保存近期满足/受挫趋势
- 保存当前主导需求与动机堆栈

建议字段：

- `physiological_pressure`
- `safety_pressure`
- `belonging_pressure`
- `esteem_pressure`
- `self_actualization_pressure`
- `recent_satisfaction`
- `dominant_need`
- `secondary_need`
- `motivation_stack`
- `pressure_sources`

### 6.2 `CharacterDynamicState`

保留现有主字段，但语义拆成三组：

1. 即时情绪层
2. 中期张力层
3. 当前驱动力层

建议扩展：

- `affect_state`
  - `fear`
  - `anger`
  - `shame`
  - `sadness`
  - `relief`
  - `curiosity`
  - `affection`
  - `joy`
  - `calm`
  - `trust`
  - `gratitude`
  - `pride`
  - `confidence`
  - `hope`
- `tension_state`
  - `stress_load`
  - `social_pressure`
  - `masking_pressure`
  - `chronic_safety_tension`
  - `belonging_frustration`
  - `esteem_wound_load`
  - `relationship_fatigue`
- `motivation_state`
  - `dominant_need`
  - `secondary_need`
  - `motivation_stack`
  - `active_need_pressures`
  - `unresolved_conflicts`

`affect_state` 表示即时情绪，不承载压力本体。压力和长期张力仍分别留在
`NeedTensionState` 与 `tension_state`；`recent_satisfaction` 只能通过
`AffectEngine` 派生 `relief/calm/trust/gratitude/pride/confidence/hope/joy`
等正面情绪 delta，再进入 runtime `CharacterDynamicState`。

### 6.3 长期候选层

建议新增运行时记录，而不是直接进入 profile：

- `DriftCandidateRecord`

它用来累计：

- 哪类需求长期受压
- 哪类情绪反应长期稳定
- 哪类应激模式不断被强化
- 哪类关系偏置持续变化

## 7. 运行时模块设计

### 7.1 `EffectiveProfileResolver`

职责：

- 读取 base profile
- 叠加 `long_term_personality_drift_layer`
- 输出 `effective_profile`

### 7.2 `NeedTensionEngine`

职责：

- 根据 `effective_profile`、当前事件、记忆、关系和目标状态
- 计算需求压力变化

输出：

- `NeedTensionDelta`
- `MotivationStack`
- `NeedPressureSummary`

### 7.3 `AffectEngine`

职责：

- 根据 `effective_profile`、`NeedTensionState`、当前解释前体
- 生成即时情绪和中期张力变化

输出：

- `AffectStateDelta`
- `DynamicStateDelta`

### 7.4 `L2Reasoner`

新的定位：

- 不再独自承担全部人格推断
- 作为解释协调器，消费：
  - `effective_profile`
  - `NeedTensionState`
  - `CharacterDynamicState`
  - 当前事件
  - memory / tensions / goal state

输出：

- `CharacterInterpretation`
- `dynamic_state_delta`
- `goal_hints`
- `reasoning_trace_summary`

### 7.5 `L3Planner`

消费：

- `CharacterInterpretation`
- `NeedTensionState`
- `CharacterDynamicState`
- goal / supervision / unresolved tensions

作用：

- 做策略排序
- 输出意图决策
- 保持“需求为中约束”

### 7.6 `DriftAccumulator`

职责：

- 累计长期人格变化候选
- 不直接晋升

### 7.7 `DriftPromotionGate`

职责：

- 决定哪些候选可以沉淀为 `long_term_personality_drift_layer`

## 8. 主状态流

```text
base profile
+ long_term drift
-> effective profile
-> need tension engine
-> affect engine
-> L2 interpretation
-> L3 planning
-> execution
```

## 9. 回写流

```text
L2 / L3 / outcome
-> dynamic_state_store
-> need_tension_store
-> unresolved_tension_store
-> drift_accumulator
-> drift_promotion_gate
-> long_term_personality_drift_layer
```

## 10. 回写规则

### 10.1 即时层

- 不回写 profile
- 只写 runtime `dynamic_state`

### 10.2 中期层

- 不回写 profile
- 写：
  - `dynamic_state`
  - `need_tension_state`
  - `unresolved_tensions`

### 10.3 长期层

只有满足以下条件才允许沉淀：

- 跨多个 scene
- 累积足够多确认事件
- 具有足够长时间跨度
- 与 authored 红线不冲突
- 不是一次性极端事件造成

### 10.4 回写目标

长期变化只进入：

- `long_term_personality_drift_layer`

不直接覆盖：

- `trait_vector_layer`
- `conversation_personality_layer`
- `virtue_value_layer`

## 11. 与现有代码的结合方式

### 11.1 已有基础

当前项目已经具备：

- `CharacterProfileRegistry`
- `CharacterAgentRuntime`
- `CharacterDynamicStateStore`
- L2/L3/L4 推理规划链
- working memory / unresolved tension / goal state

### 11.2 推荐接入顺序

1. 扩 `CharacterProfile` schema
2. 扩 `CharacterDynamicState` schema
3. 新增 `NeedTensionState`
4. 接入 `NeedTensionEngine`
5. 接入 `AffectEngine`
6. 让 L2/L3 消费新状态
7. 新增 `DriftAccumulator`
8. 最后启用 `DriftPromotionGate`

## 12. 分阶段实施建议

### Phase 1：Schema 扩展

- 扩 `CharacterProfile`
- 扩 `CharacterDynamicState`
- 新增 `NeedTensionState`

### Phase 2：需求张力接线

- 接入 `NeedTensionEngine`
- 接入 `NeedTensionStore`

### Phase 3：情绪与张力接线

- 接入 `AffectEngine`
- 区分即时情绪与中期张力

### Phase 4：L2/L3 消费升级

- 让解释层和规划层真正使用需求/情绪状态

### Phase 5：长期候选累计

- 接入 `DriftAccumulator`
- 只记录，不晋升

### Phase 6：严格长期沉淀

- 接入 `DriftPromotionGate`
- 启用 `long_term_personality_drift_layer`

## 13. 风险与约束

### 风险 1：L2 继续过胖

如果不显式引入 `NeedTensionEngine` / `AffectEngine`，则 L2 会继续膨胀为
“人格、需求、情绪、解释”的单一巨型模块。

### 风险 2：状态与档案混淆

如果短期和中期状态直接写回 profile，会破坏 authored truth。

### 风险 3：长期沉淀过快

如果不设置严格晋升闸门，会把短期波动误判为人格改变。

## 14. 推荐方案

推荐采用：

- 结构化档案扩展
- 显式 `NeedTensionEngine`
- 显式 `AffectEngine`
- 独立 `DriftAccumulator` 与 `DriftPromotionGate`

不推荐：

- 仅靠 prompt 隐式推断人格与情绪
- 让长期变化直接覆盖 authored profile 主字段
- 把需求、情绪、长期沉淀混进一个 state 层

## 15. 当前结论

当前项目已经具备承载“完整的人”的基础骨架，但仍缺少：

- 结构化需求层
- 足够细的性格反应层
- 多时间尺度情绪/张力层
- 严格保守的长期人格沉淀机制

本设计的目标，是在不破坏现有角色运行时主链的前提下，把这些能力系统化接入。
