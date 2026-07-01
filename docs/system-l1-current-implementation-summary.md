# System L1 当前实现总结

日期：`2026-06-18`

这份文档是当前仓库 `System L1` 的 repo-local 实现总结。

它不重复主项目理想架构，而是回答四件事：

1. 当前 `System L1` 到底已经实现到什么程度
2. 它现在能支撑什么真实能力
3. 一个完整案例在当前仓库里会怎样流转
4. 距离主项目理想态还差在哪

---

## 1. 一句话结论

当前仓库里的 `System L1` 已经不是“只有骨架的 demo 线”，而是：

- 有统一事实上抛出口
- 有 authority backend 结算
- 有最小角色私有感知入口
- 有运行时验证闭环

按当前 worktree 的 backend/doc/runtime 验证面，`System L1` 当前主链已成立，并且 broad Godot runtime profiles 已重新转绿。

但按主项目的 full-volume 理想态来看，它还不是最终生产级 `System L1`。

---

## 2. 当前完成状态

### 已经成立的部分

当前仓库的 `System L1` 已经具备：

- 统一 `raw_fact_event` 事实出口
- `player_input -> backend route -> result/runtime/siming` 的最小执行链
- 视觉事实系统
- 听觉 raw fact 最小链
- 触觉 / 热感 / 嗅觉 / 生理 / 角色状态这五类剩余 emitter
- `ESM` 的 deterministic 结算层
- `L1 -> candidate percept -> per-character filter -> character perceived` 的最小桥
- reconnect / zone reseed / privacy reseed / environment cycle runtime proof

### 已验证结果

当前 `2026-06-18` worktree 的关键验证结果：

- `python -m pytest -q` -> `616 passed`
- `python scripts/verification/harness.py --profile docs` -> `overall_docs_passed=True`
- `python scripts/verification/harness.py --profile character-agent-execution` -> `overall_character_agent_execution_passed=True`
- `python scripts/verification/verify_l1_runtime_edges.py` -> `overall_l1_runtime_edges_passed=True`
- `python scripts/verification/harness.py --profile phase0` -> `overall_strict_phase0_passed=True`
- `python scripts/verification/harness.py --profile phase1-slice` -> `overall_phase1_slice_passed=True`

当前 runtime verification path 还新增一条已落地 truth：

- `phase0` / `character-agent-execution` profile 现在会强制起 fresh backend，再收集 Godot runtime 证据，避免旧 backend 进程污染当前 worktree 的 runtime 验证
- `verify_phase0.py` 现在给主场景 autotest / focus-autotest 更宽的 `--quit-after` 窗口，以适配 fresh backend 启动后的连接确认与事实采样节奏
- `MainDemoController` 现在会把首次 `backend_connected` 之前的 `backend_closed:-1` 视为启动期断连噪音，但仍会补发一次自动重连，从而避免 `phase0` profile 在 fresh-backend 模式下停在首轮握手失败
- `verify_l1_runtime_edges.py` 当前已转成现行 runtime truth：`backend_connected`、初始 `zone bootstrap`、以及无 HTTPRequest overlap error 作为 hard-pass；旧 reconnect/privacy/environment edge probe 被 isolated，不再作为 hard-pass gate
- `verify_phase0.py` 当前也已去掉冗余的 `PHASE0_DEBUG_LOGGING=1` 强制注入；在保持 same-scene same-autotest path 的前提下，strict `phase0` broad runtime verification 已重新转绿
- `CharacterRuntimeState` 现在不再保留 `finalize_player_presentation_input()` 这层空转 bridge，formal presentation contract 直接沿 shared runtime-state / skin boundary 流转
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

---

## 3. 现在能做什么

### 3.1 玩家输入与执行

当前 `System L1` 已经能把这些玩家侧输入做成结构化执行消息：

- `move_intent`
- `focus_target_change`
- `dialogue_submit`
- `interact_intent`

这意味着当前仓库不再只是本地 Godot 动画或按钮逻辑，而是已经形成：

`player input -> backend route -> world/runtime response`

### 3.2 视觉层

当前已经成立的视觉事实面包括：

- `actor_looks_at_actor`
- `actor_looks_at_object`
- `actor_near_object`
- `environment_light_drop`
- `visual_evidence_projection`

这些事实不只是打印日志，而是会进入：

- backend authority
- runtime state projection
- candidate generation
- Siming 输出链

### 3.3 听觉层

当前听觉最小链已经成立：

- `speaker_active`
- `auditory_reachability_changed`
- `ambient_noise_changed`

但当前真实状态已经比这更进一步：

- `speaker_active`
- `auditory_reachability_changed`

这两类**定向**听觉事实现在已经可以进入：

- `CandidatePerceptEvent`
- `CharacterPerceivedEvent`
- 角色私有 `audible_entities`

仍然保持 system-level only 的是：

- `ambient_noise_changed`

所以当前准确状态不是“所有听觉都冻结在 `L1-only`”，而是：

- targeted actor-to-actor auditory facts 已进入 private percept path
- ambient environmental auditory context 仍保持 `L1-only`

当前角色执行边界还新增了一条已验证 truth：

- `character_agent_execution` 进入 Godot 后，`CharacterReplica` 先经 `AgentControllerAdapter` 收敛 ingress，再由 `CharacterRuntimeState` 直接从 `CharacterPresentationInput` 现算 side-effect plan
- 该 plan 现在显式接受 actor-local `dialogue_role_state` / `interaction_role_state` / `focus_role_state` / `attention_role_state` 配置，避免回退到硬编码默认 label

当前 Stage B 的 backend runtime 还额外明确了另一条 truth：

- `CharacterAgentRuntime` 会把 full-auto actor 的 `character_agent_execution_request` 写入 session timeline / memory
- `CharacterAgentRuntime` 现在也会把 `player_priority_assisted` actor 的 `character_agent_suggestion_packet` 写入 session timeline / memory
- `CharacterAgent L1` 的 private snapshot 现在也不再只停留在空默认值：定向/空间私有感知现在还能把 `attention_targets` / `current_attention_targets` / `short_horizon_social_presence` / `local_spatial_confidence_map` 填进 `CharacterPrivateWorldSnapshot`；低清晰度或低确定度的 unresolved 私有感知现在还会进入 `active_anomalies`，并把 `distraction_level` 从 `baseline` 抬到 `elevated`；司命最小 catalyst 现在也会把对应 actor 的 `vigilance_level` 从 `baseline` 抬到 `elevated`
- `CharacterWorkingMemoryState` 现在也已有 objectized state 入口，且不会破坏现有 `retrieval_bundle()` 形状：`CharacterWorkingMemory.build_state(...)` / `CharacterAgentMemoryStore.working_memory_state(...)` 已能按 actor 汇总 `recent_perceived_events` / `recent_esm_results` / `recent_siming_catalysts` / `private_snapshot`
- `CharacterContextBuilder` 现在也可选承接 objectized `working_memory_state`，同时不破坏原有 `memory_bundle` shape
- `CharacterAgentRuntime` 现在也已经把这条 objectized `working_memory_state` 送进 `L2/L3 -> gateway -> context_builder` 主链路，而不是只停留在 helper/state 层
- `CharacterPromptPolicy` 现在也开始消费这条 objectized `working_memory_state`：`user_instruction` 里会带上 `recent_perceived_events_count` / `recent_esm_results_count` / `recent_siming_catalysts_count` / `private_snapshot_actor_id`
- `CharacterPromptPolicy` 现在也开始消费 snapshot 内的 `last_siming_catalyst`，并把它压进 `user_instruction`
- `CharacterPromptPolicy` 现在也开始消费 snapshot 内的 `body_state_hints`，并把它以 `body_state_hints_count` 的形式压进 `user_instruction`
- `CharacterPromptPolicy` 现在也开始消费 snapshot 内的 `recent_world_changes` / `recent_constraint_results`，并把它们分别以 count + recent sample 形式压进 `user_instruction`
- `CharacterAgentRuntime` 现在也会把 snapshot 内的 `last_siming_catalyst` 送进 `CharacterAgentL2Service.prepare_reasoning_request(...)` 的 structured context
- `vigilance_level` 现在也不再只是停留在 `L1` private snapshot：离线 `L2` 在该值为 `elevated` 时会把 `opportunity_level` 提升到 `medium`
- `active_anomalies` 现在也不再只是停留在 `L1` private snapshot：离线 `L2` 在该列表非空时会把 `risk_level` 提升到 `medium`
- `distraction_level=elevated` 现在也不再只是停留在 `L1` private snapshot：离线 `L2` 在该值为 `elevated` 时会把 `ambiguity_level` 提升到 `medium`
- `body_state_hints` 现在也不再只是停留在 `L1` private snapshot：离线 `L2` 在该列表非空时会把 `interpretation_type` 视为 `body_state`，并把 `risk_level` 提升到 `medium`
- `recent_world_changes` / `recent_constraint_results` 现在也不再只是模型默认值：runtime 会在 settlement/dialogue writeback 时把 world-change / constraint 摘要回写到 snapshot 的短历史里
- `recent_constraint_results` 现在也不再只是停留在 snapshot 历史：离线 `L2` 在该列表非空时会把 `risk_level` 提升到 `medium`
- `recent_world_changes` 现在也不再只是停留在 snapshot 历史：离线 `L2` 在该列表非空时会把 `opportunity_level` 提升到 `medium`
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
- 但它的 perception / self-body / siming ingest 入口仍会返回 legacy `CharacterGoalCommand` 列表，说明 five-channel execution plan 和 legacy command compatibility 仍并存，而不是单一路径完全收口
- 这条兼容路径当前也带着最小 trace：
  - `CharacterGoalCommand.causation_id` / `correlation_id` 现在可从 `CharacterAgentL4Executor` 的 `actor_control_frames` 回流
  - `CharacterGoalCommand.role_state_hint` 现在会从 execution plan 的 request 语义回流
  - `CharacterGoalCommand.dialogue_text` 对 speech 类请求也会从 request `content` 或 `presentation_plan.speech_state.utterance_request` 回流

### 3.4 ESM 层

当前 `ESM` 已经能稳定处理：

- 交互成功
- 交互失败（constraint）
- 环境状态变化
- 状态机 transition
- coarse 环境场更新

当前 repo-local 已显式支持的环境请求包括：

- `light_level_drop`
- `light_level_restore`
- `thermal_level_rise`
- `smoke_density_rise`
- `noise_level_rise`

对不支持的请求，当前实现会明确拒绝，不会伪装成功。

### 3.5 角色私有输入侧

当前最小角色私有感知入口已经成立：

- `CandidatePerceptEvent`
- `PerCharacterPerceptFilter`
- `CharacterPerceivedEvent`
- `SelfBodyPerceivedEvent`

并且当前这条最小私有感知链已经不再只保留 summary string：

- `CharacterPerceivedEvent` 现在还会保留 `source_actor_id` / `target_actor_id` / `target_object_id` / `target_environment_id` / `distance_m`
- `spatial_access_fact` 进入 actor-private path 后，当前还能最小推进到 `attention_targets` / `current_attention_targets` / `short_horizon_social_presence` / `local_spatial_confidence_map`

这意味着当前仓库不再只有“系统知道发生了什么”，而是已经有：

- 某个角色会收到一条角色私有输入
- 某个角色会收到一条身体私有输入

---

## 4. 当前真实边界

### 4.1 `System L1` 已经足够的部分

如果目标是：

- 玩家控制 `PlayerCharacter`，其内嵌可见角色壳为 `CharacterReplica(actor_id=char_c)`
- `CharacterA/B` 作为其他角色壳存在
- 基于视觉事实形成最小互相感知
- 基于 authority 结果发生交互和反应

那么当前 `System L1` 已经够用。

### 4.2 `System L1` 还不够的部分

#### 听觉

听觉当前还没有**完整**进入角色私有感知。

代码里最关键的现实边界在：

- [backend/app/services/candidate_percept_service.py](/d:/Users/User/Documents/paralls-phase-0-demo/backend/app/services/candidate_percept_service.py)

当前行为现在分成两层：

- `speaker_active` / `auditory_reachability_changed`
  - 已进入 `CandidatePerceptEvent`
  - 已进入 `CharacterPerceivedEvent`
  - 已进入角色私有 `audible_entities`
- `ambient_noise_changed`
  - 仍保持 system-level only

所以当前缺的不是“完全没有私有听觉输入”，而是：

**还没有完整的 actor-private hearing 设计与 richer auditory interpretation。**

#### 视觉精度

视觉已经进了角色侧，但精度还比较粗。

当前问题不是视觉链不存在，而是：

- 过滤上下文较薄
- 还不是严格 LOS / 朝向 / 遮挡 / 几何裁剪系统

所以当前视觉是：

- 有最小闭环
- 但还不是生产级精细感知

### 4.3 角色智能体层还没完成的部分

更高层的角色智能体还没有完整实现，所以当前还做不到：

- 基于感知的复杂自主理解
- 稳定多轮自主交流
- 完整社会意义判断
- 多角色长期策略性互动

这些不完全是 `System L1` 的锅。

更准确地说：

- `System L1` 负责把事实、候选、结算和最小私有输入送到边界
- 角色智能体负责“真正听懂 / 看懂 / 形成动机 / 主动决策”

---

## 5. 一个当前仓库里真实成立的完整案例

下面这个案例是按当前代码真实能力推演的。

### 案例描述

玩家控制 `PlayerCharacter` 进入场景，其内嵌可见角色壳为 `CharacterReplica(actor_id=char_c)`；玩家先看向 `CharacterA`，再对 `A` 说话，然后转向桌上的 `obj_letter` 调查，交互成功后环境变化触发 `CharacterB` 的注意。

### 阶段 1：玩家进入并控制 `C`

- 玩家实际控制的是 `PlayerCharacter` 这个 `CharacterBase` 外壳，而其可见角色壳是内嵌的 `CharacterReplica(actor_id=char_c)`
- `A/B` 保持为 AI-driven shell
- `System L1` 持续处理：
  - `move_intent`
  - locomotion state
  - spatial access
  - 当前 focus

### 阶段 2：`C` 看向 `A`

- Godot 发出 `focus_target_change`
- 同时发出视觉事实：
  - `fixed_gaze_on_target`
  - `actor_looks_at_actor`

后端会：

- 更新 `C` 的 focus/runtime snapshot
- 基于视觉事实生成 candidate
- 将一条最小 `CharacterPerceivedEvent` 写给 `A`

### 阶段 3：`C` 对 `A` 说话

- 玩家发出 `dialogue_submit(target_actor_id="char_a")`
- backend `CharacterService` 返回 `dialogue_response(actor_id="char_a")`

于是形成：

- 玩家 `C -> A` 的显式交流
- `A` 的回应回到 Godot 表现层

### 阶段 4：听觉事实同时存在，但还只在系统层

如果当前对话链伴随听觉 raw fact：

- `speaker_active`
- `auditory_reachability_changed`
- `ambient_noise_changed`

那么当前系统会：

- 记录这些听觉事实
- 走 authority / verifier

但不会：

- 把它们编译成 candidate percept
- 把它们写成角色私有“我听到了什么”

### 阶段 5：`C` 调查 `obj_letter`

- 玩家靠近物体
- 发出 `actor_near_object`
- 玩家触发 `interact_intent`

`ESM` 会发出：

- `action_request`
- `action_resolution_result`
- `object_state_result`
- `body_state_result`
- `environment_state_result`
- `state_machine_transition`

Godot 侧还会继续发：

- `visual_evidence_projection`
- tactile fact
- thermal fact
- olfactory fact

### 阶段 6：`B` 被拉进注意链

物体状态和环境状态变化会进入：

- `ConversationRelationService`
- `CharacterRuntimeStateService`
- `SimingService`

结果是：

- `C` 自己的 runtime/candidate 会更新
- `B` 会收到一条 attention prompt
- 场景上会表现为“`B` 注意到了变化”

这就是当前仓库最真实的一条：

**玩家 -> 视觉感知 -> 交流 -> 交互 -> 世界结算 -> 他人注意**

的最小闭环。

---

## 6. 时序图

### 6.1 视觉主导的最小互感 -> 交流 -> 交互闭环

```text
玩家
  |
  v
PlayerCharacter / CharacterReplica(char_c)
  |
  | focus_target_change / move_intent / dialogue_submit / interact_intent
  v
PlayerIntentMapper / MainDemoController
  |
  | visual_fact / spatial_access_fact
  v
System L1 统一出口
  |
  v
backend/main.py
  |
  +--> SessionInputRouter
  |      - 接受 move/focus/interact/dialogue 路由
  |
  +--> ConversationRelationService
  |      - 维护 focus / visual / world relation
  |
  +--> CandidatePerceptService
  |      - visual_fact / spatial_access_fact -> candidate percept
  |
  +--> PerCharacterPerceptFilter
  |      - candidate -> CharacterPerceivedEvent
  |
  +--> CharacterPerceivedInputService
  |      - 写入 A 的私有感知输入
  |
  +--> CharacterRuntimeStateService
  |      - 生成 C 的 snapshot / delta
  |
  +--> CharacterService
  |      - 处理 A 的对话响应
  |
  +--> ESMService
  |      - 处理交互成功/失败和环境变化
  |
  +--> SimingService
         - 基于 visual/world/candidate 生成 attention prompt
```

### 6.2 听觉链当前到哪

```text
Godot AuditoryFactEmitter
  |
  v
raw_fact_event (auditory_fact)
  |
  v
backend authority route
  |
  +--> verifier / audit / debug proof
  |
  +--> candidate_percept_service
         - `speaker_active` / `auditory_reachability_changed` -> compile into candidate percepts
         - `ambient_noise_changed` -> stays `L1-only`
  |
  +--> CandidatePerceptEvent / CharacterPerceivedEvent / private `audible_entities`
  |
  x
ambient-only path does not continue into:
  - CandidatePerceptEvent
  - CharacterPerceivedEvent
  - conversation candidate
  - 角色私有“听到”输入
```

---

## 7. `room / scene / zone` 的当前实现情况

当前仓库里三者都存在，但成熟度不同。

### `room`

现在主要是：

- 顶层会话/容器标识
- 广泛出现在模型、消息、结果对象里

当前现实情况：

- 有这个字段
- 但还没有复杂的多房间 runtime 管理逻辑

### `scene`

现在主要是：

- 当前 Godot 场景上下文标识
- 用来稳定 envelope / state / result 的上下文

当前现实情况：

- 有结构意义
- 但还不是完整的多场景切换/迁移系统

### `zone`

`zone` 是三者里当前最像真实运行边界的一个。

当前已经真实承担：

- 当前区域标识
- `current_zone_id`
- `privacy_band`
- zone reseed
- privacy reseed
- 环境场按 zone 维度挂载

对应现实实现可以看：

- [backend/app/services/fact_handlers/spatial_access_fact_handler.py](/d:/Users/User/Documents/paralls-phase-0-demo/backend/app/services/fact_handlers/spatial_access_fact_handler.py)
- [backend/app/models/runtime_state.py](/d:/Users/User/Documents/paralls-phase-0-demo/backend/app/models/runtime_state.py)
- [scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd](/d:/Users/User/Documents/paralls-phase-0-demo/scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd)

当前默认上下文基本是：

- `room_id = "room_demo"`
- `scene_id = "scene_demo"`
- `zone_id = "zone_focus"`

所以大白话说：

- `room`：现在更像 ID 容器
- `scene`：现在更像场景标签
- `zone`：现在已经是最小可工作的空间边界单位

但三者都还不是主项目理想中的 full-volume 空间运行系统。

---

## 8. 理想态是什么

理想态的 `System L1` 会比当前版本更深：

- 视觉不是最小可验证 slice，而是更精细的几何/遮挡/朝向感知层
- 听觉不仅有 raw fact，还能进入 candidate percept 和角色私有输入
- `ESM` 不只是当前 coarse field / minimal workbench，而是更完整的 settlement matrix 和工作台
- `room / scene / zone` 不只是标识和最小边界，而是更完整的空间 runtime 拓扑
- 多感官到候选感知编译会有更完整、统一的策略

---

## 9. 当前差距总结

### 不是 `System L1` 的主要差距

这些更偏角色智能体未完整实现：

- 真正“听懂 / 看懂 / 形成社会理解”
- 多轮自主对话
- 稳定角色动机与策略
- 复杂角色间博弈

### 是 `System L1` 当前自己的差距

这些是 `System L1` 本身仍然没铺满的：

- 听觉没有进入角色私有感知
- 视觉过滤精度不高
- `ESM` 的工作台、模板丰富度、settlement breadth 仍是 repo-local 有界 slice
- `room / scene / zone` 还是最小运行上下文，不是完整空间系统

---

## 10. 未来实现建议

如果下一阶段继续沿着当前仓库推进，建议顺序是：

### 第一优先级

1. 把已落地的定向听觉 candidate/private-percept 链继续做强，而不是停留在最小 slice
2. 增加更完整的 hearing attribution / filtering context
3. 保持 `ambient_noise_changed` 的 system-level only 边界，直到 actor-private ambient hearing 设计成型

原因：

- 当前仓库已经具备最小视觉与定向听觉互感；下一步缺的是质量、归因与 richer interpretation，而不是从零接线

### 第二优先级

1. 让视觉 filter 的 context 变真实
2. 不再默认 `is_facing_target=True`
3. 逐步接入更真实的朝向 / 可见性 / 遮挡判断

### 第三优先级

1. 扩展 `ESM` settlement matrix
2. 丰富环境/对象模板
3. 扩展 workbench / replay / debug surface

### 第四优先级

1. 把 `room / scene / zone` 从上下文标签推进为真正空间 runtime
2. 做更明确的 zone topology / multi-zone propagation / multi-room boundary

---

## 11. 结语

当前仓库里的 `System L1` 已经完成了“从 demo 骨架到可信运行时层”的跃迁。

它现在已经足够支撑：

- 玩家控制一个角色
- 其他角色壳在同一世界里存在
- 基于视觉产生最小互感
- 基于 authority 做交流、交互、结算和反应

但如果目标是：

- 多角色智能体真正基于视觉和听觉都互相理解
- 并在复杂社会语境下自主交流与互动

那么下一步最关键的缺口不是重新写一套 `System L1`，
而是：

- 把听觉补进 `System L1` 角色私有感知链
- 把视觉感知精度做深
- 再把角色智能体层真正接起来
