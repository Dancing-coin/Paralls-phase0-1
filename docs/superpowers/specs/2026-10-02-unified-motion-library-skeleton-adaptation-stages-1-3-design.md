# 统一动作库与角色骨架适配阶段 1–3 设计

> Status: awaiting-user-review
> Date: 2026-10-02
> Scope: 为当前 `CharacterActor` / StreetCombat 角色运行时建立“骨架标准 -> 中央动作库 -> 角色包 -> 动作实现”的三阶段基础。阶段 1–3 只覆盖资产契约、中央 `AnimationLibrary` 运行时接入和构建时/缓存式重定向，不扩展到多人身体同步、运行时原始姿态复制或完整通用 IK 系统。

## 1. 决策摘要

当前三个 StreetCombat 角色已经可以使用统一的 `walking2`，并且每个角色都能运行六状态动画树：`idle`、`walk`、`run`、`jump`、`boxing`、`sword_attack`。当前实现把动作复制或烘焙到各自 GLB，再通过 manifest 和 `RoleAnimationController` 解析；它证明了动作控制和骨骼映射可行，但仍然存在动作数据重复。

本设计把目标拆成三个可独立验收的阶段：

1. **中央资产契约**：冻结 `SkeletonProfile`、`MotionLibrary`、`CharacterPackage`、`MotionRealization` 和资格化 manifest；建立 `humanoid.v1` 六状态中央库。
2. **共享库运行时**：让三个角色挂载同一份中央 `AnimationLibrary`，由 Registry 按语义动作选择 realization；GLB 内动作只作为显式迁移 fallback。
3. **重定向基础**：建立构建时或缓存式 `retargeted_library` 生成、校验和注册入口，支持不同身材和第二个骨架标准；不在游戏关键帧中生成未经验证的轨道。

设计原则：

- 业务调用使用稳定的 `semantic_action_id`，不直接使用 raw clip 名称。
- 骨架兼容由 `SkeletonProfile`、轨道路径、rest pose、单位和轴向共同证明。
- `CharacterActor` 只接收语义动作请求；`AnimationTree` 负责姿态表现；`CharacterMotor` 是身体位移和碰撞的唯一写入点。
- 动作库只产生表现和 marker 观察，不能写世界真相、伤害、库存、最终 Transform 或 Velocity。
- 过渡阶段允许 fallback，但 fallback 必须在 manifest 中显式声明并可回滚。

## 2. 当前状态和问题边界

### 2.1 已存在的能力

- `CharacterEmbodimentAssetRegistry` 已有动作资产注册、资格化包接纳、语义动作解析和 fallback 入口。
- `StreetCharacterSkin` 已统一绑定 `AnimationPlayer`、`Skeleton3D`、`RoleAnimationController`、`AnimationTree` 和 `RootMotionSampler`。
- 三个 StreetCombat 角色的 manifest 已将 `clip_aliases.walk_forward` 和 `locomotion_map.walk_forward` 指向 `walking2`。
- 现有 `CharacterActor` / `CharacterMotor` 控制链能保持玩家、agent 和程序控制的统一入口。

### 2.2 尚未存在的能力

- 独立于角色 GLB 的中央 `AnimationLibrary` 资源。
- 版本化 `SkeletonProfile` 注册表和中央 `MotionLibrary` manifest。
- 角色包到中央库的 `shared_library` / `retargeted_library` realization 解析。
- 可重复的构建时重定向工具、缓存索引和目标骨架资格化报告。

### 2.3 不把当前状态描述为完成的理由

三个 GLB 都拥有动作数据，并不等于它们共享同一份中央资源。只有当三个角色的 `AnimationPlayer` 或表现壳挂载同一份 `AnimationLibrary`，且六状态运行时探针通过，才可宣称阶段 2 完成。只有当不同骨架的重定向输出通过骨骼、接触、root motion 和运行时检查，才可宣称阶段 3 完成。

## 3. 目标架构

```text
SkeletonProfile: humanoid.v1
    骨骼语义、拓扑、rest pose、单位、轴向、挂点和版本
            |
            v
MotionLibrary: motionlib:humanoid.v1.core@1
    中央 AnimationLibrary + 语义动作清单 + 资格化报告
            |
            +--------------------+
            v                    v
CharacterPackage               MotionRealization
角色网格、骨架映射、           shared_library /
BodyProfile、IKProfile         retargeted_library /
挂点和碰撞体                   package_native / fallback
            |                    |
            +---------+----------+
                      v
CharacterActor -> CharacterPresentationRuntime -> AnimationTree
              \-> CharacterMotor -> 位移、碰撞和 root contribution
```

运行时解析方向：

```text
ControllerPort / Agent intent
    -> semantic ActionRequest
    -> CharacterEmbodimentAssetRegistry
    -> MotionRealization
    -> CharacterPresentationRuntime
    -> AnimationTree
```

## 4. 核心契约

### 4.1 `SkeletonProfile`

`SkeletonProfile` 是版本化的骨架标准，不是模型文件目录。最小字段如下：

```json
{
  "skeleton_profile_id": "humanoid.v1",
  "version": 1,
  "canonical_bones": {
    "root": "root",
    "pelvis": "pelvis",
    "spine_lower": "spine_01",
    "spine_upper": "spine_03",
    "head": "head",
    "hand_l": "hand_l",
    "hand_r": "hand_r",
    "foot_l": "foot_l",
    "foot_r": "foot_r"
  },
  "hierarchy_digest": "sha256:...",
  "rest_pose": "humanoid_v1_rest",
  "unit_scale": 1.0,
  "forward_axis": "+Z",
  "root_motion_policy": "motor_owned",
  "socket_profile": "humanoid.v1.sockets@1"
}
```

骨骼名称可由角色导入映射到 canonical bone ID；动作轨道必须最终落到稳定的相对路径或通过登记的 remap 解析。骨架 profile 版本变化必须触发重新资格化。

### 4.2 `MotionLibrary`

一个骨架标准有一个主动作库，但可以按动作族或风格拆成不可变版本：

```text
humanoid.v1
  -> motionlib:humanoid.v1.core@1
  -> motionlib:humanoid.v1.combat@1
  -> motionlib:humanoid.v1.stylized@1
```

阶段 1 的主库使用以下六状态：

| 状态 | 语义动作 | 中央库 clip | 规则 |
| --- | --- | --- | --- |
| idle | `action:locomotion.idle` | `idle` | 循环 |
| walk | `action:locomotion.walk` | `walking2` | 循环，当前统一基准 |
| run | `action:locomotion.run` | `running` | 循环 |
| jump | `action:locomotion.jump` | `jump` | 使用显式落地策略 |
| boxing | `action:melee.boxing` | `boxing` | full-body 或独占 realization |
| sword_attack | `action:melee.sword_attack` | `sword_attack` | 需要武器槽和 timing marker |

建议目标资源：

```text
assets/motion_library/
  approved/humanoid.v1/street_locomotion.tres
  approved/humanoid.v1/street_locomotion.manifest.json
```

### 4.3 `CharacterPackage`

`CharacterPackage` 绑定实际模型到骨架标准：

```json
{
  "package_id": "female_t_external",
  "skeleton_profile_id": "humanoid.v1",
  "model_scene": "res://assets/active/female_t_external/female_t_external.glb",
  "body_profile_id": "body:female_t.default",
  "binding_profile_id": "humanoid.v1.female_t@1",
  "motion_style": "street_default",
  "ik_profile_id": "ik:humanoid.v1.default",
  "supported_motion_libraries": ["motionlib:humanoid.v1.core@1"]
}
```

角色包负责网格、骨架实例、骨骼映射、挂点、碰撞体、BodyProfile 和 IK 参数；`CharacterActor` 不依赖角色包中的 raw clip 名称。

### 4.4 `MotionRealization`

同一个语义动作可以有多种 realization，但必须显式登记：

```json
{
  "semantic_action_id": "action:locomotion.walk",
  "motion_library_id": "motionlib:humanoid.v1.core@1",
  "skeleton_profile_id": "humanoid.v1",
  "package_id": "female_t_external",
  "clip_ref": "walking2",
  "realization_mode": "shared_library",
  "body_profile_id": "body:female_t.default",
  "motion_style": "street_default",
  "calibration_profile_id": "calibration:humanoid.v1.female_t@1",
  "qualification_status": "approved"
}
```

允许的模式：

| 模式 | 含义 |
| --- | --- |
| `shared_library` | 完全符合骨架标准，直接使用中央 `AnimationLibrary` |
| `retargeted_library` | 经构建时重定向生成目标库 |
| `package_native` | 角色原生动作，经过资格化后显式使用 |
| `fallback` | 中央 realization 不可用时的声明式后备 |

## 5. 阶段 1：中央资产契约

### 5.1 目标

建立一个可审查、可版本化、可被 Registry 消费的 `humanoid.v1` 中央六状态动作库。阶段 1 不改变玩家控制算法，不删除 GLB 内动作，也不要求运行时动态重定向。

### 5.2 工作范围

- 建立 `SkeletonProfile` 和 `MotionLibrary` manifest schema。
- 从 `female_jk_external` 提取并登记六状态动作。
- 为每个 clip 记录骨骼轨道数量、时长、来源 digest、root motion policy、语义动作 ID 和 qualification report。
- 明确 `walking2` 是 `action:locomotion.walk` 的 canonical clip。
- 为三个角色生成指向 `humanoid.v1` 的角色包绑定元数据。
- 让离线资格化区分中央库资源、角色原生动作和 fallback。

### 5.3 阶段 1 输出

```text
assets/motion_library/approved/humanoid.v1/street_locomotion.tres
assets/motion_library/approved/humanoid.v1/street_locomotion.manifest.json
assets/skeleton_profiles/humanoid.v1.json
assets/characters/.../package manifest updates
assets/characters/qualification_reports/.../motion-library report
```

具体路径可以按现有资源布局调整，但 manifest 的稳定 ID 和字段语义不能随意改变。

### 5.4 阶段 1 验收

- 中央库包含六个状态，且 `walk` 指向 `walking2`。
- 六个动作都绑定 `humanoid.v1`，轨道路径和 68 根标准骨骼可解析。
- manifest 能追溯源文件、digest、动作版本、骨架 profile 和资格化报告。
- Registry 能读取中央库元数据，但角色仍可使用现有 GLB fallback。
- 不通过资格化的动作不会进入中央库 approved 索引。

## 6. 阶段 2：共享库运行时接入

### 6.1 目标

让 `female_jk_external`、`female_t_external`、`female_bandage_external` 的 StreetCharacterSkin 挂载同一份中央 `AnimationLibrary`，并保持当前 CharacterActor 控制和 StreetCombat 六状态行为不变。

### 6.2 工作范围

- 在 `StreetCharacterSkin` 初始化阶段加载中央库并挂载到角色的 `AnimationPlayer` 或表现壳。
- 扩展 `CharacterEmbodimentAssetRegistry`，解析 `package_id + semantic_action_id + claims` 到 `MotionRealization`。
- 让 `RoleAnimationController` 接收语义动作解析结果，不把 raw clip 选择写回 CharacterActor。
- 保留 GLB 内动作作为 `fallback`，记录中央库缺失、轨道不兼容或绑定失败原因。
- 保证 AnimationTree、动作锁、hold、cancel、recovery 和 root motion 采样行为不退化。

### 6.3 阶段 2 运行时规则

1. `CharacterActor` 提交 `ActionRequest`，不传未经 Registry 解析的文件路径。
2. Registry 校验角色包和骨架 profile，再选择 `shared_library` 或声明的 fallback。
3. 表现层播放中央库 clip，发布 marker 和 root contribution。
4. `CharacterMotor` 消费 root contribution 并处理速度、碰撞、重力和 `move_and_slide()`。
5. 动作结束后恢复当前有效 locomotion，不固定恢复 idle。

### 6.4 阶段 2 验收

- 三个角色都挂载同一份中央 `AnimationLibrary` 资源，资源身份可在探针中证明。
- 三个角色都能运行 idle、walk、run、jump、boxing、sword_attack。
- `walking2` 映射到 walk；六状态之外的源动作不会被误加入状态树。
- CharacterActor 的玩家、agent 和程序控制仍然有效。
- AnimationTree active、AnimationPlayer binding、68 根轨道、Motor 位移和 root motion 单次消费均通过 Godot 探针。
- 中央库故意不可用时，fallback 行为可预测且有诊断，不得静默读取 incoming/review 资源。

## 7. 阶段 3：构建时/缓存式重定向基础

### 7.1 目标

把中央动作库扩展到不同身材或第二个骨架标准，生成经过资格化的 `retargeted_library`，同时保留统一语义动作目录和 CharacterActor 控制链。

### 7.2 工作范围

- 定义 source `SkeletonProfile` 到 target `SkeletonProfile` 的 canonical mapping。
- 引入 `BodyProfile`、`MotionStyle`、`CalibrationProfile` 和 `IKProfile` 的输入契约。
- 建立重定向器输出目录、缓存 key 和版本 digest。
- 生成目标 `AnimationLibrary`，并记录 retarget solver 版本、输入动作库、目标骨架、参数和报告。
- 进行脚底、手部、武器挂点、root motion、碰撞和攻击接触点资格化。
- 注册成功的 `retargeted_library`，失败结果进入 rejected 或 quarantined。

### 7.3 阶段 3 明确不做

- 不在游戏关键帧中临时生成未经验证的骨骼轨道。
- 不做完整通用运行时 IK 系统；只保留目标接口和必要的验证钩子。
- 不做 raw-pose 网络复制、回滚或 authoritative multiplayer physics。
- 不允许重定向器写世界状态、伤害、库存、最终 Transform 或 Velocity。

### 7.4 阶段 3 验收

- 给定同一中央动作库、目标骨架和参数，重定向输出可重复，缓存 key 稳定。
- 目标库的轨道只引用目标骨架的有效 canonical mapping。
- 六状态至少通过 idle、walk、run、jump，以及一个 full-body combat action 的运行时验证。
- walk/run 的步幅、脚底接触、root motion 和 CharacterMotor 速度不出现重复消费或明显脚滑。
- boxing/sword_attack 的手部、武器槽、marker timing 和接触窗口通过资格化检查。
- 重定向失败时 Registry 不注册结果，角色只能使用已声明 fallback 或拒绝动作。

## 8. 运行时和数据流约束

### 8.1 Registry 解析顺序

1. 用 `semantic_action_id` 找到动作定义和允许的 realization。
2. 校验 `CharacterPackage` 的 `skeleton_profile_id`、版本和 claims。
3. 选择匹配的 `MotionLibrary`、BodyProfile、MotionStyle 和 CalibrationProfile。
4. 按优先级选择 `shared_library`、`retargeted_library`、`package_native` 或显式 fallback。
5. 把 clip、state、mask、timing marker 和 root motion policy 交给表现层。
6. 由 `CharacterMotor` 消费允许的 root contribution。

### 8.2 参数职责

```text
SkeletonProfile      -> 拓扑和语义兼容
BodyProfile          -> 身高、腿长、臂长、质量类别、步幅和 reach 比例
MotionStyle          -> 节奏、倾斜、混合时间、加减速和姿态偏置
CalibrationProfile   -> 脚底、骨盆、挂点、碰撞体和 root motion 修正
IKProfile            -> 脚部贴地、手部抓取、武器对齐和接触修正
```

体重优先影响 Motor 的加减速、落地压缩和混合节奏，不直接改写中央动作关键帧。差异超过 BodyProfile 和校准能力时，必须建立独立 realization。

## 9. 兼容矩阵

| 条件 | 允许方式 | 必须证据 |
| --- | --- | --- |
| 同一骨架 profile、相同轨道路径 | `shared_library` | 骨骼、轨道、rest pose 和六状态探针 |
| 同一 profile、身材小幅差异 | 共享库 + BodyProfile + IK/校准 | 脚步、骨盆、root motion、碰撞和接触 |
| rest pose 或轨道路径不同但可映射 | `retargeted_library` | remap、重定向报告和目标运行时验证 |
| 骨架拓扑不同但可建立稳定 canonical mapping | 独立 profile + 共享语义目录 | 独立动作库或正式 solver 资格化 |
| 无法稳定映射或质量不达标 | 独立动作族或拒绝 | rejected/quarantined 报告 |

动作名称相同不是兼容证明；复制 GLB 轨道也不是重定向完成证明。

## 10. 验证和证据

### 10.1 阶段 1 静态证据

- manifest schema 校验；
- 中央库六状态和 `walking2` 索引校验；
- source digest、轨道数量、时长和 canonical mapping 校验；
- rejected/incoming/review 资源无法被正式 Registry 注册。

### 10.2 阶段 2 Godot 证据

- 三角色挂载同一 `AnimationLibrary` 的资源身份探针；
- 六状态播放和 AnimationTree active；
- CharacterActor 控制、Motor 位移、root motion 单次消费；
- 中央库失效时的显式 fallback；
- 原 `StreetCombatDemo` 不被破坏，副本和中央库接入场景均可启动。

### 10.3 阶段 3 资格化证据

- 重定向输入、输出、solver 版本和缓存 key；
- 目标骨骼轨道完整性；
- 脚、手、武器、root motion 和 marker timing；
- 目标角色运行时六状态和一个 combat action；
- 失败输出不进入 Registry。

## 11. 风险和处理

| 风险 | 处理 |
| --- | --- |
| Godot `AnimationLibrary` 轨道路径与角色节点路径不一致 | 阶段 1 固定 canonical 相对路径，阶段 2 增加运行时 binding probe |
| 中央库和 GLB fallback 同时存在导致选择不透明 | realization 优先级、来源和 fallback 原因写入诊断 |
| root motion 被动画层和 Motor 重复消费 | 统一 `motor_owned` policy，并验证每 tick 单次消费 |
| 身材差异造成脚滑或接触偏差 | BodyProfile + CalibrationProfile + IK 资格化，不用全局硬编码阈值 |
| 重定向器输出不可重复 | 输入 digest、solver 版本和参数进入缓存 key |
| 文档声称中央库已完成但资源尚未建立 | 阶段状态只由新鲜 manifest、Godot 探针和 Harness 证据推进 |

## 12. 非目标和后续扩展

本 spec 不定义：

- 运行时动态加载未经审核的动作文件；
- 通用角色认知、后端 authority 或 Siming 逻辑；
- 原始身体姿态网络复制；
- 完整 IK/接触求解器产品化；
- 删除所有 GLB 内动作的强制迁移时间表。

阶段 3 完成后，才评估更大的中央动作库、自动参数调度、运行时缓存预热和通用 IK。任何新增骨架标准都必须复用本 spec 的 profile、library、realization 和证据契约。

## 13. 用户审阅重点

请重点确认以下决策：

1. 阶段 1 是否以 `humanoid.v1` 和六状态中央库为唯一首个骨架标准。
2. 阶段 2 是否接受 GLB 动作作为迁移期显式 fallback。
3. 阶段 3 是否保持构建时/缓存式重定向，不把实时重定向纳入本轮。
4. `BodyProfile`、`CalibrationProfile` 和 `IKProfile` 是否按本 spec 分离职责。

