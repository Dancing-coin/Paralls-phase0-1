# 当前项目实现总结

日期：`2026-06-18`

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
- backend / docs / character-agent-execution / phase0 / phase1-slice 关键验证当前为绿

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

当前 `2026-06-18` worktree 验证结果：

- `python -m pytest -q` -> `616 passed`
- `python scripts/verification/harness.py --profile docs` -> `overall_docs_passed=True`
- `python scripts/verification/harness.py --profile character-agent-execution` -> `overall_character_agent_execution_passed=True`
- `python scripts/verification/verify_l1_runtime_edges.py` -> `overall_l1_runtime_edges_passed=True`
- `python scripts/verification/harness.py --profile phase0` -> `overall_strict_phase0_passed=True`
- `python scripts/verification/harness.py --profile phase1-slice` -> `overall_phase1_slice_passed=True`

当前 verification truth 还新增了一条 repo-local 工程事实：

- `phase0` / `character-agent-execution` runtime profile 现在使用 fresh-backend verification path，避免复用旧 backend 进程污染当前 worktree 证据
- `verify_phase0.py` 现在也给主场景 autotest / focus-autotest 更宽的 `--quit-after` 窗口，以匹配 fresh-backend 启动后的连接确认时序
- `MainDemoController` 现在会把首次 `backend_connected` 之前的 `backend_closed:-1` 视为启动期断连噪音，但仍会补发一次自动重连，避免 fresh-backend `phase0` 运行时验证停在首轮握手失败
- `verify_l1_runtime_edges.py` 当前 hard-pass 已改按现行 runtime truth 判定：`backend_connected` + 初始 `zone bootstrap` + 无 HTTPRequest overlap error；旧 reconnect/privacy/environment edge probe 现在被显式 isolated，不再作为 hard-pass 前提
- `verify_phase0.py` 当前也已去掉冗余的 `PHASE0_DEBUG_LOGGING=1` 强制注入；`PHASE0_AUTOTEST` / `PHASE0_FOCUS_AUTOTEST` 已足够打开验证日志，这次修正后 strict `phase0` broad runtime verification 重新转绿
- `CharacterRuntimeState` 已不再保留 `finalize_player_presentation_input()` 这层空转 presentation bridge，formal presentation contract 现在直接沿 shared runtime-state / skin boundary 流转
- `CharacterReplica.apply_embodied_pose_sync(...)` 现在通过 `Phase0CharacterShellSync` 显式接收 player motion state，而不再从父节点隐式回查 `motion_state`
- `CameraOcclusionFader` 现在只依赖 `PlayerShell.get_camera()` / `get_control_anchor_position()` 这层 wrapper seam，不再直接抓取 `Phase0InputBridge` 节点做 camera / anchor 查询
- `Phase0ViewAnchorResolver` 现在优先走已冻结的 direct wrapper mounts（`CharacterReplica` / `CameraHolder`）以及 `PlayerShell.get_camera()`，不再对这些 wrapper-local 节点依赖递归 `find_child(...)` 搜索
- `PlayerShell` 现在还额外提供 `get_visual_forward()`，并且 `Phase0ViewAnchorResolver` 现在会优先走这层 wrapper-facing forward seam，再回退到 recursive `VisualRoot` 搜索
- `CharacterMotor` 现在也通过 `CharacterControllerPort` 的 field-read helper 读取 normalized `CharacterIntentFrame` 的 `move_local` / `gait` / `action`，而不再在 motor 内部继续手拆这些 actor-side intent fields
- `Phase0PlayerBridge` 现在也通过 `CharacterControllerPort` 的 field-read helper 读取 normalized intent fields（`move_local` / `gait` / `action` / `desired_facing_yaw`），进一步收紧 bridge 侧的 actor-intent dictionary 直接拆包
- `PlayerShell` 现在还额外提供 wrapper-owned movement state 的薄 alias（`get_body_position` / `get_planar_velocity` / `get_vertical_velocity` / `is_grounded_state` / `get_numeric_setting`），并且 `Phase0PlayerBridge` / `CharacterMotor` 已开始通过这些 alias 读取玩家壳运动状态，而不再继续直接读 `player.global_position` / `player.velocity` / `player.is_on_floor()` / `body.get(...)`
- `PlayerShell` 现在也额外提供 `get_character_replica()`，并且 `Phase0PlayerBridge` 已改用这层 alias，而不再从桥侧直接树查 `CharacterReplica`
- `CharacterPresentationInput` 现在还额外提供更细的 field-read helper（例如 `focus_target_id` / `requested_action` / `action_gait_hint` / `equipment_gait_hint` / `active_command_type`），并且 `KnightRoleSkin` / `CharacterRuntimeState` 已开始直接通过这些 helper 读取 presentation 子字段，而不再继续拆内部子字典
- `CharacterRuntimeState` 现在还额外提供 player-shell locomotion 中间字典的读取 helper（`motion_fields` / `locomotion_decision`），并且 `CharacterReplica._update_player_shell_locomotion()` 已开始通过这些 helper 读取 locomotion 决策字段，而不再继续直接拆这两层中间字典
- `CharacterRuntimeState` 现在还额外提供 agent execution side-effect helper（`focus_target_lookup` / `physiology_hint` / `role_state_effects` 以及 `target_lookup` 读取 helper），并且 `CharacterReplica` 已开始通过这些 helper 读取 execution-side-effect 中间字典，而不再继续直接拆 `execution_side_effect_plan` / `lookup`
- `CharacterReplica._on_character_agent_execution_received(...)` 现在也通过 `CharacterRuntimeState` helper 读取 normalized intent-frame 的 `action`，而不再直接在壳侧调用 `CharacterControllerPort.get_action_name(frame)`，也不再通过壳侧 `_payload_string(...)` 回退去拆这条 shared ingress contract
- `CharacterRuntimeState` 现在还额外提供 `emitter actor_id` 同步 helper（`should_sync_emitter_actor_id(...)`），并且 `CharacterReplica` 的 role/physiology fact emitter 已开始通过这个 helper 判断是否需要写回 `actor_id`，而不再继续直接读取 emitter 本身的 `actor_id`
- `CharacterRuntimeState` 现在还额外提供 dialogue / siming / runtime-state payload actor-target helper，以及 `command target position` / line-of-sight `collider` helper；`CharacterReplica` 已开始通过这些 helper 处理 payload actor targeting、`target_position` 和 LOS hit collider，而不再继续直接拆这些中间字段
- `CharacterRuntimeState` 现在还额外提供通用 payload string helper，`CharacterReplica` 已开始通过它读取 `dialogue_text` / `target_actor_id` / `command_type` / `target_object_id` / `target_environment_id` / `causation_id` / `correlation_id`，而不再继续保留壳侧 `_payload_string(...)` 拆包层
- `phase0` harness 的 `siming_reaction` 证据判定现在也已同步到当前运行时真相：`backend_message_type:siming_output` 现在可以单独作为 repo 当前最小 Siming 反应的合法运行时证明，而不再只依赖 `attention_applied:char_b`
- `CharacterRuntimeState` 现在还额外提供 `line-of-sight hit collider` helper，且 `CharacterReplica._has_line_of_sight_to_target()` 已开始通过它读取物理射线命中的 collider，而不再继续直接访问 hit 字典字段

当前真实已证明的 runtime 事实：

- `character_agent_execution_contract=proved`
- `character_agent_execution_consumer=proved`
- `character-agent-execution` 窄专项 probe 现在还会直接证明收到的 payload 本体同时携带 `actor_control_frames` / `presentation_plan` / `action_request_bundle`
- `verify_l1_runtime_edges.py` 已按当前 runtime truth 转绿
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

### 3.4 角色智能体域：当前已有 legacy minimal slice，并已进入 full runtime convergence 的中段

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

当前主线**还没有完成**的是 full character-agent runtime 的整体收口与最终完成声明，不是 `L1/L2/L3/L4` 四层都还没开始。

当前现实状态是：

- `CharacterAgent L1` 已有 full private perception runtime 的第一批实现与测试面，并且当前 private snapshot 已经不再只停留在空默认值：定向/空间私有感知现在还能把 `attention_targets` / `current_attention_targets` / `short_horizon_social_presence` / `local_spatial_confidence_map` 填进 `CharacterPrivateWorldSnapshot`；低清晰度或低确定度的 unresolved 私有感知现在还会进入 `active_anomalies`，并把 `distraction_level` 从 `baseline` 抬到 `elevated`；司命最小 catalyst 现在也会把对应 actor 的 `vigilance_level` 从 `baseline` 抬到 `elevated`，但 richer modality coverage 和更强 runtime proof 仍未收口
- `CharacterAgent L2` 已有 gateway-facing request、structured mapping、model-backed runtime consumption 与本地 fallback
- `CharacterAgent L3` 已有 candidate generation、triple-filter、planner-driven suggestion path 与 `char_c` suggestion mode
- `CharacterAgent L4` 已有 five-channel execution plan、shared actor ingress seam、action-request authority routing与 writeback

但这仍然不等于 Stage B 或 full `L4` 已完成。

当前主线已经具备的角色智能体相关现实落地包括：

- `CharacterPerceivedEvent`
- `SelfBodyPerceivedEvent`
- `CharacterPerceivedInputService`
- 候选关系与运行态桥接对象
- `CharacterPerceivedEvent` 现在还会保留最小私有感知元数据：`source_actor_id` / `target_actor_id` / `target_object_id` / `target_environment_id` / `distance_m`
- legacy `backend/app/services/character_agent_l1.py`
- legacy `backend/app/services/character_agent_l2.py`
- legacy `backend/app/services/character_agent_l3.py`
- legacy `backend/app/services/character_agent_l4_adapter.py`
- legacy `backend/app/services/character_agent_runtime.py`

这些 legacy 服务证明仓库已经有一个最小角色智能体切片，而不是完全空白。

但它们仍然只是 partial convergence，不是本仓库当前目标所要求的 full runtime：

- `char_c` 现在已经进入统一 runtime species，并具备 `player_priority_assisted` 最小双回路：
  - 默认抑制 autonomous goal-command 输出
  - 产出结构化 `character_agent_suggestion`
  - websocket raw-fact path 现在也已用 tests 证明：在 `player_priority_assisted` 下，`char_c` 不再直接放出 autonomous `character_agent_output`，而是稳定回到 suggestion packet 路径
- session timeline 现在已经存在并可按 actor 查询，且 runtime 现在支持可选本地持久化根目录用于重建 actor timeline
- 三层 memory 现在已有最小 runtime core：
  - `working_memory`
  - `episodic_memories`
  - `relational_memories`
- `CharacterWorkingMemoryState` 现在也不再只是计划中的文件名：repo 已有 objectized state 入口，`CharacterWorkingMemory.build_state(...)` / `CharacterAgentMemoryStore.working_memory_state(...)` 已能在保持原 `retrieval_bundle()` 不变的前提下按 actor 汇总 `recent_perceived_events` / `recent_esm_results` / `recent_siming_catalysts` / `private_snapshot`
- 默认运行仍以内存态为主，但 storage seam 现在支持可选本地 JSON 持久化与恢复
- 当前这条 memory/session 链的 repo-local 真实落位已经明确存在于：
  - `backend/app/character_agent/storage/session_store.py`
  - `backend/app/character_agent/storage/memory_store.py`
  - `backend/app/character_agent/memory/working_memory.py`
  - `backend/app/character_agent/memory/episodic_memory.py`
  - `backend/app/character_agent/memory/relational_memory.py`
- relational/factual memory 现在也不再只停留在 store API 存在：带明确 `source_actor_id` 的 actor-private `CharacterPerceivedEvent` 现在会在 runtime 里产出最小 `relational_belief_event`（当前最小 shape 为 `trust_level`，低 certainty/clarity 时回写成 `guarded`），并进入 timeline / relational store；offline `L2/L3` 现在也开始对这类 guarded relational belief 产出更保守的风险/意图倾向
- 这条 guarded relational belief 现在还进一步开始进入 `L3` 的解释层：在没有更强 recent world/constraint history 时，offline `L3` 现在会把这类 guarded relation 回流到 `risk_notes`，并可直接进入 `why_this_now` / `role_consistency_hint`
- `L3` planner suggestion fallback 现在也会消费这类 guarded relational belief：当 model explanation 为空、且没有更强 recent world/constraint history 时，`build_suggestion_packet(...)` 也会把 guarded relation 回流到 `risk_notes`、`why_this_now`、`role_consistency_hint`
- runtime orchestrator 本身也已经落位为：
  - `backend/app/character_agent/runtime/runtime_loop.py`
  - legacy `backend/app/services/character_agent_runtime.py` 现在只是 compatibility shell
- 当前 runtime species 也已经明确包含：
  - `char_a`
  - `char_b`
  - `char_c`
- 其中 `char_c` 当前不是被排除在 full runtime 之外，而是：
  - 仍进入同一条 `CharacterAgentRuntime` species
  - 默认 control mode 为 `player_priority_assisted`
  - 感知与 self-body 事件照常进入 timeline / memory / reasoning request 链，只是默认不直接放出 autonomous goal-command
  - 当前 suggestion path 也不再只是 websocket 出口；`player_priority_assisted` 下生成的 `character_agent_suggestion_packet` 现在同样会写入 runtime timeline / memory
- 当前写回行为的真实边界也应按代码理解：
  - `character_perceived_event` 会写入 working + episodic
  - `character_agent_settlement_result` 会写入 working + episodic
  - `character_agent_dialogue_response` 会写入 working + episodic
  - `relational_belief_event` 会写入 working + relational
- 对 full-auto actor 而言，当前 timeline 现实还进一步包含：
  - `character_agent_execution_request`
  - 也就是 perception -> reasoning request -> interpretation -> execution request 这条最小闭环已经进入 runtime timeline，而不只是停在 interpretation
- 对 `player_priority_assisted` actor 而言，当前 timeline 现实也已包含：
  - `character_agent_suggestion_packet`
  - 也就是 perception -> reasoning request -> interpretation -> suggestion packet 这条 assisted 分支现在也进入 runtime timeline / memory，而不只是停在待发送前端的瞬时 packet
- 这仍然不等于 Stage B memory 全面完成：
  - 当前 persistence 是 local JSON seam，不是最终 DB / migration 方案
  - episodic / relational extraction 目前仍是最小规则驱动，而不是完整长期记忆策略
- `CharacterModelGateway` / `CharacterModelRouter` / `CharacterContextBuilder` / `CharacterPromptPolicy` / `CharacterStructuredOutputValidator` 已存在为 structured-input + structured-output surface
- 这条 surface 当前已经明确支持：
  - `online_default`
  - `local_only`
  - `hybrid_ready`
  - `CharacterContextBuilder` 负责把 snapshot + memory bundle + control mode 组装成 structured context
  - `CharacterContextBuilder` 现在也可选承接 objectized `working_memory_state`，同时不破坏原有 `memory_bundle` shape
  - `CharacterPromptPolicy` 负责把 task_kind / route / context 组装成 prompt + policy
  - `working_memory_state` 现在也不再只是被动透传；`CharacterPromptPolicy` 已开始把其中的 `recent_perceived_events_count` / `recent_esm_results_count` / `recent_siming_catalysts_count` / `private_snapshot_actor_id` 压进 `user_instruction`
  - `snapshot` 里的 `last_siming_catalyst` 现在也会被 `CharacterPromptPolicy` 压进 `user_instruction`
  - `snapshot` 里的 `body_state_hints` 现在也会以 `body_state_hints_count` 的形式被 `CharacterPromptPolicy` 压进 `user_instruction`
  - `snapshot` 里的 `recent_world_changes` / `recent_constraint_results` 现在也会分别以 count + recent sample 形式被 `CharacterPromptPolicy` 压进 `user_instruction`
  - `CharacterStructuredOutputValidator` 负责本地验证结构化输出
- 但这仍然不等于 provider / router 层已经完成最终收口：
  - 现在的 `CharacterModelProvider` 仍是当前 demo 的最小在线/离线双模接口
  - `CharacterModelRouter` 仍只是 route mode 解析器，而不是完整多 provider 目录
- `L2` 已有 gateway-facing request + structured output mapping + model-backed runtime consumption，仍保留本地 fallback
- `L3` 已有 candidate generation / triple-filter / planner-driven suggestion path，并已接入 model-backed candidate/suggestion 消费，仍保留本地 fallback
- 这两层现在也不是只停留在 helper API 上：
  - `CharacterAgentRuntime` 已把 `memory_bundle` 和 `control_mode` 真正送进 `CharacterAgentL2Service.prepare_reasoning_request(...)` / `interpret_*`
  - `CharacterAgentRuntime` 现在也会把 objectized `working_memory_state` 真正送进 `CharacterAgentL2Service.prepare_reasoning_request(...)` / `interpret_*`
  - `CharacterAgentRuntime` 现在也会把 snapshot 内的 `last_siming_catalyst` 真正送进 `CharacterAgentL2Service.prepare_reasoning_request(...)` 上下文，而不再只停留在 `L1`/prompt 摘要
  - `vigilance_level` 现在也不再只是停留在 `L1` private snapshot：离线 `L2` 在该值为 `elevated` 时会把 `opportunity_level` 提升到 `medium`
  - `active_anomalies` 现在也不再只是停留在 `L1` private snapshot：离线 `L2` 在该列表非空时会把 `risk_level` 提升到 `medium`
  - `distraction_level=elevated` 现在也不再只是停留在 `L1` private snapshot：离线 `L2` 在该值为 `elevated` 时会把 `ambiguity_level` 提升到 `medium`
  - `body_state_hints` 现在也不再只是停留在 `L1` private snapshot：离线 `L2` 在该列表非空时会把 `interpretation_type` 视为 `body_state`，并把 `risk_level` 提升到 `medium`
  - `recent_world_changes` / `recent_constraint_results` 现在也不再只是模型默认值：runtime 会在 settlement/dialogue writeback 时把 world-change / constraint 摘要回写到 snapshot 的短历史里
  - `recent_constraint_results` 现在也不再只是停留在 snapshot 历史：离线 `L2` 在该列表非空时会把 `risk_level` 提升到 `medium`
  - `recent_world_changes` 现在也不再只是停留在 snapshot 历史：离线 `L2` 在该列表非空时会把 `opportunity_level` 提升到 `medium`
  - `CharacterAgentRuntime` 现在也会把 `snapshot.model_dump()` 和 `memory_bundle` 真正送进 `CharacterAgentL3Service.select_intent(...)` / `build_suggestion_packet(...)`
  - `recent_world_changes` 现在也开始影响 `L3` fallback candidate generation：当 `attention_target` 为空且原始 `opportunity_level` 仍为 `low` 时，它会把 fallback planning 至少抬到 `medium` 的 opportunity 档
  - planner fallback 现在也会在 recent world change 存在、且 model `recommended_intents` 为空时，把 `speak_public` 顶到建议列表前面，与 offline `L3` model fallback 对齐
  - `vigilance_level` 现在也开始影响 offline `L3` 的 `recommended_intents` 次序：当其为 `elevated` 时，fallback model output 也会把 `speak_public` 顶到建议列表前面
  - `effective_opportunity_level` 现在也开始影响 offline `L3` 的 `selected_intent`：当没有 recent constraint 风险压制且机会档已抬到 `medium/high` 时，fallback model output 也会直接把 `selected_intent` 收敛到 `speak_public`
  - `recent_world_changes` 现在也开始影响 suggestion packet 的 `why_this_now` fallback：当 model output 没给出更强解释时，最近一条 world-change 摘要会优先回流
  - `recent_world_changes` 现在也开始影响 suggestion packet 的 `role_consistency_hint` fallback：当 model output 和 inner prompt 都没给出更强提示时，最近一条 world-change 摘要会优先回流
  - `vigilance_level=elevated` 现在也开始影响 suggestion packet 的 `why_this_now / role_consistency_hint` fallback：当既没有 recent world/constraint history，也没有更强 model 或 inner prompt 提示时，它会回流成 `heightened vigilance`
  - `distraction_level=elevated` 现在也开始影响 suggestion packet 的 `why_this_now / role_consistency_hint` fallback：当既没有 recent world/constraint history，也没有更强 model 或 inner prompt 提示时，它会回流成 `uncertain signal`
  - `recent_constraint_results` 现在也开始影响 `player_priority_assisted` suggestion 的 `risk_notes` fallback：当 model output 没显式给出 risk notes 时，这些 recent constraint 摘要会直接回流到 suggestion packet
  - `recent_constraint_results` 现在也开始影响 offline `L3` 的 `selected_intent/recommended_intents` 倾向：当 recent constraint 存在时，fallback model output 会优先把 `self_protect` 作为当前建议
  - `risk_level=medium/high` 现在也开始影响 offline `L3` 的 `selected_intent/recommended_intents` 倾向：即使没有 recent constraint 历史，fallback model output 也会直接倾向 `self_protect`
  - `recent_constraint_results` 现在也开始在没有 recent world change 时影响 offline `L3` 的 `why_this_now` fallback：constraint 摘要会优先回流到解释文本
  - `recent_constraint_results` 现在也开始在没有 recent world change 与 inner prompt 时影响 offline `L3` 的 `role_consistency_hint` fallback：constraint 摘要会优先回流到提示文本
  - `CharacterAgentRuntime` 现在也会把 objectized `working_memory_state` 真正送进 `CharacterAgentL3Service.select_intent(...)` / `build_suggestion_packet(...)`
  - `player_priority_assisted` 不只是文档名词，而是当前 runtime species 中真实影响 `L2/L3` 请求上下文与 suggestion packet 输出的控制模式
- `L4` 已有 five-channel execution plan 与 `character_agent_execution` 主运行时 ingress，`character_agent_output` 仅保留静态兼容信号链
- 但当前 `L4` 仍是双层现实，而不是单一路径完全收口：
  - `backend/app/character_agent/execution/l4_executor.py`
    - 负责 five-channel execution plan / `presentation_plan` / `action_request_bundle`
  - `backend/app/character_agent/execution/l4_adapter.py`
    - 现在已经收窄为 thin compatibility shell：它会先读取 `L4Executor` 的 execution plan，再适配出 legacy `CharacterGoalCommand`
- runtime loop 当前也确实同时做两件事：
  - `character_agent_execution_request` 被写入 timeline / memory
  - 但 `ingest_character_perceived_event(...)` / `ingest_self_body_perceived_event(...)` 的返回值仍然是 legacy `CharacterGoalCommand` 列表，说明 runtime 仍保留 compat 级的目标命令出口，而不是只输出纯 execution_plan
- 这条 execution_request 与返回命令现在至少在 actor_id 维度上是因果对齐的：同一次 ingest 既会写 execution_request，也会返回同一 actor 的 legacy `CharacterGoalCommand`
- 当前 `CharacterAgentRuntime` 的真实主线已经进一步变成：
  - 先由 `CharacterAgentL4Executor` 生成五通道 execution plan
  - 再由 `CharacterAgentL4Adapter.build_commands_from_execution_plan(...)` 兼容成 legacy `CharacterGoalCommand`
  - `backend/app/main.py` 的 websocket/runtime glue 已不再内联 fallback `CharacterPrivateWorldSnapshot` / `CharacterInterpretation` / `CharacterIntentDecision` reconstruction；legacy command 的 compat reconstruction 现在回收到 `CharacterAgentL4Adapter.command_to_execution_payload(...)`
  - 因此 `L4Adapter` 已经是 thin compat shell，而不是独立的意图/命令推导主线；它只负责把 execution plan 的 actor/frame/request 兼容成 legacy 目标命令
- 这条 legacy 命令兼容出口当前也已经收窄到单一命令语义：
  - `CharacterPerceivedEvent` / `SelfBodyPerceivedEvent` 当前返回的 legacy command 现在是 `observe`
  - 也就是说 full-auto actor 的 runtime 现在不再把 legacy command 兼容成一个宽泛命令集合，而是明确收束在 observe 语义上
- 这条 compat 还保留了最小 causality trace：
  - `CharacterAgentL4Executor` 在 `actor_control_frames` 中保留 `producer_ts`
  - `CharacterAgentL4Adapter` 会把 `producer_ts` 还原进 legacy `CharacterGoalCommand`
- `CharacterAgentL4Adapter` 当前也会把 `causation_id` / `correlation_id` 保持为 `character_agent:<producer_ts>`
- 当前更进一步的真实实现是：
  - `CharacterAgentL4Executor` 在 `actor_control_frames` 中把 `causation_id` / `correlation_id` 写成 `character_agent:<producer_ts>:<actor_id>`
  - `CharacterAgentL4Adapter` 会把这两个字段原样回流到 legacy `CharacterGoalCommand`
- 所以 compat shell 虽然还存在，但它不是无时间戳、无溯源字段的空壳映射
- 更进一步地，当前 compat shell 的溯源字段已经带上 actor 级别区分：
  - `CharacterAgentL4Executor` 在 `actor_control_frames` 里写入 `producer_ts`
  - `CharacterAgentL4Adapter` 会把 `causation_id` / `correlation_id` 还原为 `character_agent:<producer_ts>:<actor_id>`
- 当前 `producer_ts` 已经能沿这条 compat 路径回流到 returned legacy command：
  - five-channel execution plan 生成时写入 `actor_control_frames[].producer_ts`
  - `build_commands_from_execution_plan(...)` 会把它还原到 `CharacterGoalCommand.producer_ts`
- 当前 compat shell 还回流最小 role-state 语义：
  - `CharacterGoalCommand.role_state_hint` 现在会从 execution plan 的 request 语义中回流
  - 对 speech / inspect / approach 这类既有请求，legacy 命令不再只剩 command_type，而是会保留一个最小 role_state_hint
- 当前 compat shell 还回流最小 dialogue payload：
  - 对 speech 类请求，`CharacterGoalCommand.dialogue_text` 现在会优先从 request `content` 回流
  - 如果 request 没显式内容，则会回退到 `presentation_plan.speech_state.utterance_request`
- 对应地，`CharacterAgentL4Executor` 现在也不再为 speech 类请求输出 placeholder content：
  - `speak_public` / `speak_private` / `share_info` / `withhold` 的 `requested_actions[].content` 现在直接来自 `interpretation.interpreted_summary`
  - 这样 legacy compat command 与 five-channel execution plan 之间在 speech 内容上也保持了最小一致性
- 因此当前准确状态应表述为：
  - five-channel execution plan 已落地并有测试面
  - shared actor main ingress 已落地并有 Godot runtime proof
  - 但 `L4Adapter` 的 legacy command shell 仍然存在，不能把 Stage B / full `L4` 描述为单一路径最终收口完成
- `action_request` authority chain 现在只完成最小闭环：
  - `inspect_object -> interact -> ESM settlement -> runtime writeback`
  - `approach -> action_request -> minimal settlement -> runtime writeback`
  - `speak_public -> dialogue_response -> runtime writeback`
  - `speak_private -> dialogue_response -> runtime writeback`
  - `share_info -> dialogue_response -> runtime writeback`
  - `withhold -> dialogue_response -> runtime writeback`
  - `seek_private_distance -> action_request -> minimal settlement -> runtime writeback`
  - `withdraw -> action_request -> minimal settlement -> runtime writeback`
  - `follow_target -> action_request -> minimal settlement -> runtime writeback`
  - `break_contact -> action_request -> minimal settlement -> runtime writeback`

所以当前准确结论不是“角色智能体完全没开始”，而是：

- legacy minimal slice: 已存在
- full character-agent runtime convergence: 已进入中段，但远未完成

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
- auditory 现在已经部分进入 candidate generation 与角色私有感知：
  - targeted actor-to-actor auditory facts 已进入 private percept path
  - ambient environmental auditory context 仍保持 `System L1-only`
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

- 玩家控制 `PlayerCharacter`，其内嵌可见角色壳为 `CharacterReplica(actor_id=char_c)`
- `CharacterA/B` 作为其他角色壳存在
- 玩家和角色 / 物体 / 环境形成最小交互
- 交互结果经过 authority backend 结算
- 司命在背后做最小叙事催化

那么当前项目已经够用，而且已经通过严格 `Phase 0` 验证。

### 5.2 还不够的部分

#### 听觉还没完整进入角色私有感知

当前系统已经把**定向**听觉推进到了角色私有输入链：

- `auditory_fact -> CandidatePerceptEvent`
- `CandidatePerceptEvent -> CharacterPerceivedEvent`
- 角色私有 `audible_entities`

但这仍然不是 full target，因为：

- `ambient_noise_changed` 仍保持 system-level only
- actor-private hearing attribution 还没有完整设计
- richer auditory interpretation / memory / planning 还没有真正展开

#### 视觉链是闭环，但精度还比较粗

当前最关键的问题不是视觉链不存在，而是：

- 过滤上下文还比较薄
- 还不是严格 `line_of_sight / occlusion / lighting / geometry` 驱动
- 很多判断仍是 Phase 0 / Phase1-slice 级别的工程化近似

#### full `CharacterAgent L1/L2/L3/L4` 仍未完成最终收口

当前仓库虽然已经有：

- `CharacterPerceivedEvent`
- `ConversationRelationService`
- `CharacterRuntimeStateService`
- `CharacterService`
- 一套 legacy `character_agent_*` service 最小切片

但这还不是完整角色智能体，只是：

- 角色私有输入边界
- 最小关系候选层
- 最小对话与表现桥
- 最小 actor-goal output slice

真正的：

- `CharacterAgent L1` 感知层
- `L2` 理解层
- `L3` 规划层
- `L4` 执行协调层

还没有按角色智能体文档设计真正实现。

---

## 6. 一个当前主线真实成立的完整案例

### 案例描述

玩家控制 `PlayerCharacter` 进入场景，其内嵌可见角色壳为 `CharacterReplica(actor_id=char_c)`；玩家先看向 `CharacterA`，再对 `A` 说话，然后转向桌上的 `obj_letter` 调查；第一次交互成功触发物体与环境变化，`CharacterB` 被司命拉进注意链；玩家退远后再次交互，后端权威拒绝，形成失败交互证明。

### 阶段 1：玩家进入并控制 `C`

- 玩家实际控制的是 `PlayerCharacter` 这个 `CharacterBase` 外壳，而其可见角色壳是内嵌的 `CharacterReplica(actor_id=char_c)`
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

结论：**已经开始，而且当前工作已经进入从 minimal slice 向 full runtime convergence 推进的中段。**

### 为什么当前应该继续收口

因为前置条件已经差不多齐了：

- `System L1` 事实出口已经成立
- `ESM` 结算已经成立
- `L6` authority bus 已经成立
- `CharacterPerceivedEvent` 边界已经成立
- Siming 已经能作为上游催化源存在
- `Phase 0` 严格验证已经通过

这意味着当前工作的重点已经不是“要不要开始”，而是：

- 不要把已有的 partial runtime 误当成最终态
- 不要继续把能力堆回 legacy service / bridge surface
- 沿着已经建立的 runtime loop、memory、gateway、planner、execution seams 继续收口

### 为什么现在还不能宣称完整版

因为还缺几个关键前提：

- ambient auditory context 还没有完整 actor-private hearing 设计
- visual filter 精度还不够
- 角色记忆系统虽已起步，并且现在支持可选本地 JSON 持久化与恢复，但它仍不是完整 durable database/pipeline 层
- `L2/L3/L4` 已经有结构化 seams，其中 `L2/L3` 已接入 model-backed runtime consumption，但 `L4` 仍未完全收口到 shared actor main execution path

所以当前最合理的是：

- **继续沿既有 Stage B seams 做收口**
- 不把已经存在的 partial runtime 当成最终态

### 建议怎么继续

建议按这个顺序：

#### 第一步：继续扩大 allowed action request classes

当前最小闭环已经覆盖：

- `inspect_object -> interact -> ESM settlement -> runtime writeback`
- `approach -> action_request -> minimal settlement -> runtime writeback`
- `speak_public -> dialogue_response -> runtime writeback`
- `speak_private -> dialogue_response -> runtime writeback`
- `share_info -> dialogue_response -> runtime writeback`
- `withhold -> dialogue_response -> runtime writeback`
- `seek_private_distance -> action_request -> minimal settlement -> runtime writeback`
- `withdraw -> action_request -> minimal settlement -> runtime writeback`
- `follow_target -> action_request -> minimal settlement -> runtime writeback`
- `break_contact -> action_request -> minimal settlement -> runtime writeback`

下一步应继续沿同一 authority chain 收紧已落地类目的 settlement semantics、runtime proof 和 actor-side convergence，例如：

- richer settlement payloads for the already-landed request classes
- broader runtime verification around the shared actor ingress path
- further removal of legacy actor-side compatibility handling where the shared seam already exists

这样最符合当前 shared actor substrate 与 authority boundary。

#### 第二步：让 `L2/L3` 从 gateway-facing API 进入真正 runtime main path

当前已经有：

- `CharacterModelGateway`
- `CharacterModelRouter`
- `CharacterContextBuilder`
- `CharacterAgentL2Service.prepare_reasoning_request(...)`
- `CharacterAgentL2Service.map_reasoning_output(...)`
- `CharacterAgentL3Service.build_intent_plan(...)`
- planner-driven `character_agent_suggestion`

下一步不应重新设计这些 seams，而应把它们继续变成 runtime 主路径。

#### 第三步：把 `character_agent_execution` 继续收成主执行通道

当前已经有：

- `character_agent_execution`
- `actor_control_frames`，且 runtime payload 已带 `controller_source=agent`、`control_mode=agent_controlled`、`action`
- `presentation_plan`，且 runtime payload 已带 `focus_state` / `action_state` / `speech_state`
- Godot 侧 `BackendBridge -> LocalPresentationBus -> CharacterReplica` 主消费路径
- live backend + Godot main scene smoke 已验证 `raw_fact_event -> character_agent_execution -> CharacterReplica`，且 `character_agent_output(command_type)` 未回到 runtime 主路径
- `phase0` audit 现在会直接识别这条 runtime payload contract，并且当前主报告也已显式列出 `character_agent_execution_consumer=proved`；独立 `character-agent-execution` probe profile 仍作为更窄的专项证据面存在
- 另有独立 `character-agent-execution` harness profile，且现在通过专用 probe scene 在不混入其他 `phase0` gate 的情况下单独验证这条 execution seam，并证明 shared actor runtime 已消费并应用该 contract，同时直接证明收到的 payload 本体携带 `actor_control_frames` / `presentation_plan` / `action_request_bundle`
- `CharacterReplica` 当前会先经 `AgentControllerAdapter` 收敛 agent ingress，再经 `CharacterRuntimeState` 把 `presentation_plan` 收成 `CharacterPresentationInput`
- `CharacterRuntimeState` 现在直接从 `CharacterPresentationInput` 现算 agent execution side-effect plan，并由 `CharacterReplica` 把本地 `dialogue_role_state` / `interaction_role_state` / `focus_role_state` / `attention_role_state` 显式传给这个 plan
- `character_agent_output` 现在只保留在 `BackendBridge` / `LocalPresentationBus` 的静态兼容信号链上，`CharacterReplica` 不再连接旧 output handler
- `LocalPresentationBus` 的 debug 输出现在走显式 toggle：autotest / probe / `PHASE0_DEBUG_LOGGING=1` 会开启，默认 runtime 路径不再依赖永远常开的日志噪音
- `Phase0PlayerBridge` 的 program/autotest forcing state 与 locomotion mode state 现在都已拆进独立 helper，bridge 继续保留现有 callable surface，但其内联状态进一步缩薄

当前 interact bridge 已经去掉了 self-body 的重复兼容 ingest，并且默认 runtime 消息现在只落到 `character_agent_execution`；下一步应继续把其余 actor-side consumer 一起向这条更终态的 shared ingress/presentation seam 收敛，而不是把 bridge surface 再加厚。

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

## 10. 当前建议顺序

如果从当前 worktree 继续往前推进，我建议顺序是：

1. 继续扩大 `action_request` allowed classes，保持 settlement 仍归 `ESM`
2. 继续深化 `L2/L3` 的 `gateway/context/memory bundle` 模型消费，并收紧本地 fallback 语义
3. 继续把 `character_agent_execution` 作为 shared actor main ingress 收口，并收紧旧 `character_agent_output(command_type)` 兼容入口
4. 再补 richer dialogue/model/provider/output-policy surfaces

不要反过来先做：

- 大而全的持久化数据库层
- 复杂人格/长期博弈系统
- 脱离当前 demo loop 的通用 agent framework

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
