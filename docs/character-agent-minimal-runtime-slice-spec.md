# 角色智能体最小运行时切片设计

日期：`2026-06-11`

---

## 1. 文档目标

本文档不是《开本》完整角色智能体总设计的替代品。

它的目标是：

1. 在当前仓库已经跑通的 `L1 / L6 / Siming` 底座上，定义一个**最小可运行角色智能体切片**
2. 明确这个切片当前应该接什么、不该接什么
3. 让 `CharacterA / CharacterB` 开始具备真正的“角色私有理解 -> 最小意图 -> 最小具身回应”能力
4. 为未来完整角色智能体 `L1-L4` 演化保留正确边界

一句话：

**这份 spec 讨论的是“现在怎么把角色智能体接起来”，不是“现在就把角色智能体全部做完”。**

---

## 2. 名词冻结：`System L1` 与 `CharacterAgent L1` 必须区分

当前仓库里，`L1` 这个词有两种完全不同的含义。

如果不先分清，后面的 spec 很容易把“世界事实层”和“角色主观入口层”混成一层。

### 2.1 `System L1`

`System L1` 指系统级确定性空间层。

它负责：

- Godot 本地高频执行
- 玩家输入结构化
- raw fact / visual fact / spatial fact / sensory fact 生产
- backend `ESM` 权威结算
- 物体、环境、身体的物理或确定性状态变化

一句话：

**`System L1` 生产世界相关事实，并对世界是否真的发生变化负责。**

### 2.2 `CharacterAgent L1`

`CharacterAgent L1` 指角色智能体内部的感知层。

它不生产公共世界事实，也不做 `ESM` 结算。

它只负责：

- 接收已经经过私有裁剪的角色输入
- 维护角色版短时世界快照
- 为后续 `CharacterAgent L2/L3/L4` 提供主观世界入口

一句话：

**`CharacterAgent L1` 不是真实世界层，而是角色对世界的私有感知层。**

### 2.3 两者的正确关系

统一链路必须保持为：

`System L1 facts / ESM results -> System L2 candidate compilation / per-character filter -> CharacterPerceivedEvent -> CharacterAgent L1 -> CharacterAgent L2/L3/L4`

因此：

- `System L1` 在角色智能体之外
- `CharacterAgent L1` 在角色智能体之内
- 两者不是同一层，只是编号都叫 `L1`

后文如果出现不带前缀的 `L1`，都应该视为不够精确。

---

## 3. 为什么现在该开始写

当前主线已经具备几个关键前置条件：

- `System L1` 已经能稳定发出结构化事实与玩家输入
- backend `ESM` 已经能做 deterministic 结算
- `L6` authority event bus 已经成立
- `L2` Siming 已经能消费 authority 事件并回写最小催化输出
- `CharacterPerceivedEvent` / `SelfBodyPerceivedEvent` 边界已经成立
- 严格 `Phase 0` 验证已经通过

如果现在还不开始角色智能体，后续很多“角色好像有理解/有反应”的逻辑会继续堆在：

- `MainDemoController.gd`
- `CharacterService`
- `ConversationRelationService`
- `CharacterReplica.gd`

这些过渡层里。

这会导致：

- 角色主观理解和世界事实层继续混写
- 司命、角色、`ESM` 的边界越来越模糊
- 后面很难从“跑得通的 demo”进化到“可维护的角色运行时”

所以现在是合适的切入点。

---

## 4. 这份 spec 不是写什么

这份 spec 明确**不**覆盖以下内容：

- 完整人格档案系统
- 五池记忆系统
- 完整长期关系图谱
- 完整 `L1/L2/L3/L4` 角色智能体实现
- 完整多轮自主对话
- 完整 `FACS/SACS + Binder + Canonical Rig + Asset Adapter` 生产链
- 完整挂机接管系统
- 完整玩家双回路补全系统

这份 spec 只定义：

**一个最小、可运行、可验证、可渐进扩展的角色智能体 runtime slice。**

---

## 5. 上游与下游边界

### 4.1 正式上游输入

当前角色智能体只正式接收四类输入：

1. `CharacterPerceivedEvent`
2. `SelfBodyPerceivedEvent`
3. `Siming` 高层催化消息
4. world / constraint / conversation 相关结构化回写

统一输入链必须保持为：

`System L1 facts / ESM results -> Candidate Compilation -> Per-Character Filter -> Character Perceived Event -> CharacterAgent L1 -> CharacterAgent L2/L3/L4`

角色智能体默认**不直接消费全局原始事实流**。

### 4.2 正式下游输出

角色智能体当前切片只允许输出：

- 最小行为意图
- 最小对话行为
- 最小社交空间行为
- 最小具身表达计划

它不直接决定：

- 世界物理是否成立
- 交互是否成功
- 身体是否真的受伤
- 物体是否真的改变状态

这些仍由 `System L1 / ESM` 结算。

### 4.3 与司命的关系

司命是全局催化者，不是角色脑。

在当前切片里：

- 司命可以提高某件事的可观察性
- 司命可以发 attention / fact reveal 类型催化
- 司命不能直接替角色做最终行为选择

角色是否接住一条催化，必须经过自己的主观解释和最小意图选择。

### 4.4 与 `ESM` 的关系

`ESM` 决定：

- 身体发生了什么
- 环境发生了什么
- 物体发生了什么

角色智能体决定：

- 这些结果对角色意味着什么
- 角色接下来倾向做什么
- 角色会如何在具身层暴露这种变化

---

## 6. 当前主线已提供的前置能力

当前仓库已经有这些可直接复用的实现：

### `System L1`

- `raw_fact_event` 统一出口
- `player_input` 结构化输入
- visual / spatial / auditory / tactile / thermal / olfactory / physiology / role-state facts
- deterministic `ESM`

### `L6`

- `AuthorityEvent`
- `InMemoryAuthorityEventBus`
- `Phase0AuthorityEventAdapter`
- `FrontendAuthorityEventProjector`

### `角色私有边界`

- `CharacterPerceivedEvent`
- `SelfBodyPerceivedEvent`
- `CharacterPerceivedInputService`
- `ConversationRelationService`
- `CharacterRuntimeStateService`

### `Siming`

- `SimingEventPipeline`
- `SimingRuntime`
- `siming.fact_reveal`
- `siming.visual_observability_request`

### Godot 具身侧

- `CharacterReplica.gd`
- `MainDemoController.gd`
- `Phase0PlayerBridge.gd`
- 角色壳 attention / dialogue / role-state / physiology 的最小表现入口

这意味着：

当前 spec 的重点不是“发明基础设施”，而是**把角色智能体插到已有基础设施之间**。

---

## 7. 当前切片的目标角色

当前最小切片只覆盖：

- `CharacterA`
- `CharacterB`

不优先覆盖：

- 玩家主控角色 `CharacterC`

理由：

- `A / B` 是最稳定的 AI-driven 壳
- 玩家角色当前仍采用“玩家主控 + 系统补全”的过渡形态
- 如果现在就把 `C` 拉进同一个自动智能体主链，会把“玩家接管边界”问题提前放大

所以当前切片以：

**让 `A / B` 真正变成最小角色智能体**

为目标。

---

## 8. 当前切片的最小四层

这份 spec 仍沿用主项目的 `L1/L2/L3/L4` 口径，但只做最小版。

### 8.1 `CharacterAgent L1`：感知层

当前角色智能体的 `CharacterAgent L1` 不是重新做 raw fact，也不是 `ESM`，而是角色智能体内部的私有感知层。

它和 `System L1` 的关系必须明确：

- `System L1` 产生世界事实与结算结果
- `CharacterAgent L1` 只接收角色有资格收到的私有感知版本

所以 `CharacterAgent L1` 不是世界层，而是角色智能体的感知层。

输入包括：

- `CharacterPerceivedEvent`
- `SelfBodyPerceivedEvent`
- Siming 高层催化消息

它维护一个最小 `Private World Snapshot`，至少包含：

- `visible_entities`
- `audible_entities`
- `attention_targets`
- `active_candidates`
- `recent_world_changes`
- `recent_constraint_results`
- `body_state_hints`

注意：

当前第一阶段里，`audible_entities` 可以存在结构，但听觉仍可能是空的，因为 auditory 还没推进到角色私有感知链。

### 8.2 `CharacterAgent L2`：最小理解层

当前应该实现一个真正的最小 `L2 Interpreter`。

它不做大模型式全脑理解，只做最少四件事：

1. 解释：我刚收到的输入意味着什么
2. 标注：这件事是风险、机会、异常、还是普通变化
3. 归因：当前我最应该盯住谁 / 什么
4. 评估：我是不是应该产生一句最小回应或一个最小动作倾向

建议最小输出结构：

- `interpreted_summary`
- `interpretation_type`
- `salience_score`
- `ambiguity_level`
- `risk_level`
- `opportunity_level`
- `attention_target`
- `inner_prompt_candidate`

这个 `L2` 先不要求“高智商”，只要求：

- 主观
- 连续
- 不越权

### 8.3 `CharacterAgent L3`：最小意图选择层

当前只支持一小组候选行为：

- `observe_target`
- `speak_brief_response`
- `inspect_object`
- `reposition`
- `stay_silent`

最小三重过滤器仍然保留，但只做轻量实现：

1. `Persona Filter`
   当前角色像不像会做这件事的人
2. `Logic Filter`
   当前局面下这件事合不合理
3. `Gain/Loss Filter`
   做这件事值不值得

当前切片不做复杂长期目标规划，只做：

- 单步主导意图选择
- 风险和机会的最小排序

### 8.4 `CharacterAgent L4`：最小执行适配层

当前 `L4` 不重新发明一套角色执行系统，而是复用现有 Godot 具身壳接口。

它只把最小意图翻译成：

- attention 变化
- 一句最小对话回应
- 一次空间微调
- 一个 role-state / physiology 表现提示

它不直接控制世界结果，也不直接控制真实结算。

---

## 9. 当前第一阶段只支持的输入模态

第一阶段正式支持：

- Vision
- World Result
- Self Body
- Siming catalyst

第一阶段暂不正式支持：

- Audition
- Smell 的高阶主观理解
- Thermal / tactile 的复杂主观解释

原因不是这些模态不重要，而是：

- 当前主线最成熟的是视觉、世界结果和司命催化链
- 听觉目前仍冻结为 `L1-only`
- 其它模态虽然已经有事实上抛器，但还没形成真正的角色私有理解链

---

## 10. 当前第一阶段只支持的输出类型

第一阶段角色智能体只允许输出这些最小动作：

- `attention_shift`
- `brief_dialogue_response`
- `observe_object`
- `reposition_step`
- `role_state_hint`
- `physiology_hint`

第一阶段不允许直接输出：

- 复杂社交联盟动作
- 长期多步策略
- 复杂欺骗链
- 大段主动独白
- 直接世界操作结果

---

## 11. 当前仓库中的接入点

### backend 接入点

- `backend/app/services/character_perceived_input_service.py`
  - 当前私有感知暂存入口
- `backend/app/services/conversation_relation_service.py`
  - 当前候选关系与短时关系状态
- `backend/app/services/character_runtime_state_service.py`
  - 当前角色运行态投影
- `backend/app/main.py`
  - 当前 websocket / authority / runtime 组合根

### Godot 接入点

- `scripts/character/CharacterReplica.gd`
  - 角色壳表现出口
- `scripts/phase0/MainDemoController.gd`
  - 运行时调度与 demo glue
- `scripts/autoload/BackendBridge.gd`
  - backend 输入输出桥

### 当前建议新增的角色智能体运行时入口

建议新增一个角色智能体 runtime 子树，例如：

- `backend/app/services/character_agent_runtime.py`
- `backend/app/services/character_agent_l2.py`
- `backend/app/services/character_agent_l3.py`
- `backend/app/services/character_agent_l4_adapter.py`

注意：

第一阶段不要急着把它们搬进一个全新的庞大目录树里。
先让它们在现有主线中跑起来，再考虑正式归位到 `backend/app/l2/character_agent/*`。

---

## 12. 当前最小数据流

```text
System L1 Facts / WorldResult / Siming Catalyst
  |
  v
Candidate Compilation / Per-Character Filter
  |
  v
CharacterPerceivedEvent / SelfBodyPerceivedEvent
  |
  v
CharacterAgent L1 Snapshot
  |
  v
CharacterAgent L2 Interpreter
  |
  v
CharacterAgent L3 Intent Selector
  |
  v
CharacterAgent L4 Presentation Adapter
  |
  +--> CharacterReplica attention / pose / dialogue hooks
  +--> possible ActionRequestIssued back to ESM (future)
```

这条链必须严格保持：

- 角色只接收角色版世界
- 角色不直接订阅全局事实真相
- 角色不绕过 `ESM`
- 司命不代替角色定案

---

## 13. 当前切片与 `System L1` 的明确分工

### `System L1` 负责

- 事实生产
- 输入结构化
- `ESM` 结算
- authority event 进入 `L6`
- 世界结果和环境结果回写

### `CharacterAgent L1` 负责

- 私有感知事件接收
- 私有短时世界快照
- 把感知结果和短时主观上下文交给 `CharacterAgent L2`

### 明确禁止

当前角色智能体切片中，`CharacterAgent L1` 不得：

- 重新定义 raw fact
- 直接读取全局 authority event bus 原始事实真相
- 直接替代 `ESM`
- 直接发世界成功/失败结论

---

## 14. Phase 1 切片验收标准

当前最小角色智能体切片完成时，至少要证明：

1. `CharacterA/B` 能消费 `CharacterPerceivedEvent`
2. 能基于该输入生成一条最小主观解释结果
3. 能基于解释结果选出一个最小意图
4. 能把该意图翻译成至少一种当前 Godot 壳可观察输出：
   - attention
   - brief dialogue response
   - reposition
5. 不直接订阅全局 raw fact
6. 不直接决定 world result
7. `verify_phase0.py` 继续通过
8. 当前 authority / Siming / `ESM` 闭环不回退

建议第一阶段至少补三类测试：

- backend unit tests
  - 角色感知 -> 解释 -> 意图
- integration tests
  - perception event -> Godot-facing表现链
- verification audit
  - 严格证明角色没有越过边界直接读公共世界事实

---

## 15. 为什么现在不该写完整版 spec

如果现在直接写“完整角色智能体 spec”，会出现两个问题：

1. 文档会和当前仓库能力严重脱节  
   现在 auditory 还没进角色私有感知，记忆系统没起步，完整 spec 会天然变成空中楼阁。

2. 设计会掩盖真正的工程顺序  
   当前最关键的问题不是“人格设计还不够华丽”，而是：
   - 输入边界怎么接
   - 最小主观理解怎么成立
   - 最小意图怎么回到现有 Godot 壳

所以现在最正确的 spec 不是总纲复写，而是：

**“角色智能体最小运行时切片 spec”**

---

## 16. 未来演化顺序

建议的推进顺序：

### 第一步

把 auditory 推进到角色私有感知链：

- `auditory_fact`
- `CandidatePerceptEvent`
- `CharacterPerceivedEvent`

### 第二步

实现最小 `CharacterAgent L2`

### 第三步

实现最小 `CharacterAgent L3`

### 第四步

把最小 `CharacterAgent L4` 接到现有 Godot 壳

### 第五步

再逐步扩展：

- 记忆
- 社交推断
- 长期动机
- 玩家接管双回路
- `FACS/SACS/Binder`

---

## 17. 一句话收束

当前该写的角色智能体 spec，不是“完整角色智能体总设计”，而是：

**如何在当前已经跑通的 `L1 / L6 / Siming` 底座上，接入一个不越权、可验证、可渐进扩展的最小角色智能体切片。**

这份切片的目标不是一次性把角色脑做完，而是先让 `CharacterA/B` 真的开始拥有：

- 私有输入
- 主观理解
- 最小意图
- 最小具身回应

并且不破坏当前已经成立的 `Phase 0` 运行闭环。
