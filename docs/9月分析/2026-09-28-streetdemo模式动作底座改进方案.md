# Streetdemo 驱动动作底座方案修订与现状

日期：`2026-09-28`

状态：修订方案，执行入口见：

- [渐进替代设计](../superpowers/specs/2026-09-28-character-action-foundation-series-completion-design.md)
- [渐进替代实施计划](../superpowers/plans/2026-09-28-streetdemo-mode-action-foundation-improvement-plan.md)

## 一、修订结论

原始 `streetdemo.gd` 只能证明动作表现 pilot，不能直接替代旧角色系统。正式路线改为：

```text
Streetdemo 行为来源
  -> CharacterActor 正式运行时
  -> 统一 intent / Arbiter
  -> RoleAnimationController
  -> CharacterMotor
  -> Registry / qualified realization
  -> authority
```

`CharacterReplica` 在迁移期间保留为只转发的兼容壳，所有 caller、场景、probe 和 authority 链路迁移完成后才退休。

## 二、三个方案的最终分工

| 文档 | 最终职责 |
| --- | --- |
| Streetdemo 改进方案 | 当前实施路线和行为来源 |
| 统一角色底座与 Replica 退出方案 | 兼容面、迁移顺序和退休门槛 |
| 动作底座通用化重构方案 | 长期架构约束、资产准入、BodyProfile、capability 和 root motion 规则 |
| 统一动作库与骨架适配讨论 | 动作索引、骨架 realization、身材校准和 IK 规则 |

不再把四份文档当作互相竞争的实现方案，而是把它们分成实施、迁移、架构和资产四层。

## 三、动作底座当前状态

### 已完成或已有 fresh 局部证据

- Streetdemo 单角色 AnimationTree pilot；
- 三个街区角色的核心状态和动作资产接缝；
- `CharacterActor` 中已有部分旧行为实现；
- `RoleAnimationController` 和 `RootMotionSampler` 已存在；
- CharacterMotor 已具备 command 和 root-exclusive 接缝；
- semantic action、Registry、RolePresentationAdapter 已有部分基础；
- 旧 authority 测试和 StreetCombatDemo backend 链路仍存在。

### 已落地但不能视为关闭的迁移接缝

- `CharacterReplica` 已继承 `CharacterActor`，但仍被活动场景实例化；
- 旧兼容方法已部分转发到 `CharacterActor`；
- StreetCombatDemo 仍调用 `begin_embodied_control_frame()`；
- StreetCharacterSkin 仍保留第二套 action lock/recovery；
- StreetCharacterSkin 仍存在 manifest 旁路解析；
- 新旧静态契约仍不完全一致。

### 尚未关闭的门

1. **Animation ownership gate**：Skin 和 controller 仍有重复状态。
2. **Motor ownership gate**：新 demo 和 StreetCombatDemo 仍存在场景级 velocity 写入。
3. **Intent convergence gate**：player、agent、program 尚未完全统一到同一 intent。
4. **Scene migration gate**：StreetCombatDemo 仍实例化 CharacterReplica。
5. **Replica retirement gate**：caller inventory、退休探针和归档条件尚未闭合。
6. **Asset admission gate**：正式 Skin 仍有直接 manifest/clip 路径。
7. **Root motion gate**：真实 root motion 尚未完成校准和生产准入。
8. **Authority closure gate**：新动作入口尚未完全进入统一 ActionAttempt 链路。
9. **Documentation/Harness gate**：spec、plan、current-state 和 fresh evidence 尚未全部一致。

## 四、验证现状

局部静态测试：

```text
test_streetdemo_copy.py
test_character_replica_convergence_static.py
test_street_combat_scene.py
结果：8 passed
```

更广的 Actor、Motor、Controller 和场景契约测试：

```text
53 passed, 11 failed
```

失败集中在旧的 `CharacterReplica` 静态契约，说明代码、测试和迁移目标尚未统一。它们不是“方案已经关闭”的证据。

本轮完成的是方案和执行计划修订，没有执行代码迁移，也没有新增 Godot runtime evidence。

## 五、关闭判断

当前状态：

> **动作底座 pilot：已落地。**
> **CharacterActor 迁移接缝：部分落地。**
> **旧系统替代：未完成。**
> **CharacterReplica 退休：未完成。**
> **通用动作底座：未完成。**
> **动作底座相关方案：不能关闭。**

只有渐进替代计划中的所有 gate 都有 fresh evidence，才能把动作底座相关方案统一标记为 closed。
