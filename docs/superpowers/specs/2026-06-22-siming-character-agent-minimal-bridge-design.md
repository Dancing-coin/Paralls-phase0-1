# 司命与角色智能体最小双向闭环对接设计

Status: approved

## 问题

当前项目已经有可运行的角色智能体主链，也已经存在 `siming_output -> CharacterAgentRuntime.ingest_siming_output()` 的兼容入口。

但按照 `D:\Paralls\docs` 的主设计文档，正式结构不应把这条直连链视为最终架构。上游设计要求的是：

- 司命是 `L2` 平行运行时核心，不是角色控制器
- 角色智能体不是司命下属执行脚本
- 司命只发高层催化消息，不发低层动作命令
- 角色通过自己的 `L2 / L3 / L4` 承接司命输入
- 角色只把结构化、可回放的外部结果回流给司命

因此，这次设计的核心不是“重写角色智能体”，而是把现有角色智能体接到司命主链上，同时保持：

- 对上符合权威事件总线和 `Per-Character` 输入边界
- 对内尽量复用现有 `CharacterAgentRuntime`

## 目标

- 让司命能以正式高层消息影响角色智能体
- 让角色执行与结算结果能回流给司命下一轮观察
- 不重写角色智能体现有 `L1 / L2 / L3 / L4`
- 不让司命直接调用角色内部推理层
- 不让角色直接订阅全局原始事实流
- 为后续把兼容入口替换成正式私有输入对象预留稳定位置

## 非目标

- 不重写角色智能体整体运行时结构
- 不把司命变成角色低层动作控制器
- 不把司命全局知识图谱真值直接喂给角色
- 不把玩家接管模式改成自动执行模式
- 不在本设计中重写 `ESM` 结算链
- 不在本设计中引入完整群体模拟执行层

## 上游依据

主依据来自 `D:\Paralls\docs` 中以下文档：

- `docs/phase1/core/01-运行时核心/司命设计文档.md`
- `docs/phase1/core/01-运行时核心/角色智能体设计文档.md`
- `docs/phase1/core/01-运行时核心/事件总线与感知链路设计.md`
- `docs/phase1/core/01-运行时核心/司命/08-司命与角色智能体协作协议.md`
- `docs/phase1/core/01-运行时核心/角色智能体/17-司命与角色智能体协作协议.md`
- `docs/phase1/core/01-运行时核心/角色智能体/19-角色智能体与事件总线契约.md`
- `docs/phase1/core/01-运行时核心/事件总线/05-事件信封与字段分层规范.md`
- `docs/consolidation/12-运行时四核边界一致性审计-司命-事件总线-角色智能体-ESM.md`

说明：

- `D:\Paralls\docs` 路径下未发现 `司命/19-司命接入事件总线后端设计.md`
- 因此本设计的 canonical 信封和字段分层，以 `事件总线/05` 和 `角色智能体/19` 为准
- 若上游旧稿仍残留 `world_ts / producer / source_actor_id / target_actor_ids` 一类字段，本设计不采用

## 设计原则

### 1. 总线优先

司命与角色智能体的正式协作面应是权威事件总线，而不是 `main.py` 中的临时直连链。

### 2. 兼容优先

角色智能体内部现有 `ingest_siming_output(payload)` 保留，但其定位调整为：

> 角色接收司命高层输入的兼容入口

而不是：

> 司命直控角色的最终正式入口

### 3. 私有输入转换

司命输出必须先转成“该角色有资格收到的输入对象”，再进入角色 `L2 / L3 / L4`。

补充约束：

- 在架构归属上，`SimingCharacterDispatchAdapter` 属于角色私有输入编译链的特例分支
- 它不是独立于角色感知链之外的长期旁路输入系统
- 第一阶段仅在物理落点上复用 `ingest_siming_output(payload)` 做兼容承接

### 4. 双通道回流

角色回流要同时覆盖：

- 公共世界可见结果
- 受限审计面可见、默认不进入公共业务总线的承接摘要

### 5. 公共层与本地层分离

公共信封、司命高层消息、角色本地运行态三层必须分开，不能互相污染。

## 总体结构

```text
Authority Event Bus
-> SimingEventConsumer
-> SimingRuntime
-> siming.impulse / siming.opportunity / siming.fact_reveal
-> SimingCharacterDispatchAdapter
-> CharacterAgentRuntime.ingest_siming_output(...)
-> Character L2 / L3 / L4
-> CharacterOutcomePublisher
-> Authority Event Bus
-> SimingRuntime next tick
```

这条链路表达的是：

- 司命在总线侧发高层催化
- adapter 在角色侧把总线消息转成私有输入
- 角色自己决定是否接住
- 结果再通过总线回到司命

## 组件边界

### `SimingEventConsumer`

职责：

- 从权威事件总线消费司命有资格看到的原始/结构化事件
- 对输入事件做基础 schema 校验
- 把总线事件转换成司命运行时输入对象

不负责：

- 角色输入编译
- 角色私有过滤
- 角色执行控制

### `SimingRuntime`

职责：

- 执行事实校验、局势评估、故事线评估与高层催化决策
- 产出 `impulse / opportunity / fact_reveal`

不负责：

- 角色内部理解与规划
- 直接生成低层动作
- 直接写世界成功事实

### `SimingCharacterDispatchAdapter`

职责：

- 接收 `siming.*` 总线事件
- 按 `routing.target_ids` 和目标 actor 逐角色 fan-out
- 为每个 actor 生成单独的角色私有输入实例
- 将司命高层消息转换为当前角色 runtime 能消费的兼容 payload
- 调用现有 `CharacterAgentRuntime.ingest_siming_output(payload)`
- 在投递时执行合法性检查

架构定位：

- 输出在类型归属上属于角色正式输入族中的 `SimingHighLevelMessage`
- 它不是原始世界感知链上的 `CharacterPerceivedEvent`
- 第一阶段只是在运行时落点上复用现有 `ingest_siming_output(payload)`

这是本设计的关键边界层。

它的存在使系统可以同时满足：

- 上游“总线原生 + 角色私有输入”的结构要求
- 当前仓库“角色 runtime 已有兼容入口”的现实条件

### `CharacterAgentRuntime`

职责：

- 保持现有 `L1 / L2 / L3 / L4` 承接链
- 对司命输入做角色化解释、候选调整、过滤和执行规划
- 在 `agent_full_auto` 下产出执行命令
- 在 `player_priority_assisted` 下产出建议而不是自动执行

不负责：

- 直接订阅全局原始事实流
- 解释司命全局知识图谱真值

### `CharacterOutcomePublisher`

职责：

- 位于 `CharacterAgentRuntime` 外部
- 将角色侧外化结果写回总线
- 为 replay / audit 生成受限承接摘要
- 关联 `ESM` / 会话链产生的权威结算结果

不负责：

- 重复生产 `world_result`
- 重复生产 `constraint_result`
- 重复生产 `conversation_resolution`
- 暴露角色完整 chain-of-thought
- 暴露角色私有心理真值

说明：

- 角色可以回写“我做了什么”
- 不能回写“世界最终成立了什么”或“会话最终确认了什么”

## 消息分层

### 第 1 层：`AuthorityEvent` 公共信封

canonical 字段采用：

- `event_id`
- `event_type`
- `producer_ts`
- `room_id`
- `scene_id`
- `zone_id`
- `source`
- `routing`
- `priority`
- `ttl`
- `durability`
- `causation_id`
- `correlation_id`
- `payload`

`source` 采用：

- `source.layer`
- `source.system`
- `source.actor_id`
- `source.object_id` 可选

`routing` 采用：

- `routing.audience_mode`
- `routing.routing_mode`
- `routing.dialog_group_id` 可选
- `routing.target_ids` 可选

本设计不采用旧字段：

- `producer`
- `source_actor_id`
- `target_actor_ids`
- `world_ts` 作为公共信封字段

### 第 2 层：司命高层 dispatch 消息

正式消息类型固定为：

- `siming.impulse`
- `siming.opportunity`
- `siming.fact_reveal`

本 spec 的作用域只覆盖 `character_input_path`。

不覆盖：

- `environment_change_path`
- `visual_fact_path`
- `l3_highlight_path`
- `siming.environment_request`
- `siming.visual_observability_request`
- `siming.presentation_highlight_request`

建议最小 `payload` 字段：

- `message_id`
- `intervention_band`
- `target_scope`
- `reason_tag`
- `strength`
- `ttl`
- `fact_ref` 或 `established_fact_ref`
- `attention_target`
- `presentation_hint` 可选
- `pressure_hint` 可选
- `world_ts` 可选，仅留在 payload / 领域对象
- `sim_tick_ts` 可选，仅留在 payload / 领域对象

其中 `fact_reveal` 只允许表达“事实接入权限变化”，不允许表达“直接给角色结论”。

允许：

- 已成立事实的可接触引用
- 已存在信息项的接入窗口
- 角色通过当前催化合法接触到的信息

不允许：

- 司命内部公平判断
- 高阶知识图谱全局真值
- 角色最终结论
- `you_now_believe_X`
- `you_should_suspect_Y`

### 第 3 层：角色兼容输入对象

为了兼容当前仓库实现，adapter 可继续生成现有 runtime 已支持的输入字段，例如：

- `delivery_id`
- `target_actor_id`
- `target_object_id`
- `target_environment_id`
- `presentation_hint`
- `producer_ts`
- `causation_id`
- `correlation_id`

设计原则是：

- 对外使用 canonical `AuthorityEvent`
- 对内保留兼容 payload
- 未来若角色输入合同升级，只替换 adapter，不动司命主链与角色心智主链

其中：

- `message_id` 标识原始司命高层消息
- `delivery_id` 标识某次 fan-out 后落到某个角色的私有输入实例
- 多目标分发时，必须为每个 actor 生成独立 `delivery_id`

## 角色本地状态边界

以下内容不得进入公共信封，也不应作为司命发给角色的真值：

- `privacy_pressure`
- `heard_from_ts`
- `member_from_ts`
- `primary_conversation_id`
- `speech_entitlement`
- `attention_focus_in_conversation`
- 角色私有怀疑值
- 角色内心独白
- 完整候选行动列表
- 未过滤 chain-of-thought

这些内容属于角色本地运行态、记忆或调试面，不属于公共总线层。

## 双向回流闭环

### 通道 A：结构化外化结果通道

只回写角色侧真正外化的结构化结果：

- `SpeechActPublished`
- `ActionRequestIssued`
- `InformationShareIssued`
- `SocialSignalPublished`
- `AutonomyModeChanged`

司命应基于这些对象判断：

- 角色是否真正接住了催化
- 是否形成了外部可见行为
- 后续是否引出了世界或会话层结算

补充约束：

- 进入总线不等于全局公开
- `SpeechActPublished`
- `InformationShareIssued`
- `SocialSignalPublished`

都必须继续受 `routing.audience_mode / routing.dialog_group_id / routing.target_ids` 约束

### 通道 B：受限审计结果通道

只写入调试、审计、工作台或受限内部审计流，不作为公共业务广播：

- `InterpretationSummary`
- `BeliefAffectDeltaSummary`
- `CandidateShiftSummary`
- `FilterDecisionSummary`
- `IntentCommitted`
- `IntentRejected`
- `IntentDeferred`
- `SuggestedOnly`
- `rejected_by_filter`
- `blocked_by_world_constraint`

这条链用来回答：

- 角色为什么没接住
- 玩家接管下是否只生成了建议
- 是角色拒绝，还是 `ESM` 拒绝，还是环境约束拒绝

默认规则：

- 司命主业务判断默认不依赖 `IntentCommitted`
- 司命默认看“做没做出来”
- `IntentCommitted` 属于受限审计对象，而不是默认公共结果对象

### 闭环判定规则

司命不能把“消息已发出”视为“干预已生效”。

正式闭环应按以下顺序认定：

```text
siming message emitted
-> role interpretation / filter trace
-> committed or rejected outcome
-> public action / speech / share event
-> ESM or conversation settlement
-> Siming next tick re-evaluates
```

### 特殊情况

#### `player_priority_assisted`

玩家接管模式下：

- 司命输入只应转成 suggestion / risk / impulse hint
- 不应直接触发自动执行
- 只有玩家后续真实执行，才进入公共结果通道

#### `ESM` 拒绝

`ESM` 拒绝代表：

- 角色愿意做
- 但世界不允许

它应通过 `constraint_result` 回流给司命，而不是被误判为“角色没接住”。

#### 无动作

无动作不能伪装成什么都没发生。

至少应在本地 audit / replay 通道中留下：

- `rejected`
- `deferred`
- `suggested_only`

## 关联主键

整条链至少要稳定传递以下关联键：

- `message_id`
- `delivery_id`
- `event_id`
- `correlation_id`
- `causation_id`

它们分别回答：

- 这是哪条司命消息
- 这是哪次逐角色投递实例
- 这是哪次具体事件
- 这条链属于哪次整体影响链
- 这次结果直接由谁触发

## 合法性检查分层

### `SimingRuntime`

负责业务层合法性：

- 这条消息是否应发出
- 这条 `fact_reveal` 是否引用合法事实
- 这条 `opportunity` 是否确有窗口
- 目标 actor 集合与 `reason_tag` 是否合理

### `SimingCharacterDispatchAdapter`

负责投递时合法性：

- `routing.target_ids` 是否仍可落到该 actor
- `ttl` 是否过期
- actor 当前是否仍支持接收该类消息
- fan-out 后是否能成功实例化单角色输入
- 失败时记录 `expired / unroutable / target_unavailable`

### `CharacterAgentRuntime`

负责角色承接合法性：

- 消息合法送达后，角色是否接受
- 如何解释、过滤、拒绝或建议化

不负责：

- 兜底总线分发错误
- 兜底过期投递错误

## 最小落地策略

### 第一阶段保留

保留当前角色智能体内部主链不动：

- `CharacterAgentRuntime`
- `ingest_siming_output(payload)`
- 现有 `L1 / L2 / L3 / L4`
- `agent_full_auto` 与 `player_priority_assisted` 分流
- 现有 `character_agent_execution / world_result / dialogue_response` 下游链

### 第一阶段新增

只新增总线外侧的薄层：

1. `SimingEventConsumer`
2. `SimingCharacterDispatchAdapter`
3. `CharacterOutcomePublisher`

### 第一阶段替换

当前仓库中的：

- `siming_output -> ingest_siming_output()`
- `_insert_character_agent_execution_after_siming(...)`

可以继续保留行为兼容，但在架构定位上应降级为：

- 过渡编排钩子
- 兼容路径

而不是长期 canonical 协作面。

过渡钩子只允许：

- 维持现有输出顺序
- 承担兼容层 envelope 转发
- 在迁移阶段挂接 adapter 结果

过渡钩子不允许：

- 新增司命业务判断
- 新增角色筛选逻辑
- 决定角色是否执行
- 新增世界结算逻辑
- 维护长期 canonical schema

### 第二阶段演进位

后续若角色智能体切换到正式私有输入事件合同：

- 只替换 `SimingCharacterDispatchAdapter`
- 不改 `SimingRuntime`
- 不改角色内部 `L2 / L3 / L4`

这就是本设计避免后续推倒重来的核心策略。

## 验收口径

本设计的第一阶段最小验收应覆盖：

1. 司命能发出 canonical `siming.*` 总线事件
2. adapter 能把它转成角色兼容输入
3. `agent_full_auto` 角色仍经自身 `L2 / L3 / L4` 产出执行
4. `player_priority_assisted` 角色只产出 suggestion，不自动执行
5. 角色执行、拒绝、建议、结算结果能重新回流
6. 司命下一轮能区分：
   - 已送达未承接
   - 已承接已外化
   - `ESM` 拒绝
   - 玩家未采纳建议
7. 公共信封中不出现：
   - `world_ts`
   - 角色私有运行态字段
   - chain-of-thought
8. adapter 验证的不只是“送达”，还包括语义不降级：
   - `impulse` 不得降级为低层动作命令
   - `fact_reveal` 不得降级为角色最终结论
   - 角色 runtime 看到的仍然是输入材料，而不是已决定结果

## 风险与后续专题

当前仍需单独专题化的后续问题：

- 多目标 actor fan-out 时的 adapter 分发策略
- `siming.*` 与 `Per-Character` 正式输入对象的最终 schema 收口
- 玩家接管态 suggestion / prompt 的工作台呈现
- 角色本地 audit 摘要与公共 replay 的联跳协议
- `ESM` 失败码、约束码与司命结果解释的统一表

这些问题不阻塞第一阶段最小闭环，但必须在进入正式实现计划时列成独立任务。

## 一句话收束

这次对接的正确方向，不是“让司命直接接管已经存在的角色智能体”，而是：

> 保持司命走权威总线、保持角色走自己的心智链，在两者之间增加一个把高层催化消息转换为角色私有输入的适配层，用兼容迁移的方式做出最小双向闭环。
