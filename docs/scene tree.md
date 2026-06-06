## 一：仓库结构

现在这个仓库的主结构比较清晰，运行项目主要分成 `scenes/`、`scripts/`、`backend/`、`docs/` 四块。

**顶层结构**
- `scenes/phase0/`
  这里是 Godot 场景资源，主运行场景是 [MainDemo.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/MainDemo.tscn:5609)
- `scripts/`
  Godot 逻辑脚本，按 `player/`、`character/`、`object/`、`environment/`、`autoload/`、`phase0/`、`verification/` 分层
- `backend/`
  Python 后端，入口是 [main.py](/d:/Users/User/Documents/paralls-phase-0-demo/backend/app/main.py:1)
- `docs/`
  运行说明、场景导入记录、设计/计划文档

**`scenes/phase0` 文件列表**
- [MainDemo.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/MainDemo.tscn:5609)
- [CharacterReplica.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/CharacterReplica.tscn:8)
- [KnightRoleSkin.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/KnightRoleSkin.tscn:6)
- [InteractiveObject.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/InteractiveObject.tscn:1)
- [EnvironmentStateNode.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/EnvironmentStateNode.tscn:1)
- [GreyboxHumanoidVisual.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/GreyboxHumanoidVisual.tscn:1)
- 另外还有一批预览/导入验证场景：
  `ThroneHall*`, `ThroneRoom*`, `BlenderRenderedApproxEnvironment.tres`

**主场景 Scene Tree**
[MainDemo.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/MainDemo.tscn:5609) 的核心 tree 可以概括成这样：

```text
MainDemo
├─ RoomVisualRoot
│  ├─ GreyboxRoomRoot
│  │  ├─ Field
│  │  ├─ FieldBody
│  │  ├─ BoundaryNorth / South / West / East
│  │  ├─ EntryGuide
│  │  ├─ ObservationBench
│  │  ├─ ObservationScreen
│  │  ├─ FocusPad
│  │  ├─ ControlPlinth
│  │  ├─ ReactionPad
│  │  ├─ ReactionMarkerL / ReactionMarkerR
│  │  └─ ReactionLintel
│  └─ TableVisualRoot
│     ├─ TableAssetMount
│     │  └─ RotationOffset
│     │     └─ ScaleOffset
│     │        └─ ImportedTable
│     └─ GreyboxTableRoot
│        ├─ TableTop
│        ├─ TableTopBody
│        └─ TableLegA / B / C / D
├─ DirectionalLight3D
├─ BlenderRenderedApproxEnvironment
├─ FillLightA / FillLightB / FillLightC
├─ Player
│  ├─ Phase0InputBridge
│  ├─ Phase0Embodiment
│  └─ CameraOcclusionFader
├─ IntentMapper
├─ VisualFactEmitter
├─ CharacterA
├─ CharacterB
├─ CharacterC
├─ InteractiveObject
├─ EnvironmentStateNode
├─ DebugOverlay
└─ ThroneRoomImported
   └─ 大量导入的 throne room 静态网格/灯光/装饰节点
```

这里最关键的是：
- `Player`：隐藏可视壳的控制/碰撞/相机壳
- `CharacterA/B`：AI 巡逻角色
- `CharacterC`：玩家在世界中的骑士可视壳
- `InteractiveObject`：当前关键交互物
- `EnvironmentStateNode`：环境状态变化节点
- `VisualFactEmitter`：视觉事实发射器
- `DebugOverlay`：调试显示
- `ThroneRoomImported`：导入的大型王座厅资产树，节点很多，主要是环境网格和灯光

**角色子场景结构**
[CharacterReplica.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/CharacterReplica.tscn:8)：

```text
CharacterReplica
├─ VisualRoot
│  ├─ AssetMount
│  │  └─ RotationOffset
│  │     └─ ScaleOffset
│  │        └─ ImportedModel
│  │           └─ RoleAssetRoot
│  │              └─ GodotPlushSkin
│  └─ GreyboxBodyRoot
│     └─ GreyboxHumanoidVisual
├─ SpatialVoiceController
└─ Nameplate
```

这说明角色是双轨结构：
- `GreyboxHumanoidVisual`：灰盒表现
- `GodotPlushSkin`：正式骑士资产壳
当前 `use_role_asset=true` 时主要走骑士资产壳

**骑士皮肤子场景**
[KnightRoleSkin.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/KnightRoleSkin.tscn:6)：

```text
GodotPlushSkin
└─ KnightScene
```

`KnightScene` 是导入的骑士模型整体，`KnightRoleSkin.gd` 负责：
- 动作状态切换
- 材质变体
- focus 高亮
- root motion 提取

**脚本目录重点**
- `scripts/player/`
  `Phase0PlayerBridge.gd`, `PlayerIntentMapper.gd`, `Phase0PlayerEmbodiment.gd`
- `scripts/character/`
  `CharacterReplica.gd`, `KnightRoleSkin.gd`, `SpeakingStateController.gd`, `LookAtController.gd`, `RecoilStateController.gd`
- `scripts/phase0/`
  `MainDemoController.gd`
- `scripts/autoload/`
  `BackendBridge.gd`, `LocalPresentationBus.gd`
- `scripts/verification/`
  `verify_phase0.py`, `verify_phase1_slice.py`

**后端结构**
- `backend/app/models/`
  协议对象：`player_input.py`, `ai_output.py`, `world_result.py`, `siming_output.py`, `runtime_state.py`
- `backend/app/services/`
  `character_service.py`, `esm_service.py`, `siming_service.py`, `session_runtime.py` 等
- `backend/tests/`
  后端与验收测试

如果你要，我下一条可以继续给你一份“按运行链路解释的 scene tree”，也就是：
`Player -> CharacterC -> BackendBridge -> LocalPresentationBus -> CharacterA/B/Object/Environment`
这种视角。

## 二：三个角色相关的结构可以分成两层看：

1. `Player`：真正可控的第三人称碰撞/相机壳  
2. `CharacterA/B/C`：场景中的角色副本壳，其中 `CharacterC` 是玩家在世界里的骑士可视壳

先给你结论：

- `Player` 用的是第三方控制器场景 `addons/JehenoThirdPersonController/PlayerCharacter/player_character_scene.tscn`
- `CharacterA/B/C` 都实例化自 [CharacterReplica.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/CharacterReplica.tscn:8)
- `CharacterReplica` 内部同时挂了两套表现：
  - 灰盒表现 `GreyboxHumanoidVisual.tscn`
  - 正式骑士资产 `KnightRoleSkin.tscn`
- 当前主场景里三名角色都 `use_role_asset = true`，所以实际跑的是骑士资产壳
- `CharacterC` 现在是玩家 root motion 可视壳，`Player` 只是隐藏的控制/碰撞/相机壳

**一、MainDemo 里三个角色怎么挂**
在 [MainDemo.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/MainDemo.tscn:5841) 里，相关节点是：

```text
MainDemo
├─ Player                          -> 第三人称控制器壳
│  ├─ Phase0InputBridge            -> scripts/player/Phase0PlayerBridge.gd
│  ├─ Phase0Embodiment             -> scripts/player/Phase0PlayerEmbodiment.gd
│  └─ CameraOcclusionFader         -> scripts/player/CameraOcclusionFader.gd
├─ CharacterA                      -> CharacterReplica.tscn instance
├─ CharacterB                      -> CharacterReplica.tscn instance
└─ CharacterC                      -> CharacterReplica.tscn instance
```

对应配置大意：
- `CharacterA`
  - `actor_id = "char_a"`
  - `patrol_enabled = true`
  - `use_role_asset = true`
- `CharacterB`
  - `actor_id = "char_b"`
  - `patrol_enabled = true`
  - `use_role_asset = true`
- `CharacterC`
  - `actor_id = "char_c"`
  - `patrol_enabled = false`
  - `use_role_asset = true`
  - `player_shell_visual_offset = Vector3(0, -0.32, 0)`

**二、Player 的 scene tree**
`Player` 实例来自：
[addons/JehenoThirdPersonController/PlayerCharacter/player_character_scene.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/addons/JehenoThirdPersonController/PlayerCharacter/player_character_scene.tscn:1)

核心 tree 是：

```text
PlayerCharacter (CharacterBody3D)
├─ VisualRoot
│  ├─ GodotPlushSkin
│  ├─ ParticlesManager
│  └─ MovementDust
├─ AudioRoot
│  ├─ FootStepAudio
│  ├─ ImpactAudio
│  └─ WaveAudio
├─ CameraHolder
├─ CollisionShape3D
├─ StateMachine
│  ├─ IdleState
│  ├─ WalkState
│  ├─ RunState
│  ├─ JumpState
│  └─ InairState
├─ Raycasts
│  └─ FloorRaycast
├─ HUD
└─ InputManagementComponent
```

**Player 对应脚本**
- 根节点脚本：
  [player_character_script.gd](/d:/Users/User/Documents/paralls-phase-0-demo/addons/JehenoThirdPersonController/PlayerCharacter/StateMachine/player_character_script.gd:1)
- 状态机：
  [state_machine_script.gd](/d:/Users/User/Documents/paralls-phase-0-demo/addons/JehenoThirdPersonController/PlayerCharacter/StateMachine/state_machine_script.gd:1)
- 状态脚本：
  [idle_state_script.gd](/d:/Users/User/Documents/paralls-phase-0-demo/addons/JehenoThirdPersonController/PlayerCharacter/StateMachine/idle_state_script.gd:1)  
  [walk_state_script.gd](/d:/Users/User/Documents/paralls-phase-0-demo/addons/JehenoThirdPersonController/PlayerCharacter/StateMachine/walk_state_script.gd:1)  
  [run_state_script.gd](/d:/Users/User/Documents/paralls-phase-0-demo/addons/JehenoThirdPersonController/PlayerCharacter/StateMachine/run_state_script.gd:1)  
  [jump_state_script.gd](/d:/Users/User/Documents/paralls-phase-0-demo/addons/JehenoThirdPersonController/PlayerCharacter/StateMachine/jump_state_script.gd:1)  
  [inair_state_script.gd](/d:/Users/User/Documents/paralls-phase-0-demo/addons/JehenoThirdPersonController/PlayerCharacter/StateMachine/inair_state_script.gd:1)
- 输入映射：
  [input_management_component_script.gd](/d:/Users/User/Documents/paralls-phase-0-demo/addons/JehenoThirdPersonController/PlayerCharacter/InputManagement/input_management_component_script.gd:1)

**Player 挂的资产**
- 可视壳：
  `addons/JehenoThirdPersonController/PlayerCharacter/GodotPlush/godot_plush_skin.tscn`
- 音频：
  `addons/JehenoThirdPersonController/PlayerCharacter/Sounds/*.ogg`
- 相机：
  `addons/JehenoThirdPersonController/PlayerCharacter/Camera/camera_holder_scene.tscn`

**Player 在你当前项目里的额外挂件**
这些不是第三方原场景自带逻辑，而是你项目加在 `Player` 节点下面的：
- [Phase0PlayerBridge.gd](/d:/Users/User/Documents/paralls-phase-0-demo/scripts/player/Phase0PlayerBridge.gd:1)
- [Phase0PlayerEmbodiment.gd](/d:/Users/User/Documents/paralls-phase-0-demo/scripts/player/Phase0PlayerEmbodiment.gd:1)
- [CameraOcclusionFader.gd](/d:/Users/User/Documents/paralls-phase-0-demo/scripts/player/CameraOcclusionFader.gd:1)

这三者职责是：
- `Phase0PlayerBridge`
  把 `Player` 壳和 `CharacterC` 可视壳桥接起来；现在 root motion 玩家链的关键就在这里
- `Phase0PlayerEmbodiment`
  处理轻微姿态反馈
- `CameraOcclusionFader`
  做相机遮挡淡化

**三、CharacterA/B/C 的通用 scene tree**
三者都来自：
[CharacterReplica.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/CharacterReplica.tscn:8)

tree 是：

```text
CharacterReplica (Node3D)
├─ VisualRoot
│  ├─ AssetMount
│  │  └─ RotationOffset
│  │     └─ ScaleOffset
│  │        └─ ImportedModel
│  │           └─ RoleAssetRoot
│  │              └─ GodotPlushSkin
│  └─ GreyboxBodyRoot
│     └─ GreyboxHumanoidVisual
├─ SpatialVoiceController
└─ Nameplate
```

**CharacterReplica 根脚本**
- [CharacterReplica.gd](/d:/Users/User/Documents/paralls-phase-0-demo/scripts/character/CharacterReplica.gd:1)

这个脚本同时负责：
- A/B 巡逻逻辑
- 对话/注意力/姿态状态
- `CharacterC` 玩家可视壳模式
- root motion 增量消费
- 角色 focus / runtime state 显示

**CharacterReplica 里两套可视资产**
1. 灰盒壳
- 场景：
  [GreyboxHumanoidVisual.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/GreyboxHumanoidVisual.tscn:1)
- 脚本：
  [GreyboxHumanoidVisual.gd](/d:/Users/User/Documents/paralls-phase-0-demo/scripts/character/GreyboxHumanoidVisual.gd:1)

2. 正式骑士壳
- 场景：
  [KnightRoleSkin.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/KnightRoleSkin.tscn:6)
- 脚本：
  [KnightRoleSkin.gd](/d:/Users/User/Documents/paralls-phase-0-demo/scripts/character/KnightRoleSkin.gd:1)

**四、KnightRoleSkin 的 scene tree**
[KnightRoleSkin.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/KnightRoleSkin.tscn:6)

```text
GodotPlushSkin (Node3D)
└─ KnightScene
```

这里的 `KnightScene` 来自导入骑士资产：
- `res://assets/characters/shared/crusader_knight.glb`

`KnightRoleSkin.gd` 负责：
- 动作状态映射：`idle / walk / run / jump / speak / inspect / alert`
- 角色外观变体：`char_a / char_b / char_c`
- 高亮材质
- root motion 提取

也就是说，A/B/C 三个角色虽然都用同一个 `CharacterReplica` 场景，但具体差异主要在：
- `actor_id`
- 巡逻参数
- root motion 驱动模式
- `KnightRoleSkin` 的 `configure_role(actor_id)`

**五、三个角色分别是什么关系**
最重要的是这个：

```text
Player                = 控制壳 / 碰撞壳 / 相机壳
CharacterA            = AI 巡逻角色
CharacterB            = AI 巡逻角色
CharacterC            = 玩家在世界中的骑士表现壳
```

更具体一点：

- `Player`
  - 真正接收 WASD、Shift、Space、镜头输入
  - 有碰撞、重力、相机
  - 自己的 `VisualRoot` 现在默认被隐藏
- `CharacterC`
  - 作为玩家“在世界里被看见的角色”
  - 现在吃 root motion，反向驱动 `Player` 的 grounded 移动
- `CharacterA/B`
  - 同样是 `CharacterReplica`
  - 由 patrol target 和控制器约束决定方向
  - 再优先吃动作根位移推进

**六、如果按“资产 + 脚本”对应表来看**
`Player`
- Scene:
  [player_character_scene.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/addons/JehenoThirdPersonController/PlayerCharacter/player_character_scene.tscn:1)
- Main script:
  [player_character_script.gd](/d:/Users/User/Documents/paralls-phase-0-demo/addons/JehenoThirdPersonController/PlayerCharacter/StateMachine/player_character_script.gd:1)
- Added project scripts:
  [Phase0PlayerBridge.gd](/d:/Users/User/Documents/paralls-phase-0-demo/scripts/player/Phase0PlayerBridge.gd:1),
  [Phase0PlayerEmbodiment.gd](/d:/Users/User/Documents/paralls-phase-0-demo/scripts/player/Phase0PlayerEmbodiment.gd:1),
  [CameraOcclusionFader.gd](/d:/Users/User/Documents/paralls-phase-0-demo/scripts/player/CameraOcclusionFader.gd:1)

`CharacterA/B/C`
- Scene:
  [CharacterReplica.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/CharacterReplica.tscn:8)
- Main script:
  [CharacterReplica.gd](/d:/Users/User/Documents/paralls-phase-0-demo/scripts/character/CharacterReplica.gd:1)
- Voice:
  [SpatialVoiceController.gd](/d:/Users/User/Documents/paralls-phase-0-demo/scripts/audio/SpatialVoiceController.gd:1)
- Visual assets inside:
  [GreyboxHumanoidVisual.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/GreyboxHumanoidVisual.tscn:1)
  and
  [KnightRoleSkin.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/KnightRoleSkin.tscn:6)

`KnightRoleSkin`
- Scene:
  [KnightRoleSkin.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/KnightRoleSkin.tscn:6)
- Script:
  [KnightRoleSkin.gd](/d:/Users/User/Documents/paralls-phase-0-demo/scripts/character/KnightRoleSkin.gd:1)
- Imported asset:
  `assets/characters/shared/crusader_knight.glb`

如果你要，我下一条可以继续给你一份“只看角色系统”的树，把 `Player`、`CharacterC`、`KnightScene` 细化成更可读的 ASCII 结构，并把“哪一层负责输入、哪一层负责 root motion、哪一层负责后端同步”逐层标出来。