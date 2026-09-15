# 美术资源资格与接入需求清单

## 目标

所有美术资源都必须作为可替换的 Presentation Pack 接入，不能成为
`Unified3DIntegrationValidation` 或角色智能体、司命、Gameplay Authority 的硬编码依赖。

默认项目入口是：

```text
scenes/integration/Unified3DIntegrationValidation.tscn
```

默认入口使用 generic fallback。正式资源只有在明确激活、通过资格场、并取得
`approved` 状态后，才允许进入展示或专项集成验证。

## 资源状态

```text
archive/                 原始保留区，不参与默认 Godot 扫描
assets/active/           显式激活的候选包
assets/validation/       manifest 与资格配置
scenes/qualification/    资格场
scenes/integration/      通用运行时集成场
```

状态流转：`archived -> activated -> candidate -> qualified -> approved`。

## 角色资源

### 包装与运行时契约

- [ ] GLB/GLTF、贴图、材质、动画和 wrapper 场景路径完整。
- [ ] 没有旧活动目录、外部工程、绝对路径或 `goblend/scenes/...` 依赖。
- [ ] 可复制到 `assets/active/<pack_id>/` 后独立导入。
- [ ] 角色 skin 挂载在 `CharacterReplica/VisualRoot/AssetMount/.../RoleAssetRoot`。
- [ ] 提供 `configure_role`、`set_state`、`set_motion_profile`。
- [ ] 提供 `play_reviewed_action_atom`、`consume_root_motion_delta`、`reset_root_motion`。
- [ ] 提供 `get_current_clip_name`、`get_current_motion_profile_name`。

### Skeleton3D

必须解析并在 manifest 中记录：

- [ ] hips / pelvis
- [ ] lower spine / upper spine
- [ ] neck / head
- [ ] 左右 upper arm / forearm / hand
- [ ] 左右 thigh / calf / foot

不能依靠运行时猜测骨骼名称；必须有 candidate list 或显式 binding profile。

### 第一版普通绑骨准入

第一版正式角色资源可以使用普通人体绑骨；不要求手指骨骼、面部骨骼、眼球骨骼
或 FACS 表情系统。最低可用骨架为：

```text
pelvis / hips
spine
neck
head
upper_arm_l -> forearm_l -> hand_l
upper_arm_r -> forearm_r -> hand_r
thigh_l -> calf_l -> foot_l
thigh_r -> calf_r -> foot_r
```

手部骨骼是必须项，但手指骨骼不是。没有手指细节时，装备和交互道具挂在
`hand_l` 或 `hand_r`，由整手姿态、道具局部偏移和必要的手臂 IK/modifier 表现。

普通绑骨角色可以通过第一版资格并支持：

- [ ] 行走、跑步、转身、观察、说话、警戒和检查。
- [ ] 抬手、伸手、接触、开门、拿取、携带和放置。
- [ ] 剑、盾、工具等整体装备挂载。
- [ ] 基于手部 anchor 的 reach/contact 验证。

普通绑骨不承担以下精细表现，这些是后续升级项：

- [ ] 手指逐根弯曲、精细抓握和手势语言。
- [ ] 小型机关、钮扣、钥匙等手指级操作。
- [ ] 面部骨骼、眼球骨骼或 FACS 表情。

### 模型交付要求

- [ ] 优先交付 GLB；需要拆分调试时可使用 GLTF + BIN。
- [ ] 模型比例使用米制，人物高度、根节点朝向和站立姿态稳定。
- [ ] 网格、骨架、动画、材质和贴图都在同一可移动资源包内。
- [ ] 不能引用原工程、旧活动目录或绝对路径。
- [ ] gameplay collision 不应绑定在美术模型上；由 `CharacterBase` 的
  `CharacterBody3D` 和 `CollisionShape3D` 负责。

### 动作与 root motion

最低动作集合：

- [ ] idle
- [ ] walk
- [ ] run
- [ ] observe
- [ ] speak
- [ ] inspect
- [ ] interact
- [ ] recover

每个动作记录 action tag、实际 clip、root-motion profile、兼容等级、装备槽位和
post-animation modifier。root motion 必须由 motor 消费，skin 不能直接写世界坐标。

第一版允许 `root_motion_profile: none`：角色移动仍由 `CharacterMotor` /
`CharacterBody3D` 控制，动画只负责视觉。这一等级为
`locomotion_plus_equipment`，可作为正式资源的第一阶段通过条件。

`full_action_ready` 才要求对需要位移的动作提供 root motion，并证明动画位移只被
motor 消费，循环、动作切换和动作结束会清理累计位移。

### 装备、交互和碰撞

- [ ] right hand / left hand 等装备槽可解析。
- [ ] 每个槽位有 anchor path、位置偏移和旋转偏移。
- [ ] reach/contact 动作能找到交互 anchor。
- [ ] 需要 SkeletonIK 或 modifier 时必须声明并验证。
- [ ] 角色 host 使用独立 `CharacterBody3D` + `CollisionShape3D`。
- [ ] visual 替换不会改变 actor_id、控制模式或 authority contract。

## 环境资源

- [ ] 模型可以独立加载和实例化。
- [ ] 单位比例、朝向、出生点和相机 anchor 已校准。
- [ ] 地面、墙体、障碍物有独立 collision scene/profile。
- [ ] 有 NavigationRegion3D 或明确导航构建输入。
- [ ] 有 zone、player spawn、角色站位和交互锚点。
- [ ] approach、contact、observation、placement anchor 齐全。
- [ ] 环境状态点可绑定 `environment_id`。
- [ ] 遮挡、视线、距离和 occupancy 可以被结构化采样。
- [ ] 灯光使用独立 presentation profile。
- [ ] 环境模型不拥有 gameplay truth。

环境资格场至少检查 MeshInstance3D、collision scene、导航/anchor manifest、
state fixture，以及没有活动区外部路径依赖。

## 道具、UI、音频与特效

- [ ] 道具拥有稳定 object_id，visual、collision、anchor、affordance 分离。
- [ ] 成功/失败状态只由 authority result 驱动。
- [ ] UI 与运行时数据绑定分离，能显示角色、司命、authority、失败和 replay 状态。
- [ ] 语音资源有 provider/model/voice binding 和审批状态。
- [ ] 原始录音、临时 URL、API key 不入库。
- [ ] 特效只负责 presentation，不写世界真值。

## 资格命令

```powershell
$env:CHARACTER_QUALIFICATION_MANIFEST = 'res://assets/validation/manifests/<pack>-qualification.json'
& 'D:\godot\Godot_v4.6.3-stable_win64_console.exe' --headless --path . `
  --scene res://scenes/qualification/CharacterAssetQualification.tscn `
  --quit-after 8 --rendering-method gl_compatibility --render-thread safe
```

```powershell
$env:ENVIRONMENT_QUALIFICATION_MANIFEST = 'res://assets/validation/manifests/<pack>-qualification.json'
& 'D:\godot\Godot_v4.6.3-stable_win64_console.exe' --headless --path . `
  --scene res://scenes/qualification/EnvironmentAssetQualification.tscn `
  --quit-after 8 --rendering-method gl_compatibility --render-thread safe
```

报告：

- `.harness/verification/character-asset-qualification-report.json`
- `.harness/verification/environment-asset-qualification-report.json`

## 当前状态

- `crusader_knight`：资格尝试失败。GLB 仍引用旧的 `assets/characters/shared/...`
  贴图路径，必须重新导出或完成受控路径归一化。
- `throne_room_existing`：未通过资格，保持 legacy archive。
- `astra_room`：未通过正式环境资格，保持 candidate archive。
- `apartment_test`：未通过正式环境/角色资格，保持 candidate archive。
- `Unified3DIntegrationValidation`：generic fallback 运行时闭环已验证，不承担正式
  角色骨骼、动画和美术质量证明。

只有资格报告为 `qualified`、无外部路径依赖、碰撞/导航/锚点/动作通过，且统一场
asset binding smoke test 通过后，manifest 才能从 `candidate` 改为 `approved`。
