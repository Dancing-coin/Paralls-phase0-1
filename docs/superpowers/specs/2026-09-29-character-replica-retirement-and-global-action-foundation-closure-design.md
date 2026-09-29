# CharacterReplica 丝滑退役与动作底座全局收口设计

**日期：** 2026-09-29  
**状态：** awaiting-user-review  
**范围：** Phase 0 仓库内角色运行时、动作底座、兼容迁移与验收门禁

## 1. 目标

本设计的目标是让新动作底座在整个仓库内取代旧的 `CharacterReplica` 运行路径，并让
`CharacterReplica` 在不破坏现有场景、旧协议和验证入口的前提下平滑退出。

最终运行时必须只有一条正式角色路径：

```text
Player / Agent / Program
  -> CharacterControllerPort
  -> CharacterControlIntent
  -> CharacterActor
  -> ActorActionArbiter
  -> RoleAnimationController / MotionContributionComposer
  -> CharacterMotor
```

后端仍然拥有语义 authority、ActionAttempt 提交、ESM/Gameplay 结算和恢复事实；Godot
只拥有局部输入、身体运动和可视/音频呈现。任何本地脚本都不能直接声明命中、伤害、弹药、
库存、投射物或世界事实。

## 2. 当前问题

StreetCombatDemo 已证明新方案在一个正式动作场景内可运行，但全局替代仍未成立：

- 仓库仍有 `CharacterReplica` 兼容 caller、场景引用和 provider lookup；
- 旧路径仍可能直接承担位置、速度、动画或 embodied 状态行为；
- `CharacterMotor` 尚未被全局证明为唯一身体运动 owner；
- root motion 仍是 `hold / zero-envelope` 临时能力边界；
- 通用 ActionAttempt、Registry admission 和恢复/重放证据尚未覆盖全部角色 caller；
- 当前完整 pytest 为 `7671 collected / 7621 passed / 48 failed / 2 skipped / 103 warnings`；
- 因此动作底座系列的全局关闭门禁仍未满足。

## 3. 设计原则

### 3.1 单一正式运行时

`CharacterActor` 是正式 actor host。`CharacterReplica` 在迁移窗口内只能是兼容转发壳，
不能继续作为第二套角色运行时。

### 3.2 单一身体运动 owner

所有角色的速度、重力、朝向、碰撞、root-motion consumption 和 `move_and_slide()` 只能
由 `CharacterMotor` 完成。任何旧 caller 直接写 `global_position`、`velocity` 或调用
`move_and_slide()` 都必须迁移或被门禁拒绝。

### 3.3 语义输入优先

旧方法参数、网络 payload、agent execution 和 embodied command 都先转换为
`CharacterControlIntent`，再进入 arbiter。展示层不能把动作名称直接当作身体或世界事实。

### 3.4 兼容壳不复制逻辑

迁移窗口内保留旧方法名、信号和必要 NodePath，但壳体只能：

1. 校验旧参数；
2. 转换为标准 intent 或 presentation request；
3. 转发到 `CharacterActor`；
4. 转发只读状态和生命周期结果；
5. 记录 caller、scene、actor、method 和 migration batch。

壳体不得保留独立 Motor、动画 owner、authority writer、agent scheduler 或状态 truth。

### 3.5 证据先于关闭

每一批迁移都必须有静态、focused runtime 和必要的 Harness 证据。没有 fresh evidence，
不能宣布 caller 已迁移，也不能删除兼容壳。

## 4. 目标架构

### 4.1 输入与控制

- `CharacterControllerPort`：统一输入、agent、program 和兼容 API 的入口。
- `CharacterControlIntent`：确定性、可序列化、无 authority 字段的语义意图。
- `ActorActionArbiter`：处理优先级、锁定、取消、死亡、重复请求和冲突。
- `CharacterActor`：承载 actor identity、runtime ingress、intent 生命周期和 presentation binding。

### 4.2 身体与呈现

- `CharacterMotor`：唯一身体运动、碰撞和 root-motion consumption owner。
- `MotionContributionComposer`：合并 locomotion、root motion 和受限外部贡献，不能直接移动身体。
- `RoleAnimationController`：唯一动画状态、锁定、保持、取消和恢复 owner。
- `CharacterPresentationRuntime`：语义呈现适配器，不拥有 gameplay truth。
- `CharacterEmbodimentAssetRegistry`：动作包、骨架、资源 digest 和 capability admission 的唯一入口。

### 4.3 兼容边界

迁移期的调用链为：

```text
legacy caller
  -> CharacterReplica compatibility shell
  -> CharacterControllerPort adapter
  -> CharacterActor
```

新 caller 不得经由 `CharacterReplica`。当兼容调用计数归零且静态 caller 清单归零时，
兼容边界才可删除。

## 5. 迁移模型

### 5.1 调用者分类

所有引用分为五类，并为每个引用登记 owner、迁移目标、回退方式和验收证据：

1. **场景与节点引用**：`CharacterBase`、验证场景、集成场景和旧 `.tscn`。
2. **玩家与演示桥接**：`MainDemoController`、`PlayerShell`、`Phase0PlayerBridge`。
3. **身体与状态 provider**：`EmbodiedStateProvider`、`EmbodiedSkeletalStateProvider`、局部 perception。
4. **交互与动作 host**：ArchiveDoor、物理交互、验证探针和旧 action host。
5. **Agent / Siming / execution**：CharacterAgent execution、Siming delivery、NPC 和自主路径。

### 5.2 迁移状态机

每个 caller 必须按以下状态推进：

```text
inventoried
  -> adapter-ready
  -> dual-observed
  -> actor-only
  -> compatibility-zero
  -> retired
```

- `inventoried`：已登记真实 caller 和触发入口；
- `adapter-ready`：已具备标准 intent/presentation adapter；
- `dual-observed`：旧接口和新 actor 的结果已做对照观测，但只有 actor 写入事实；
- `actor-only`：正式运行只调用 `CharacterActor`；
- `compatibility-zero`：该 caller 的兼容调用计数为零；
- `retired`：旧引用、桥接方法和专属测试已删除或改成新契约。

任何阶段失败都只能回退到该 caller 上一个已验证状态，不能恢复旧的第二套运动或 authority owner。

## 6. 迁移顺序

### 阶段 A：冻结与基线

- 生成全仓库 `CharacterReplica` caller matrix；
- 为每个 caller 记录场景、方法、信号、状态读写、运动写入、authority 触点；
- 加入禁止新增 Replica caller 的静态检查；
- 固定新旧行为对照字段和证据格式；
- 将 StreetCombatDemo 作为新路径的已通过基线，不把它扩展成第二套实现。

### 阶段 B：兼容壳收缩

- 将 `CharacterReplica` 现有实现收缩为纯 forwarding shell；
- 旧 movement、animation、authority 和 agent scheduling 逻辑迁入 actor stack；
- 兼容方法保留原签名和结果语义；
- 所有兼容调用输出结构化计数和来源；
- 增加 strict mode：壳体一旦出现直接运动、动画或事实写入，测试立即失败。

### 阶段 C：分域迁移

按以下依赖顺序迁移：

1. 场景根节点、`CharacterBase` 和验证场景；
2. 玩家、MainDemo 和 Phase0 bridge；
3. embodied state/provider 和局部 perception；
4. ArchiveDoor、物理交互和验证 probe；
5. Agent、Siming、CharacterAgent execution 和 NPC；
6. 非 StreetCombatDemo 的旧演示和剩余脚本 caller。

每个域完成后必须满足：新 actor 运行结果可观察、旧 caller 只产生兼容转发、Motor/animation
没有第二 owner、authority 结果可以重放且重复请求不产生第二次写入。

### 阶段 D：能力与资源收口

- 所有动作包通过 Registry admission；
- skeleton、clip、marker、root profile 和 fallback 均有 digest 证据；
- root motion 从 `hold / zero-envelope` 进入真实测量、限幅和 Motor 消费；
- 未合格资源必须 fail closed，不得由旧 skin 或 Replica 直接兜底写入身体状态。

### 阶段 E：零兼容切换

- 所有场景实例切换至 `CharacterActor` 正式 host；
- provider、bridge、interaction host 和 verification probe 不再查找 Replica；
- 兼容调用计数为零；
- 静态 caller inventory 为零；
- 所有旧 NodePath、信号和 wrapper 依赖已迁移或删除；
- 新旧对照报告只保留为历史证据，不再作为运行时依赖。

### 阶段 F：删除与封存

只有在所有收口门禁通过后才删除：

- `scripts/character/CharacterReplica.gd`；
- `scenes/phase0/CharacterReplica.tscn`；
- `ValidationCharacterReplica.tscn` 及其专属 wrapper；
- 只服务旧壳的桥接方法、provider lookup 和迁移测试；
- 旧兼容文档中的现行说明。

历史文档可以保留，但必须明确标记为 historical/transitional，不能再被索引为执行入口。

## 7. 并行工作边界

并行执行只允许在文件和责任边界清晰时进行。建议分为以下独立 lane：

- **Lane 1：契约与 caller inventory**：静态清单、禁止新增规则、迁移状态表；
- **Lane 2：玩家与场景**：CharacterBase、MainDemo、PlayerShell、验证场景；
- **Lane 3：embodied 与交互**：providers、ArchiveDoor、物理 host、局部 perception；
- **Lane 4：Agent / Siming**：execution、delivery、NPC 和自主路径；
- **Lane 5：Motor / root motion / registry**：唯一 owner、能力 admission、真实 root 校准；
- **主控集成 lane**：跨 lane 冲突处理、回归、Harness 和最终删除。

各 lane 不得修改其他 lane 的 owner 文件；跨边界接口必须先更新契约和测试，再接入实现。

## 8. 回退与故障处理

- 回退单位是单个 caller batch，不是整个仓库；
- 回退只能恢复到最后一个 actor-backed 兼容状态；
- 不允许恢复旧的 direct movement、direct animation 或 local authority 写入；
- 任何双写、双 Motor、双 animation owner 或 authority divergence 都是 hard failure；
- 发现新失败时先保留当前证据，再按系统化诊断流程定位，不得用放宽门禁掩盖失败。

## 9. 验收门禁

### 9.1 静态门禁

- `CharacterReplica` 只存在于迁移历史或已批准的兼容测试中；
- 活跃场景、provider、bridge、interaction host 和 agent execution 无 Replica runtime lookup；
- 只有 `CharacterMotor` 能调用 `move_and_slide()` 或写入身体运动字段；
- 只有 `RoleAnimationController` 能提交动作状态；
- 只有后端 authority 能提交世界事实。

### 9.2 运行时门禁

- 玩家、Agent、Program、NPC 均通过统一 actor ingress；
- intent digest、arbiter、animation、Motor 和 authority 结果可关联；
- 重复、过期、取消、恢复和重连行为确定性一致；
- root motion 测量、限幅和消费有真实 runtime evidence；
- 兼容调用计数为零。

### 9.3 仓库级门禁

- 动作底座 focused tests 全绿；
- `python -m pytest -v` 全绿；
- `python scripts/verification/harness.py --profile street-combat` 通过；
- `python scripts/verification/harness.py --profile all` 通过；
- fresh evidence 与当前源码 digest 一致；
- `.harness/` 只保留契约和静态元数据，运行产物按仓库 retention 规则导出和清理。

## 10. 完成定义

只有同时满足以下条件，才可以宣布“新方案完美替代旧系统”并关闭动作底座系列：

1. 全仓库所有有效角色 caller 已进入 `CharacterActor` 主线；
2. `CharacterReplica` 没有活跃场景实例、runtime caller 或 provider lookup；
3. `CharacterMotor` 是全局唯一身体运动 owner；
4. `RoleAnimationController` 是全局唯一动作状态 owner；
5. root motion 已完成生产级校准并由 Motor 消费；
6. Registry admission、ActionAttempt authority、恢复和重放链路完整闭合；
7. 全套 focused、pytest 和 Harness 验证通过；
8. 兼容壳、旧场景和旧桥接已删除或仅作为明确的历史资料保留。

在上述条件全部满足前，StreetCombatDemo 只能被称为已通过的 pilot/acceptance slice，
不能被称为全局旧系统替代完成。
