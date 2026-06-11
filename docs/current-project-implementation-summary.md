# 当前项目实现总结

日期：`2026-06-11`

这份文档是当前仓库 `Paralls Phase 0 Demo` 的 repo-local 实现总结。

它不重复主项目理想架构，而是回答六件事：

1. 当前项目到底已经实现到什么程度
2. 它现在能支撑什么真实能力
3. 当前 `System L1 / L2 / L6` 分层在主线上是怎么落地的
4. 一个完整案例在当前仓库里会怎样流转
5. 角色智能体现在是不是该开始做了，以及该怎么做
6. 已经实现的各部分未来应该如何加强

---

## 1. 一句话结论

当前主线仓库已经不再是“只有 Godot 壳和后端骨架”的技术样片，而是一个真正能闭环的最小运行时切片：

- Godot 本地 `System L1` 已经能稳定发出结构化事实与玩家输入
- backend authority 已经能做 deterministic `ESM` 结算
- `L6` authority event bus 已经成立
- `L2` Siming 已经能消费 authority 事件并回写最小催化输出
- Godot 前端兼容层已经能通过 authority projection 稳定消费候选、世界结果、状态机转移和司命输出
- 严格 `Phase 0` 验证已经通过

按当前仓库自己的 repo-local 目标，这个项目已经完成了一个“玩家角色 + 两个角色壳 + 世界交互 + 最小司命催化”的可运行验证闭环。

但按主项目的 full-volume 理想态看，它还不是完整的角色智能体系统，也还不是完整的多层运行时架构收口版。

---

## 2. 当前完成状态

### 已经成立的部分

当前主线已经具备：

- `raw_fact_event` 统一事实上抛出口
- `player_input -> backend route -> authority result -> Godot presentation` 的执行链
- 视觉事实上抛与运行时投影闭环
- 听觉 raw fact 最小链
- 触觉 / 热感 / 嗅觉 / 生理 / 角色状态这五类剩余 emitter
- `ESM` deterministic 结算层
- `System L1 -> candidate percept -> per-character filter -> character perceived` 的最小桥
- `L6` authority event bus
- Siming authority-event 消费与输出链
- Godot websocket 兼容投影层
- backend 掉线后的 Godot 自动重连与关键请求补发

### 已验证结果

当前主线关键验证结果：

- `python -m pytest -q backend` -> `203 passed`
- `python scripts/verification/verify_phase0.py` -> `overall_strict_phase0_passed=True`
- `python scripts/verification/verify_phase1_slice.py` -> `overall_phase1_slice_passed=True`

当前严格 `Phase 0` 已证明：

- `dialogue_loop=proved`
- `successful_interaction=proved`
- `failed_interaction=proved`
- `visible_world_state_change=proved`
- `siming_reaction=proved`
- `voice_stub_path=proved`

---

## 3. 当前系统层级是怎样落地的

### 3.1 `System L1`：确定性空间层

当前 `System L1` 的现实职责是：

- Godot 本地高频执行
- 玩家输入结构化
- 视觉 / 听觉 / 触觉 / 热感 / 嗅觉 / 生理 / 角色状态事实发射
- backend `ESM` 结算

Godot 侧：

- `scripts/phase0/MainDemoController.gd`
- `scripts/autoload/BackendBridge.gd`
- `scripts/l1/facts/emitters/*`

backend 侧：

- `backend/app/services/fact_router.py`
- `backend/app/services/fact_handlers/*`
- `backend/app/services/esm_service.py`

这意味着当前 `System L1` 不只是“动画层”或“本地输入层”，而是已经承担：

- 角色壳所在空间中的可观察事实生产
- 玩家行为的结构化意图发送
- 世界状态的权威结算

### 3.2 `System L6`：事件总线层

当前 `L6` 的现实职责是：

- authority envelope 统一化
- authority event in-memory bus
- frontend compatibility projection
- replay / audit / verification 辅助边界

关键实现：

- `backend/app/models/authority_event.py`
- `backend/app/services/authority_event_bus.py`
- `backend/app/services/phase0_authority_event_adapter.py`
- `backend/app/services/frontend_authority_event_projection.py`

当前主线已经把这些消息放进 authority projection 体系：

- `conversation_candidate_event`
- `world_result`
- `state_machine_transition`
- `siming_output`

所以 `L6` 在主线里已经不是文档名词，而是实际运行中的中介层。

### 3.3 `System L2`：当前主要落成的是司命层

当前 `L2` 的现实职责就是 Siming：

- 订阅 authority 事件
- 生成公平快照 / 候选 / 决策 / attention prompt
- 通过 authority event producer 回写催化输出
- 保留 audit writer

关键实现：

- `backend/app/services/siming_event_consumer.py`
- `backend/app/services/siming_event_pipeline.py`
- `backend/app/services/siming_runtime.py`
- `backend/app/services/siming_event_producer.py`
- `backend/app/services/siming_audit_writer.py`

当前它能基于：

- `visual_fact_event`
- `esm_result_event`
- `conversation_resolution_event`
- `constraint_state_event`

产生最小但真实的司命输出，例如：

- `siming.fact_reveal`
- `siming.visual_observability_request`

### 3.4 角色智能体域：当前只具备前置输入边界，尚未正式实现内部 `L1-L4`

这里必须把两种层级分清楚：

- `System L1 / System L2 / System L6`
  - 属于系统级六层架构
- `CharacterAgent L1 / L2 / L3 / L4`
  - 属于角色智能体内部四层心智模型

它们不是同一层级的并列物，不能直接拿来对照。

当前主线已经成立的是：

- `System L1`
  - 世界事实生产
  - 玩家输入结构化
  - `ESM` 权威结算
- `System L2`
  - 当前主要落成的是 Siming
- `System L6`
  - authority event bus / projection / replay 边界

当前主线**还没有正式实现**的是角色智能体这条系统第二层域内部的：

- `CharacterAgent L1` 感知层
- `CharacterAgent L2` 理解层
- `CharacterAgent L3` 规划层
- `CharacterAgent L4` 执行层

当前主线已经具备的只是角色智能体域前置边界：

- `CharacterPerceivedEvent`
- `SelfBodyPerceivedEvent`
- `CharacterPerceivedInputService`
- 候选关系与运行态桥接对象

这些说明“角色智能体可以开始接入”，但还不能说明“角色智能体内部四层已经实现”。

---

## 4. 现在能做什么

### 4.1 玩家输入与执行

当前系统已经能稳定处理这些玩家侧输入：

- `move_intent`
- `focus_target_change`
- `dialogue_submit`
- `interact_intent`
- `environment_request`

它们不只是日志或按钮绑定，而是完整进入：

`Godot input -> websocket -> backend route -> authority result -> Godot presentation`

### 4.2 世界结算

当前 `ESM` 已经能稳定处理：

- 交互成功
- 交互失败（constraint）
- 环境状态变化
- 状态机 transition
- coarse 环境场更新

当前 repo-local 支持的环境请求包括：

- `light_level_drop`
- `light_level_restore`
- `thermal_level_rise`
- `smoke_density_rise`
- `noise_level_rise`

### 4.3 感知与候选链

当前已经成立的感知链包括：

- visual fact
- spatial access fact
- auditory fact
- tactile / thermal / olfactory / physiology / role-state fact

但注意成熟度不同：

- visual / spatial access 已经真正进入 candidate generation 与 runtime projection
- auditory 已经进入 authority 路由和验证，但仍冻结为 `System L1-only`
- tactile / thermal / olfactory / physiology / role-state 已经进入系统，但更多承担补强场景事实与验证价值

### 4.4 最小司命闭环

当前已经不是“后端里有个 Siming 类”而已，而是：

- authority 事件真实进入 Siming
- Siming 输出真实回到 Godot
- 角色壳会对司命 attention prompt 做出注意力反应

---

## 5. 当前真实边界

### 5.1 已经足够的部分

如果目标是：

- 玩家控制 `CharacterC`
- `CharacterA/B` 作为其他角色壳存在
- 玩家和角色 / 物体 / 环境形成最小交互
- 交互结果经过 authority backend 结算
- 司命在背后做最小叙事催化

那么当前项目已经够用，而且已经通过严格 `Phase 0` 验证。

### 5.2 还不够的部分

#### 听觉还没进入角色私有感知

当前系统已经有听觉 raw fact，但还没有把它推进到：

- candidate percept
- per-character perceived
- 角色私有“听到”输入

这意味着角色之间真正的“我听到了什么”还没成立。

#### 视觉链是闭环，但精度还比较粗

当前最关键的问题不是视觉链不存在，而是：

- 过滤上下文还比较薄
- 还不是严格 `line_of_sight / occlusion / lighting / geometry` 驱动
- 很多判断仍是 Phase 0 / Phase1-slice 级别的工程化近似

#### `CharacterAgent L1/L2/L3/L4` 还没有真正开始

当前仓库虽然有：

- `CharacterPerceivedEvent`
- `ConversationRelationService`
- `CharacterRuntimeStateService`
- `CharacterService`

但这还不是完整角色智能体，只是：

- 角色私有输入边界
- 最小关系候选层
- 最小对话与表现桥

真正的：

- `CharacterAgent L1` 感知层
- `L2` 理解层
- `L3` 规划层
- `L4` 执行协调层

还没有按角色智能体文档设计真正实现。

---

## 6. 一个当前主线真实成立的完整案例

### 案例描述

玩家控制 `CharacterC` 进入场景，先看向 `CharacterA`，再对 `A` 说话，然后转向桌上的 `obj_letter` 调查；第一次交互成功触发物体与环境变化，`CharacterB` 被司命拉进注意链；玩家退远后再次交互，后端权威拒绝，形成失败交互证明。

### 阶段 1：玩家进入并控制 `C`

- 玩家实际控制的是 `CharacterC` 对应的世界角色壳
- `A/B` 作为其他角色壳在场
- `MainDemoController` 和 `Phase0PlayerBridge` 维持玩家壳与角色壳的同步
- `System L1` 持续发空间、朝向、视觉和生理事实

### 阶段 2：`C` 看向 `A`

- Godot 发出 `focus_target_change`
- 同时发出视觉事实：
  - `fixed_gaze_on_target`
  - `actor_looks_at_actor`

backend 会：

- 更新 `C` 的 runtime snapshot / delta
- 通过 `ConversationRelationService` 形成候选关系
- 通过 authority projection 产出 `conversation_candidate_event`
- Siming 接收到候选事件并发出最小 `siming_output`

### 阶段 3：`C` 对 `A` 说话

- 玩家发出 `dialogue_submit(target_actor_id="char_a")`
- backend `CharacterService` 返回 `dialogue_response(actor_id="char_a")`
- Godot 角色壳表现出回应
- `voice stub` 路径会留下可验证证据

### 阶段 4：`C` 调查 `obj_letter`

- 玩家靠近并聚焦 `obj_letter`
- Godot 发出 `actor_near_object`
- 玩家发出 `interact_intent`

`ESM` 会依次给出：

- `action_request`
- `action_resolution_result`
- `state_machine_transition`
- `object_state_result`
- `body_state_result`
- `environment_state_result`

同时 Godot 继续发：

- `visual_evidence_projection`
- tactile fact
- thermal fact
- olfactory fact

### 阶段 5：`B` 被司命拉进注意链

这些 authority 事件会进入 `SimingRuntime`：

- `world_result`
- `conversation_resolution_event`
- `visual_fact_event`

司命会选择是否放大可观察性，并回写：

- `siming.fact_reveal`
- `siming.visual_observability_request`

前端投影层将其转成 Godot 兼容 `siming_output`，`CharacterB` 因而出现“注意到变化”的反应。

### 阶段 6：失败交互

玩家退远后再次对 `obj_letter` 发起交互。

这次 `ESM` 返回：

- `constraint_state_result`
- `constraint_type = distance_constraint`
- `constraint_code = out_of_range`

这不是本地假失败，而是 backend authority 真正拒绝。

于是当前主线已经具备：

**玩家 -> 感知 -> 交流 -> 成功交互 -> 世界变化 -> 司命催化 -> 他人注意 -> 失败交互**

的完整最小闭环。

---

## 7. 当前 `System L1 / System L6 / System L2` 的真实数据流

```text
Godot / MainDemoController
  |
  | player_input / raw_fact_event / visual_fact_event / environment_request
  v
backend/app/main.py
  |
  +--> System L1 route
  |      - fact_router
  |      - visual_fact_handler
  |      - ESMService
  |
  +--> relation/runtime seam
  |      - ConversationRelationService
  |      - CharacterRuntimeStateService
  |      - CandidatePerceptService
  |      - PerCharacterPerceptFilter
  |
  +--> System L6 authority bridge
  |      - Phase0AuthorityEventAdapter
  |      - InMemoryAuthorityEventBus
  |      - FrontendAuthorityEventProjector
  |
  +--> System L2 Siming
         - SimingEventConsumer
         - SimingRuntime
         - SimingEventProducer
         - SimingAuditWriter

authority_event_bus
  |
  +--> SimingEventPipeline
  |
  +--> FrontendAuthorityEventProjector
          |
          +--> world_result
          +--> state_machine_transition
          +--> conversation_candidate_event
          +--> siming_output
                  |
                  v
            Godot LocalPresentationBus / CharacterReplica / object/environment controllers
```

---

## 8. 角色智能体现在该不该开始做

结论：**应该开始，但不应该一上来就做 full-volume 角色智能体。**

现在最合适的不是直接铺完整 `L1-L4` 角色智能体，而是启动一个：

**“角色智能体最小可运行切片”**

### 为什么现在适合开始

因为前置条件已经差不多齐了：

- `System L1` 事实出口已经成立
- `ESM` 结算已经成立
- `L6` authority bus 已经成立
- `CharacterPerceivedEvent` 边界已经成立
- Siming 已经能作为上游催化源存在
- `Phase 0` 严格验证已经通过

这意味着现在再不开始角色智能体，后续很多增强就只能继续堆在 `MainDemoController`、`CharacterService`、`ConversationRelationService` 这类“过渡实现”里，边界会越来越脏。

### 为什么现在还不能直接做完整版

因为还缺几个关键前提：

- auditory 还没进入角色私有感知
- visual filter 精度还不够
- 角色记忆系统还没有真正起步
- `L2/L3/L4` 角色智能体运行预算、调试面、状态持久化都还没成型

所以现在最合理的是：

- **开始做角色智能体**
- 但只做最小竖切，不做全铺开

### 建议怎么开始

建议按这个顺序：

#### 第一步：补听觉进角色私有感知

先把 auditory 从 `L1-only` 推进到：

- `CandidatePerceptEvent`
- `CharacterPerceivedEvent`
- 角色私有 `audible_entities` / `attention` 输入

原因：

- 如果角色智能体连“听见别人说话/环境变化”都还没有，就会天然残缺

#### 第二步：做一个最小 `L2` 理解层

不要一次做完整人格脑，而是先做一个真正的 `CharacterAgentL2Runtime`：

- 输入：`CharacterPerceivedEvent`、`SelfBodyPerceivedEvent`、Siming 高层消息
- 输出：
  - `interpreted_summary`
  - `salience_score`
  - `risk_or_opportunity`
  - `attention_target`
  - 一条最小 `inner monologue candidate`

这一步的重点不是“聪明”，而是把“角色主观理解”从现在的规则桥里独立出来。

#### 第三步：做一个最小 `L3` 候选意图层

从最少几个候选开始：

- `observe`
- `approach`
- `withdraw`
- `speak`
- `inspect_object`
- `stay_silent`

然后加一个最简三重过滤器：

- persona bias
- logic viability
- gain/loss

先不要做复杂长期策略。

#### 第四步：把 `L4` 输出接回当前 Godot 表现层

这一步不要另起一套表现系统，直接复用当前已有的：

- `CharacterReplica.gd`
- role state / physiology / attention / dialogue 入口

让角色智能体先能驱动：

- 注意力切换
- 说/不说
- 站位变化
- 姿态变化

这就够了。

---

## 9. 已实现部分未来怎么加强

### `L1`

未来最该加强的是：

- auditory -> candidate -> per-character perceived
- visual filter 精度
- 更多真实空间条件：LOS / occlusion / lighting / ambient noise
- 环境状态与对象状态模板丰富度

### `L6`

未来最该加强的是：

- authority event 类型治理
- replay / audit surface
- debug panel 和 trace 工具统一化
- 把当前仍在 `main.py` 里的组合逻辑进一步下沉到分层入口

### `L2 Siming`

未来最该加强的是：

- 不只做 attention prompt，还要做更明确的公平快照、候选和决策解释
- audit record 的工程化可读性
- 更多环境 / 社交 /多角色失衡判断
- 与角色智能体的高层催化协议

### Godot 前端兼容层

未来最该加强的是：

- 将更多过渡逻辑从 `MainDemoController.gd` 拆出
- 让 `LocalPresentationBus`、`BackendBridge`、presenter/controller 更清晰分层
- 减少 `MainDemoController` 同时承担“autotest orchestrator + runtime coordinator + gameplay glue”三种职责

### 角色壳与执行层

未来最该加强的是：

- `CharacterReplica` 从“表现壳 + 部分逻辑壳”继续向真正的 `L4` 执行端靠拢
- root motion / stance / attention / body-state 更明确进入角色执行通道
- 玩家壳与 AI 壳的共同底层继续统一

---

## 10. 未来建议顺序

如果从今天开始继续往前推进，我建议顺序是：

1. 把 auditory 推进到角色私有感知
2. 做最小 `CharacterAgent L2`
3. 做最小 `CharacterAgent L3`
4. 复用现有 Godot 表现层接一个最小 `CharacterAgent L4`
5. 再逐步加深视觉/听觉精度、记忆、关系和长期策略

不要反过来先做：

- 长期记忆大系统
- 复杂人格大系统
- 多角色策略博弈大系统

因为那会在当前工程边界还不稳定的时候，过早把系统复杂度拉爆。

---

## 11. 结语

当前主线项目已经完成了从“Phase 0 演示壳”到“可验证的最小多层运行时切片”的跃迁。

它现在已经足够支撑：

- 玩家控制一个世界内角色
- 两个角色壳与玩家形成最小交流和观察关系
- 交互结果经 authority backend 结算
- 司命在背后做最小催化
- 严格 `Phase 0` 验证全通过

下一阶段最关键的，不是重写 `System L1`，也不是继续无止境增强 `MainDemoController`，
而是：

- 把听觉补进角色私有感知
- 把最小角色智能体真正接起来
- 然后在已有 `System L1 / System L6 / System L2` 基础上，逐步把角色主观理解、意图选择和具身执行独立成真正的角色智能体内部四层

一句话收束：

**现在的项目已经足够支撑“玩家 + 两个角色壳 + 世界 + 司命”的最小戏剧闭环；下一步该启动角色智能体，但应该从最小可运行切片开始，而不是一次性上完整脑。**
