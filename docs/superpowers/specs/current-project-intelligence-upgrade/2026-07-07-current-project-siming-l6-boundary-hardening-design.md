# 当前项目 Siming / System L6 边界硬化设计

- 状态：`proposed`
- 日期：`2026-07-07`
- 上位规格：
  - `docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-intelligence-upgrade-master-design.md`
  - `docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-02-current-project-siming-global-situation-layer-design.md`
- 相关架构文档：
  - `docs/架构/运行时/模块/SystemL6事件总线.md`
  - `docs/架构/运行时/模块/Siming.md`
  - `docs/架构/运行时/运行时覆盖矩阵.md`

## 1. 背景

当前架构文档已经把职责边界分清：

- `System L6` 是 authority event bus、路由、回放和审计辅助基础设施。
- `Siming` 是全局态势和高层 catalyst 层。
- `ESM` 是 authority settlement owner。
- `System L1` 是事实、provider、PQF 和 projection 边界。
- `CharacterAgentRuntime` 才拥有角色认知、意图和执行语义。

当前实现已经具备这些入口：

- `backend/app/models/authority_event.py`
- `backend/app/services/authority_event_bus.py`
- `backend/app/services/frontend_authority_event_projection.py`
- `backend/app/services/siming_event_pipeline.py`
- `backend/app/services/siming_event_producer.py`
- `backend/app/services/siming_character_dispatch_adapter.py`
- `backend/app/services/siming_global_situation.py`
- `backend/app/services/siming_runtime.py`

但部分边界仍主要依赖命名、约定和局部测试：

- `AuthorityEvent.routing / ttl / durability` 还没有完整执行语义。
- `FrontendAuthorityEventProjector` 容易继续膨胀成事实上的 route 解释层。
- `Siming -> Character` 目前有 adapter，但缺少独立 catalyst contract。
- `SimingGlobalSituationLayer` 已存在，但还不是所有全局导演决策的主入口。

本设计的目标是在继续扩展 Siming director 行为前，先把这些边界硬化。

## 2. 目标

1. 为 `System L6` 增加最小可执行语义：
   - consumer identity
   - targeted routing
   - `replayable / reliable / realtime` durability 行为
   - `ttl` replay/list 过滤
2. 将 `FrontendAuthorityEventProjector` 固定为 frontend compatibility adapter，而不是 authority route owner。
3. 定义 `SimingCatalystInput`，作为 `Siming -> AI-controlled Character` 的唯一高层输入契约。
4. 禁止 Siming catalyst 携带低层执行、authority mutation、物理成功、私有记忆注入或角色意图选择字段。
5. 定义 player-controlled actor 的 `inner_prompt` 分支，让司命可以产生心理暗示或内心旁白，但只进入 frontend presentation / narration。
6. 让多角色、公平性、VLA advisory 和全局态势类 Siming 决策可追溯到 `SimingGlobalSituationSnapshot`。
7. 保持当前 `phase0` 最小 Siming reaction、`siming-backend-chain` 和 mainline runtime proof 不退化。

## 3. 非目标

- 不替换 in-memory authority event bus 为外部 broker。
- 不引入分布式顺序、死信队列、持久数据库或跨进程投递。
- 不改现有 Godot 场景行为；只允许为 player-facing `inner_prompt` 定义 presentation-only 出口。
- 不让 Siming 生成 `character_agent_execution`。
- 不让 Siming 生成 ESM settlement、world mutation 或 physical success claim。
- 不重做完整 CharacterAgent L1/L2/L3/L4 架构。

## 4. 设计判断

### 4.1 L6 先做执行语义，不做平台化

当前问题不是吞吐或分布式 transport，而是 `AuthorityEvent` envelope 字段还没有足够执行力。

因此第一阶段只补：

- consumer identity
- route match
- replay store
- ttl filtering
- durability gate

不引入外部消息系统。

### 4.2 Projector 只能做投影

`FrontendAuthorityEventProjector` 应继续负责：

- `world_result`
- `state_machine_transition`
- `conversation_candidate_event`
- `siming_output`

但它不应决定事件是否应该被投递给自己。这个判断属于 `System L6`。

### 4.3 Catalyst 是输入，不是命令

`SimingCatalystInput` 面向 AI-controlled actor，只允许表达：

- 注意力提示
- 事实显露
- 情境压力
- 机会提示
- 证据引用
- salience / reason scope
- 冲动暗示

它不允许表达：

- actor control frame
- action request bundle
- selected intent
- world mutation
- private memory patch
- physical success

角色 runtime 可以把 catalyst 作为感知、注意、警觉、解释上下文或 timeline 输入，但不能把它当成执行命令。

`impulse_hint` 是允许的第一版 catalyst type，但它是角色内在动机输入，不是行动命令。它支持三类 `impulse_axis`：

- `narrative`：推动角色更想揭露事实、靠近冲突、观察异常。
- `relation`：推动角色更想接近、躲避、试探、保护或质疑某个角色。
- `action`：推动角色更想执行某类行动，但最终是否执行仍由角色 runtime 决定。

`impulse_hint` 只能提高候选权重或影响解释上下文，不能指定最终 selected intent，不能携带 action request，不能绕过角色自己的 L2/L3/L4。第一版 `intensity` 硬上限为 `0.35`；超过上限时应拒绝并记录 audit，而不是静默 clamp。

Player-controlled actor 不使用 `impulse_hint` 进入 `CharacterAgentRuntime`。玩家角色的心理暗示使用 `inner_prompt` 分支，走 `FrontendAuthorityEventProjector -> Godot presentation / narration`，只作为体验层提示。

### 4.4 新的全局导演判断必须 situation-backed

当前 `SimingRuntime.tick()` 仍包含若干事件特化路径。它们可作为 Phase0 compatibility candidate 保留。

但新增加的全局导演能力必须走：

```text
public authority events / evidence refs
-> SimingGlobalSituationSnapshot
-> FairnessStateSnapshot
-> InterventionCandidate
-> policy / feasibility
-> siming.* AuthorityEvent
```

这样才能避免 Siming 继续长成 event-rule bundle。

## 5. 数据契约

### 5.1 `SimingCatalystInput`

AI-controlled actor 的推荐最小字段：

```text
catalyst_id
catalyst_type
impulse_axis
impulse_label
room_id / scene_id / zone_id
target_actor_id
target_object_id
target_environment_id
source_authority_event_id
situation_snapshot_id
presentation_hint
pressure_hint
salience_boost
intensity
reason_scope
evidence_refs
causation_id
correlation_id
producer_ts
```

允许的 `catalyst_type` 第一版集合：

```text
fact_reveal
attention_prompt
opportunity_hint
pressure_hint
impulse_hint
```

`impulse_hint` 还必须满足：

- `impulse_axis` 必须为 `narrative / relation / action` 之一。
- 至少有一个 `target_actor_id / target_object_id / target_environment_id / situation_snapshot_id`。
- 必须有 `evidence_refs`。
- `evidence_refs` 必须来自公开 authority event、world result、public fact、Siming global situation 或 VLA advisory。
- `intensity <= 0.35`。

禁止字段：

```text
actor_control_frames
action_request_bundle
character_agent_execution
physical_success
world_mutation
private_memory_patch
selected_intent
command_type
low_level_motion
```

### 5.2 `InnerPrompt`

Player-controlled actor 的心理暗示不进入 `CharacterAgentRuntime`，而是使用 frontend-facing `inner_prompt`。

推荐最小字段：

```text
prompt_id
prompt_type = inner_prompt
room_id / scene_id / zone_id
target_actor_id
source_authority_event_id
situation_snapshot_id
prompt_text
intensity
evidence_refs
player_facing = true
non_authoritative = true
presentation_effects
causation_id
correlation_id
producer_ts
```

`inner_prompt` 允许触发 presentation-only effect：

- narration text
- subtle audio cue
- screen vignette
- controller rumble
- short UI hint

`inner_prompt` 禁止：

- 修改角色位置
- 修改 focus target
- 自动触发 movement / interact input
- 改 object / environment state
- 生成 backend action request
- 写 authority event truth
- 携带 action / command / focus mutation 字段

`inner_prompt` 必须有 `situation_snapshot_id` 或 `evidence_refs`，`intensity <= 0.35`，并且展示语气必须是感受、直觉或心理暗示，不能表达为系统命令。

### 5.3 L6 consumer identity

推荐第一阶段 consumer identity：

```text
siming
frontend_projector
audit
verification
```

现有 `routing.target_ids` 可以继续使用字符串列表，但 bus 必须把 consumer identity 与 target 做匹配。

### 5.4 Durability

推荐第一阶段语义：

- `replayable`：进入 in-memory replay store，可被 replay/list current 查询返回。
- `reliable`：进入 store 或 audit-visible trace，但不要求作为 runtime replay 主路径。
- `realtime`：只投递给当前 consumer，不进入 replay。

### 5.5 TTL

第一阶段只要求：

- replay/list current 查询过滤过期事件。
- 不要求后台清理线程。
- 不要求从 audit evidence 中物理删除过期事件。

## 6. 验证要求

必须新增或扩展测试证明：

- `target_ids=["siming"]` 不会投递给 `frontend_projector`。
- `replayable` 事件可 replay。
- `realtime` 事件不可 replay。
- 过期 `ttl` 事件不会作为 current replay 返回。
- `siming.fact_reveal` 可转成 `SimingCatalystInput`。
- `siming.impulse` 面向 AI-controlled actor 时可转成 `SimingCatalystInput(catalyst_type="impulse_hint")`。
- `impulse_hint` 支持 `narrative / relation / action` 三类 `impulse_axis`。
- `impulse_hint.intensity > 0.35` 时被拒绝并产生 audit。
- `impulse_hint` 缺少 target 或 evidence 时被拒绝。
- player-controlled actor 的心理暗示转成 `inner_prompt`，只走 frontend presentation / narration。
- `inner_prompt` 可以触发 presentation-only effect，但不能修改输入、focus、世界状态或 backend action request。
- `siming.visual_observability_request` 不进入 character runtime。
- 含 forbidden 字段的 catalyst payload 被拒绝。
- global situation 拒绝 `character_mm:` / `character_private` 输入。
- VLA advisory conflict 只记录 conflict refs，不覆盖 authoritative evidence。
- 现有 Phase0 最小 Siming reaction 不退化。

## 7. 推荐实施顺序

1. 先实现 `SimingCatalystInput` 和 adapter validation。
2. 再实现 L6 consumer identity、routing、durability、ttl 和 replay。
3. 再把新全局 Siming 决策接到 `SimingGlobalSituationSnapshot` provenance。
4. 最后更新运行时架构文档和 harness 证据说明。

## 8. 一句话收束

这次边界硬化不是扩展 Siming 能力，而是先把 `System L6`、`SimingGlobalSituation` 和 `Siming -> Character` 的运行时合同钉牢，防止后续导演能力把事件总线、角色脑和 authority settlement 重新揉在一起。
