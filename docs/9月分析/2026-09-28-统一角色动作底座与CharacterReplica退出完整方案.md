# 统一角色动作底座与 `CharacterReplica` 退出完整方案

日期：`2026-09-28`

状态：九月分析参考稿。其 CharacterReplica 兼容面、caller inventory 和退休门槛已吸收到
[角色动作底座渐进替代设计](../superpowers/specs/2026-09-28-character-action-foundation-series-completion-design.md)
及其执行计划；本文不再作为独立执行入口。正式执行以对应 spec、plan、测试和 Harness 证据为准。

## 方案结论

动作底座的目标不是增加几个动画，而是让玩家、CharacterAgent、程序控制和未来网络输入都进入同一套角色运行时。所有来源先进入统一 intent 和动作仲裁，再由唯一 `CharacterMotor` 执行身体运动，由唯一动画控制器负责表现，最后通过 `ActionAttempt` 进入后端 authority。

`CharacterReplica` 不作为最终角色实现继续扩张。它要退出活动运行时路径，正式入口统一为 `CharacterActor`；迁移的是旧实现和旧职责，角色身份、运行时状态、感知、目标和兼容接口不能丢失。

> 九月分析提议稿：用于记录方案和架构决策，不直接授权实现。正式执行入口保留在 [docs/superpowers/plans/2026-09-28-streetdemo-mode-action-foundation-improvement-plan.md](../superpowers/plans/2026-09-28-streetdemo-mode-action-foundation-improvement-plan.md)。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**目标：** 将成功 `streetdemo` 的单一动作驱动闭环提炼为正式动作底座，同时支持玩家、角色智能体和程序控制，并在一次迁移中让 `CharacterReplica` 退出所有活动运行时路径。

**架构：** 复用 `streetdemo` 的行为模型，而不是原样复制键盘脚本。所有控制来源先进入统一的 intent 接口，由 `CharacterActor` 每个物理帧仲裁并生成唯一最终动作状态；`CharacterMotor` 执行唯一身体位移；`RoleAnimationController` 执行唯一 AnimationTree 播放；`CharacterAssetPresentation` 只负责导入角色资产、骨架绑定和语义动作适配。活动场景直接使用 `CharacterActor`，旧 `CharacterReplica` 在迁移完成后只保留在仓库外备份或历史归档中。`StreetCombatDemo` 作为真实街区验收面。

**技术栈：** Godot 4.6 GDScript、`CharacterBody3D`、`AnimationTree`/`AnimationPlayer`、现有 GLB manifest、现有 Python backend authority、pytest、Godot headless probe、Harness。

**依据：** `docs/superpowers/specs/2026-09-28-character-action-foundation-series-completion-design.md`、`docs/superpowers/specs/2026-06-15-character-actor-architecture-optimization-design.md`。

## 全局约束

- `CharacterMotor` 是唯一的速度、重力、朝向、碰撞、根运动合成和 `move_and_slide()` owner。
- `RoleAnimationController` 是唯一的 AnimationTree/AnimationPlayer 播放 owner。
- `CharacterAssetPresentation` 不得写入角色身体变换，也不得直接暂停或重启底层 `AnimationPlayer` 来绕过控制器。
- 玩家、agent、program 使用同一个 `CharacterActor` substrate，只更换控制来源。
- 后端 ESM/Gameplay/Composite 继续拥有攻击命中、伤害、状态和其他世界后果的 authority。
- 外部动画先以 in-place/physics locomotion 作为稳定基线；真实根运动必须经过独立资格和 Motor 消费验证后才能启用。
- `CharacterReplica` 不得出现在活动场景、正式 runtime caller 或 StreetCombatDemo；迁移前保留一次性备份，迁移后从运行时代码树删除。
- `StreetCombatDemo` 是动作质量验收场景；灰盒和 `Unified3DIntegration` 只作兼容探针。

## 评审重点

- 同一物理帧只能产生一个最终 locomotion/action 状态，不能由场景、Actor、AssetPresentation 多方抢写。
- action lock 期间，输入、agent locomotion 或 backend 结果不能错误覆盖一次性动作。
- 行走和跑步必须同时改变动画状态和物理速度，且 Shift 输入必须通过运行时探针确认。
- 模型前向轴必须与 Actor 朝向一致，三个街区角色不能依靠未经说明的 180° 偏置获得不同语义。
- 玩家、agent、program 的动作请求必须经过同一仲裁和表现入口，不能重新产生玩家专用角色种类。

## 文件职责地图

- `scripts/street_combat/streetdemo.gd`：仅作为已验证的行为参考；实施后不再作为正式运行时入口。
- `scripts/character/CharacterControlIntent.gd`：新增，定义人类、agent、program 共用的 locomotion/action intent 数据。
- `scripts/character/CharacterActor.gd`：接收 intent、执行仲裁、生成唯一最终表现状态和 Motor command。
- `scripts/character/CharacterMotor.gd`：执行唯一物理命令；暂不改变其唯一位移 owner 边界。
- `scripts/character/RoleAnimationController.gd`：接收最终语义状态，负责 AnimationTree 状态、过渡、锁定、恢复和诊断。
- `scripts/character/CharacterAssetPresentation.gd`：通用导入角色资产表现适配器，负责 manifest、Skeleton3D、AnimationPlayer、clip alias 和动作实现；不包含街区专属逻辑。
- `scripts/street_combat/StreetCombatDemo.gd`：只采集玩家输入、提交 intent、处理相机和战斗协调，不直接选择动画 clip/state。
- `scenes/phase0/CharacterActor.tscn`：新增正式 actor scene；活动场景不再实例化 `CharacterReplica.tscn`。
- `scripts/character/CharacterReplica.gd`：仅作为迁移前备份来源，完成迁移后不再属于活动 runtime。
- `scripts/verification/StreetDemoModeProbe.gd`：新增，验证同一状态驱动在玩家、agent、动作锁、恢复、转向和跑步上的实际结果。
- `scripts/verification/tests/test_streetdemo_mode_static.py`：新增，固定控制入口、唯一 owner 和禁止直接 Skin 驱动的静态契约。
- `docs/character/streetdemo-mode-action-foundation.md`：新增，记录运行时链路、输入适配、状态优先级和故障诊断。

## 通用命名决策

- `StreetCharacterSkin` 改名为 `CharacterAssetPresentation`：它服务的是任意已准入的导入角色包，不只服务街区角色。
- 节点名统一为 `CharacterAssetPresentation`，脚本路径为 `res://scripts/character/CharacterAssetPresentation.gd`。
- `RoleAnimationController` 保留：它描述的是角色动画状态实现，不绑定街区、模型或具体资产包。
- `StreetCombatDemo` 保留为场景产品名；产品场景名不扩散到通用角色模块。
- 所有 manifest、动作 descriptor、骨架映射和 root profile 继续使用 `package_id` 作为资产身份，不用脚本类名表达资产来源。

## 实施任务

### Task 1：冻结 streetdemo 行为基线

**文件：**

- 创建：`docs/character/streetdemo-mode-action-foundation-baseline-2026-09-28.md`
- 创建：`scripts/verification/StreetDemoModeProbe.gd`
- 创建：`scripts/verification/tests/test_streetdemo_mode_static.py`

**接口：**

- 探针读取 `get_playback_state()`、`get_current_clip_name()`、`CharacterBody3D.velocity`、`global_position`、`animation_controller.is_locked()`。
- 探针覆盖 `streetdemo.tscn` 和 `StreetCombatDemo.tscn`，但只把后者作为最终验收目标。

- [ ] 记录当前 `streetdemo` 的 idle/walk/run/jump/boxing/sword 行为、速度、过渡和墙体碰撞结果。
- [ ] 记录当前 `StreetCombatDemo` 的三个角色状态树、模型旋转、玩家速度属性、输入动作名和 `CharacterReplica` 实例数量。
- [ ] 扫描所有活动场景、脚本、probe 和 adapter，建立 `CharacterReplica` 引用清单，作为退出门槛。
- [ ] 写静态测试，禁止 `StreetCombatDemo.gd` 直接调用 `CharacterAssetPresentation.play_*` 或 `RoleAnimationController`。
- [ ] 写静态测试，确认 active 场景只有 `CharacterMotor.gd` 调用 `move_and_slide()`。
- [ ] 运行静态测试和现有街区 headless probe，保存失败与通过输出作为迁移前基线。

### Task 2：一次性退出 CharacterReplica 活动路径

**文件：**

- 创建：`scenes/phase0/CharacterActor.tscn`
- 创建：`scripts/character/CharacterAssetPresentation.gd`
- 修改：`scenes/phase0/StreetCombatDemo.tscn`
- 修改：`scenes/phase0/CharacterReplica.tscn`
- 修改：所有 Task 1 清单中的活动 `CharacterReplica` caller
- 修改：`scripts/verification/CharacterReplicaConvergenceProbe.gd`
- 创建：`scripts/verification/CharacterReplicaRetirementProbe.gd`
- 归档：旧 `scripts/character/CharacterReplica.gd` 到 `archive/character-replica/2026-09-28/CharacterReplica.gd`

**接口：**

- `CharacterActor.tscn` 根节点类型为 `CharacterActor`，保留现有碰撞形状和公开 actor 属性。
- `CharacterAssetPresentation.gd` 提供现有 Skin 调用方所需的语义接口：`set_state`、`play_locomotion_state`、`play_action_state`、`consume_root_motion_delta`、诊断方法；这些接口内部只转发到统一 controller。

- [ ] 先复制旧 `CharacterReplica.gd` 到 `archive/character-replica/2026-09-28/CharacterReplica.gd`，记录路径和 SHA256；不删除任何用户备份。
- [ ] 将 `CharacterReplica.tscn` 的活动使用者全部迁移到 `scenes/phase0/CharacterActor.tscn`，包括 `StreetCombatDemo`、Phase 0 活动场景和 probe。
- [ ] 将所有 `StreetCharacterSkin.gd` 节点与脚本引用改为 `CharacterAssetPresentation.gd` 和 `CharacterAssetPresentation`。
- [ ] 将旧兼容方法转换为 `CharacterActor` 或 `CharacterControlIntent` 接口；不把转发逻辑重新放回 `CharacterReplica`。
- [ ] 运行 `CharacterReplicaRetirementProbe`，确认活动场景实例数为零、活动脚本引用数为零、唯一 `CharacterActor`/Motor/Animation controller 链路存在。
- [ ] 只有退休探针通过后，才从活动代码树删除 `CharacterReplica.gd`；历史文档中的旧引用改为迁移说明，不保留第二个可运行实现。

### Task 3：提炼统一控制意图

**文件：**

- 创建：`scripts/character/CharacterControlIntent.gd`
- 修改：`scripts/character/CharacterActor.gd`
- 修改：`scripts/street_combat/StreetCombatDemo.gd`
- 测试：`scripts/verification/tests/test_streetdemo_mode_static.py`

**接口：**

定义稳定的 intent 结构：

```gdscript
CharacterControlIntent.create(
    move_direction: Vector3,
    wants_run: bool,
    jump_type: StringName,
    action_id: StringName,
    source_kind: StringName,
    target_ref: StringName,
) -> Dictionary
```

`CharacterActor.submit_control_intent(intent: Dictionary) -> void` 只保存当前物理帧 intent；它不直接播放动画。

- [ ] 将 `streetdemo.gd` 的方向、跑步、跳跃和动作选择转换为 intent 语义，而不是复制 `Input` 读取逻辑到 Actor。
- [ ] 为玩家、agent、program 保留相同字段和默认值，缺失字段归一化为 idle/none。
- [ ] 让 `StreetCombatDemo.gd` 只提交玩家 intent；agent 请求继续从既有 execution contract 进入 Actor。
- [ ] 保留 `begin_embodied_control_frame()` 作为 `CharacterActor` 兼容适配，但让它内部转换为统一 intent，不再直接影响资产表现层。
- [ ] 写单元/静态测试，确认不同 source_kind 不会产生第二套状态机或第二个 Motor。

### Task 4：建立唯一最终状态解析器

**文件：**

- 创建：`scripts/character/CharacterPresentationState.gd`
- 修改：`scripts/character/CharacterActor.gd`
- 修改：`scripts/character/CharacterRuntimeState.gd`
- 修改：`scripts/character/ActorActionArbiter.gd`

**接口：**

```gdscript
CharacterActor.resolve_presentation_state() -> Dictionary
```

返回至少包含：`locomotion_state`、`action_state`、`action_locked`、`wants_run`、`facing_yaw`、`root_motion_policy`、`source_digest`。

- [ ] 固定优先级：death/stun > admitted action > jump > run > walk > idle。
- [ ] 规定同一物理帧只解析一次最终状态，并记录请求来源、拒绝原因和覆盖原因。
- [ ] 将 action lock、guard hold、one-shot recovery 都放进同一状态解析结果，不再由 `CharacterAssetPresentation` 自己维护另一套动作意图。
- [ ] 将跑步速度和跑步动画绑定到同一个 `wants_run`/gait 结果，避免“run clip + walk velocity”。
- [ ] 对未具备并行动作资格的 boxing/sword 保持 full-body exclusive，明确拒绝或排队 locomotion 覆盖。

### Task 5：把 streetdemo 的播放闭环接入 AnimationTree

**文件：**

- 修改：`scripts/character/RoleAnimationController.gd`
- 修改：`scripts/character/CharacterAssetPresentation.gd`
- 修改：`scripts/character/CharacterActor.gd`

**接口：**

```gdscript
RoleAnimationController.apply_presentation_state(state: Dictionary) -> Dictionary
CharacterAssetPresentation.apply_presentation_state(state: Dictionary) -> Dictionary
```

- [ ] 保留六个语义状态和 `0.18` 秒 cross-fade。
- [ ] 确保同一 `state + clip` 不重复 `travel()`，状态变化才切换。
- [ ] 让 one-shot、guard hold、cancel、recovery 全部由 controller 拥有。
- [ ] 移除或封装 AssetPresentation 中会产生第二套 action timer/恢复决策的路径；兼容 API 只能转换为语义请求。
- [ ] 缺少 AnimationTree、clip 或 manifest 时 fail-closed 到 idle/fallback，并输出诊断原因。

### Task 6：让 StreetCombatDemo 只做输入与场景协调

**文件：**

- 修改：`scripts/street_combat/StreetCombatDemo.gd`
- 修改：`scenes/phase0/StreetCombatDemo.tscn`
- 修改：`scripts/character/CharacterActor.gd`

- [ ] 用统一输入动作读取玩家方向和 Shift；增加运行时日志/探针确认 `phase0_run` 实际按下时为真。
- [ ] 去除场景脚本对 `play_locomotion_state()`、`set_state()`、AnimationTree 的直接调用。
- [ ] 保留相机、目标选择、战斗请求、HUD 和环境碰撞职责。
- [ ] 对齐三个角色的 forward-axis 约定，移除无来源的 180° `CharacterAssetPresentation` 偏置；若某个 GLB 确实需要修正，将其写入 manifest/binding profile，而不是散落在场景节点。
- [ ] 保持玩家 `move_speed=1.8`、`player_run_speed=4.8` 的基线，并验证 walk/run 的实际速度和动作一致。

### Task 7：接入角色智能体而不复制玩家脚本

**文件：**

- 修改：`scripts/character/CharacterActor.gd`
- 修改：`scripts/street_combat/StreetCombatCoordinator.gd`
- 创建：`scripts/verification/AgentStreetDemoModeProbe.gd`

- [ ] 将 agent 的移动、追击、停留、guard、boxing、sword 意图转换为同一 `CharacterControlIntent`。
- [ ] 保持 backend 只决定 authority 结果；本地 agent 只能提交 proposal/admitted action，不能本地宣布命中或伤害。
- [ ] 让 agent 与玩家共享 action lock、cancel、recovery 和 Motor 边界。
- [ ] 验证玩家和两个 agent 可以在同一场景中同时使用同一 AnimationTree 控制接口。
- [ ] 验证 agent 断线或 authority 拒绝时只恢复表现状态，不产生本地世界后果。

### Task 8：根运动保持独立迁移，不与闭环重构混调

**文件：**

- 修改：`scripts/character/RootMotionSampler.gd`
- 修改：`scripts/character/CharacterMotor.gd`
- 修改：`scripts/character/MotionContributionComposer.gd`
- 创建：`scripts/verification/StreetDemoRootMotionProbe.gd`

- [ ] 第一轮保持街区 manifest 的 `root_motion_policy=hold`，确认 in-place 动作闭环稳定。
- [ ] 只验证采样、清空、消费 token 和 zero-envelope 不位移，不在本任务中启用生产根运动。
- [ ] 第二轮单独测量 walking/running root track 的方向、距离、周期和 envelope。
- [ ] 只有测量通过后，才为单一 locomotion profile 开启 `drive_locomotion`，并证明不会叠加等价 velocity。
- [ ] 将根运动验收与动作驱动验收分开记录，避免用根运动问题掩盖状态驱动问题。

### Task 9：运行时验收与文档收敛

**文件：**

- 修改：`scripts/verification/CharacterReplicaConvergenceProbe.gd`
- 修改：`docs/character/character-action-foundation-current-state.md`
- 修改：`docs/character/character-action-foundation-operator-guide-and-index.md`
- 修改：`docs/character/character-replica-convergence.md`
- 创建：`docs/character/streetdemo-mode-action-foundation.md`
- 修改：`docs/INDEX.md`

- [ ] StreetCombatDemo 实机证明三个角色拥有 active AnimationTree、有效 binding、六状态、动作锁定和恢复。
- [ ] 实机证明玩家 walk/run 的速度差异、朝向一致、跳跃和攻击表现连续。
- [ ] 实机证明两个 agent 使用同一动作入口，并且 backend authority 结果仍正确映射到表现恢复。
- [ ] 静态证明不存在 StreetCombatDemo 场景级直接动画驱动，不存在 Motor 之外的活动 `move_and_slide()` owner。
- [ ] 文档明确区分：streetdemo 行为基线、正式 runtime 适配、根运动实验和 CharacterReplica 退休记录。
- [ ] 运行 `python -m pytest -v`、相关 Godot probe、`git diff --check`，再根据仓库门禁运行对应 Harness profile。

## 验收梯度

1. **静态入口门禁：** 场景脚本不直接驱动 Skin/AnimationTree；唯一 Motor owner 通过静态扫描。
2. **单角色闭环：** `streetdemo` 行为在 `StreetCombatDemo` 的真实角色和街区相机下复现。
3. **三角色共享：** 玩家、JK agent、T agent 使用同一语义控制入口和同一 AnimationTree controller。
4. **动作与 authority：** boxing/sword 的本地锁定、恢复、backend result 和重复/过期请求继续通过。
5. **根运动隔离：** 先证明 hold/in-place，再单独证明校准后的 root contribution。
6. **迁移完成：** 活动场景、probe、bridge 和 runtime caller 中不再存在 `CharacterReplica`，正式入口统一为 `CharacterActor`。

## 明确不做的事

- 不把 `streetdemo.gd` 原样复制为玩家专用角色脚本。
- 不在本计划中重写后端 authority、Siming 或世界运行时。
- 不直接修改 `.blend` 源文件。
- 不同时启用根运动、输入重构和全动作仲裁重写来混合验证。
- 不以灰盒或 `Unified3DIntegration` 场景作为动作质量验收。
- 不保留一个仍可被活动代码调用的 `CharacterReplica` 第二实现。

## 完成标准

本计划完成时，`StreetCombatDemo` 应满足：玩家、agent、program 可以通过不同控制来源进入同一动作底座；每帧只有一个最终动作状态和一个 Motor command；AnimationTree 播放连续、速度与动作一致；战斗 authority 边界不变；根运动可以独立开启和回滚；活动运行时不再存在 `CharacterReplica`，正式角色入口统一为 `CharacterActor`。

## 独立方案补充：目标、边界与退出条件

### 当前 Demo 的验证边界

现有 `StreetCombatDemo` 已证明三个 GLB 的骨骼绑定、核心 locomotion/action 播放、玩家与 agent 的 authority 战斗、duplicate/stale/recovery 和 HUD 链路。它是迁移基线和真实验收面，但不能单独证明整套动作底座已经完成。

仍需独立证明：

1. 活动代码中只有 `CharacterMotor` 写身体位移；
2. `RoleAnimationController` 是唯一 AnimationTree/AnimationPlayer 播放 owner；
3. 玩家、agent、program 使用同一个 intent 和仲裁器；
4. root motion 经过校准并由 Motor 只消费一次；
5. marker、Motor evidence、ActionAttempt、幂等和恢复链路闭合。

### `CharacterReplica` 迁移定义

必须迁移出去的职责：直接位置、速度和朝向写入；第二套移动逻辑；直接消费 root motion 改世界位移；第二套动作 timer、lock、recovery；raw clip 播放；玩家专用 agent 逻辑。

必须保留并迁移的能力：actor identity、runtime state、感知和目标、agent execution 接收、presentation input、authority request correlation、原有公开属性和兼容接口。

正式结构为：

```text
CharacterActor
├── CharacterControlIntent
├── ActorActionArbiter
├── CharacterRuntimeState
├── MotionContributionComposer
├── CharacterMotor
├── RoleAnimationController
├── RootMotionSampler
└── CharacterAssetPresentation
```

只有以下条件全部满足，才允许从活动运行时代码树移除 `CharacterReplica`：活动场景全部使用 `CharacterActor`；bridge、probe、adapter 和 backend-facing caller 不再依赖其具体实现；旧方法已转成 `CharacterActor` 或 `CharacterControlIntent` 接口；唯一身体位移 owner 是 `CharacterMotor`；唯一动画播放 owner 是 `RoleAnimationController`；退休探针确认活动实例和活动引用为零；旧实现已归档且不可被运行时加载。

### 交付顺序与回滚边界

1. 冻结 StreetCombatDemo 的动作、速度、碰撞、攻击、HUD 和 authority 基线；
2. 建立 `CharacterActor`，先保持 backend 协议不变；
3. 将玩家、agent、program 输入转换为 `CharacterControlIntent`；
4. 将 action lock、guard、one-shot、cancel、recovery 收敛到动画控制器；
5. 清理非 Motor 的身体位移路径；
6. 将街区 Skin 收敛为通用资产表现层；
7. 保留 ActionAttempt 的 marker、evidence、幂等、修订和恢复语义；
8. 运行退休探针后再移除活动 `CharacterReplica`；
9. 最后单独进行 root motion 校准和动作库正式入库。

第一轮继续使用 `root_motion_policy=hold`，不把动画迁移、碰撞修复和生产 root motion 混在同一次回归中。每个阶段必须能独立回滚。

### 最终验收证据

- 静态 owner 扫描：非 Motor 身体位移 owner 为零；
- 动画 owner 扫描：非 RoleAnimationController 的播放 owner 为零；
- Godot 运行时：三角色 Skeleton3D、AnimationTree、核心状态、锁定、恢复、转身、碰撞和 Motor command；
- Authority：拳击、剑击、duplicate、changed duplicate、stale revision、断线恢复；
- Agent：玩家和两个 agent 使用同一 intent、仲裁、表现和 Motor 边界；
- 资产：digest、canonical mapping、action descriptor、root profile 和 qualification report 一致；
- 文档：spec、plan、current-state、operator guide、九月分析和 Harness profile 一致。

单独通过 StreetCombatDemo 动画探针只能关闭动画 pilot，不能关闭整套动作底座计划。
