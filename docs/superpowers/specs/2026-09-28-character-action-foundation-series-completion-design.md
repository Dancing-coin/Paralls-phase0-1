# 角色动作底座渐进替代设计

> Status: awaiting-user-review
> Date: 2026-09-28
> Scope: 用已验证的 Streetdemo 动作闭环，渐进替代旧角色运行时；保留可回滚的 CharacterReplica 兼容层，直到所有旧调用方、场景、探针和 authority 链路完成迁移。

## 1. 决策摘要

原始 `streetdemo.gd` 是动作表现 pilot，不是旧角色系统的完整替代品。它证明了外部角色资产可以通过 AnimationTree 播放 idle、walk、run、jump、boxing 和 sword_attack，但仍直接写 `velocity`、调用 `move_and_slide()`，也不包含感知、事实发射、agent execution、交互、authority 和旧场景兼容。

正式路线采用三层合并：

1. **Streetdemo 提供行为来源**：保留已经跑通的动画状态、动作锁、速度基线和可见验收场景。
2. **CharacterActor 提供正式运行时**：所有控制来源进入同一 intent、仲裁、表现和 Motor 链路。
3. **CharacterReplica 提供迁移兼容**：只转发旧接口，不再增加行为；确认所有调用方迁移后才退休。

本设计不授权直接删除旧系统，也不把原始 Streetdemo 场景直接升级为正式运行时。

## 2. 替代定义

“替代完成”不是只证明动画能播放，而是同时满足：

- 旧调用方的公开行为合同已映射到新接口；
- 玩家、agent、program 使用同一控制入口；
- 只有 CharacterMotor 写身体运动；
- 只有 RoleAnimationController 管理动画状态、锁定和恢复；
- 资产都经过 Registry 和 qualification admission；
- backend authority、幂等、修订和恢复语义不变；
- 活动场景不再实例化 CharacterReplica；
- fresh static、Godot、backend 和 Harness evidence 全部闭合。

在这些条件完成前，系统状态只能称为“新动作底座与旧运行时共存”。

## 3. 目标运行时

```text
human / agent / program
        |
        v
CharacterControllerPort
        |
        v
CharacterControlIntent
        |
        v
ActorActionArbiter
        |
        v
CharacterRuntimeState / PresentationInput
        |
        +--> RoleAnimationController
        |       |
        |       +--> animation state, lock, hold, cancel, recovery
        |       +--> marker observations
        |
        +--> MotionContributionComposer
                |
                +--> CharacterMotor
                        |
                        +--> velocity, gravity, facing, collision,
                             root contribution consumption, move_and_slide
        |
        v
ActionAttempt candidate
        |
        v
ESM / Gameplay / Composite authority
        |
        v
AuthorityResult -> local projection and recovery
```

资产表现层只负责：

- package manifest；
- skeleton binding；
- semantic action realization；
- AnimationTree/AnimationPlayer 绑定；
- marker 和 root contribution 采样。

资产表现层禁止写 actor transform、velocity、damage、inventory、status 或 authority result。

## 4. 分阶段迁移

### 阶段 0：冻结基线和 caller inventory

不改变产品行为，记录旧运行时的：

- 玩家移动、跑步、跳跃；
- boxing、sword、guard、cancel、recovery；
- agent execution；
- perception 和事实发射；
- ArchiveDoor/right-hand reach；
- authority commit、duplicate、changed duplicate、stale revision 和 reconnect；
- 所有 CharacterReplica 场景、脚本、probe、bridge 和 adapter caller。

输出：

- old/new caller matrix；
- StreetCombatDemo 行为基线；
- Motor 和 Animation owner 扫描；
- 旧接口到新接口的映射表。

### 阶段 1：替换动作表现层

保留 CharacterReplica 场景和旧公开方法。将 Streetdemo 已验证的状态播放接入 RoleAnimationController 和 RootMotionSampler。

本阶段不做：

- CharacterReplica 删除；
- 真实 root motion；
- authority 协议重写；
- agent execution 协议重写；
- package-specific capability 大迁移。

退出条件：

- 六个状态在三个街区角色上可播放；
- action lock、guard hold、cancel、recovery 有 fresh Godot evidence；
- StreetCharacterSkin 不再直接暂停或重启 AnimationPlayer；
- 表现层不写身体运动。

### 阶段 2：统一控制入口和唯一 owner

新增稳定的 `CharacterControlIntent`：

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

`CharacterActor.submit_control_intent(intent)` 只接收当前物理帧意图，不直接播放 clip。

旧方法改为适配器：

- `begin_embodied_control_frame()`
- `apply_embodied_pose_sync()`
- `perform_action()`
- `play_reviewed_action_atom()`

本阶段必须删除场景脚本直接写 velocity 的路径，并把跳跃、跑步、朝向和 root contribution 交给 Motor command。

退出条件：

- player、agent、program 走同一 ControllerPort -> Arbiter -> Composer -> Motor；
- active GDScript 中只有 CharacterMotor 调用 `move_and_slide()`；
- 同一物理帧只有一个最终表现状态和一个 PhysicsMotionCommand。

### 阶段 3：统一动画锁定和表现适配器

StreetCharacterSkin 先作为薄适配器存在，负责：

- package 绑定；
- skeleton 查询；
- semantic action 转发；
- diagnostics。

它不再保留第二套：

- action timer；
- action lock；
- recovery 决策；
- raw clip 状态机。

需要时再将它改名为 CharacterAssetPresentation，但改名必须晚于行为和调用方迁移。

退出条件：

- lock、hold、cancel、recovery 只有一个 owner；
- 动作结束后恢复到当前有效 locomotion，而不是固定回 idle；
- player 和 agent 的恢复结果一致。

### 阶段 4：迁移场景和旧入口

创建 `scenes/phase0/CharacterActor.tscn)，按顺序迁移：

1. StreetCombatDemo；
2. Phase 0 player bridge；
3. agent execution probe；
4. interaction probe；
5. backend-facing adapter；
6. 其他活动场景和 editor tooling。

CharacterReplica 只保留兼容转发。退休前必须满足：

- active scene 实例数为零；
- active script 引用数为零；
- probe 不依赖具体 Replica 实现；
- 所有旧公开方法都有新接口映射；
- 兼容壳不拥有身体位移、动画播放、感知、交互或 authority 逻辑；
- 旧实现已归档且不能被正式运行时加载。

### 阶段 5：统一资产准入和动作索引

正式运行时统一使用：

```text
package_id + semantic_action_id
    -> CharacterEmbodimentAssetRegistry
    -> qualified realization profile
    -> CharacterAssetPresentation
    -> RoleAnimationController
```

必须支持：

- canonical skeleton mapping；
- body profile；
- motion style；
- realization profile；
- qualification report；
- fallback reason；
- rejected package fail-closed。

数字索引只能作为缓存或序列化优化，不能作为业务唯一标识。

### 阶段 6：root motion、能力模块和 authority 收口

Root motion 顺序固定为：

1. hold；
2. zero-envelope；
3. 单次采样；
4. 单次 Composer 去重；
5. 单次 Motor 消费；
6. walking/running calibration；
7. 单一 locomotion profile 开启真实 root motion。

能力模块按 package/capability 注册，不在通用 Actor 中增加 Knight、ArchiveDoor 或 package_id 分支。

authority 必须重新证明：

- marker + Motor evidence 形成一个 ActionAttempt；
- duplicate 返回原结果；
- changed duplicate 拒绝；
- stale revision 零写入；
- reconnect 后清除旧 lease/prediction；
- backend 仍是世界后果 authority。

## 5. 兼容性原则

迁移期间必须保持：

- actor identity；
- runtime state；
- perception；
- target resolution；
- agent execution 接收；
- presentation input；
- authority request correlation；
- 原有公开属性；
- 旧 probe 可识别的最小节点和方法表。

兼容层不得新增行为。所有新功能必须进入 CharacterActor、ControllerPort、Arbiter、PresentationRuntime 或 Motor。

## 6. 验收矩阵

### 6.1 API 等价

旧方法与新接口对输入、输出、失败码、锁定和恢复行为有明确映射。

### 6.2 行为等价

玩家、agent、program 对同一 intent 产生一致的：

- locomotion state；
- action state；
- facing；
- velocity；
- lock/recovery；
- Motor command。

### 6.3 场景等价

感知、事实发射、对话、司命、交互、HUD 和 authority 链路继续工作。

### 6.4 所有权等价

- 非 Motor 身体 writer 为零；
- 非 RoleAnimationController 播放 owner 为零；
- root contribution 每 tick 只消费一次；
- asset admission 没有旁路。

### 6.5 证据等价

必须有 fresh：

- focused pytest；
- Godot StreetCombatDemo runtime evidence；
- backend authority evidence；
- relevant Harness profile；
- 文档和索引一致性检查。

## 7. 明确不做

- 不把原始 streetdemo.gd 直接复制为正式玩家脚本；
- 不在第一阶段启用生产 root motion；
- 不在表现迁移阶段重写 backend authority；
- 不在所有 caller 迁移前删除 CharacterReplica；
- 不用旧报告替代本轮 evidence；
- 不把“六个动画状态通过”描述为“动作底座完成”。

## 8. 关闭条件

动作底座相关方案只有在以下条件全部满足后才能关闭：

1. Streetdemo pilot gate 已关闭；
2. CharacterActor runtime gate 已关闭；
3. Motor ownership gate 已关闭；
4. Animation ownership gate 已关闭；
5. Replica retirement gate 已关闭；
6. Asset admission gate 已关闭；
7. Authority/recovery gate 已关闭；
8. Documentation/Harness gate 已关闭。

任何一个 gate 未关闭，动作底座工作都应标记为“进行中”或“部分完成”。
