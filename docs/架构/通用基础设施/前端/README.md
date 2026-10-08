# 前端通用基础设施

前端通用基础设施位于 Godot 侧，负责输入、角色控制意图、局部相机和可见表现的组合。它不拥有世界真相、authority 结算或角色认知。

## 当前代码映射

| 能力 | 代码 | 状态 |
| --- | --- | --- |
| 控制源编排 | `scripts/character/control/CharacterControlFoundation.gd` | current |
| 玩家输入适配 | `scripts/character/control/CharacterPlayerInputSource.gd` | current |
| 相机控制 | `scripts/character/control/CharacterCameraController.gd` | current，基础跟随 |
| 角色宿主 | `scripts/character/CharacterActor.gd` | current |
| 身体运动 | `scripts/character/CharacterMotor.gd` | current |
| 动作与骨架表现 | `scripts/character/CharacterPackagePresentationAdapter.gd`、`CharacterEmbodimentAssetRegistry.gd` | current |
| 骑士包示例 | `assets/active/crusader_knight/`、`native_motion_library.tres` | current，package adapter sample |
| 街斗样板 | `scenes/phase0/StreetCombatActorControlDemo.tscn` | current，adapter sample |
| 新增人物 | Registry 检查 + 场景独立 `CharacterActor` 实例 + `bind(root)` | current，静态追加；事务接纳、增量名单和注册配置解耦 planned |

新增默认保留原人物，先检查可复用的骨架和动作库，再装配独立人物实例。资源包身份与人物实例身份分开；注册资源不替换场景人物。完整规则和当前限制见设计文档的“新增人物的装配契约”，实际配置见说明文档。

## 主题文档

- [角色控制基础设施设计](角色控制基础设施设计.md)
- [角色控制基础设施说明](角色控制基础设施说明.md)
- [角色控制基础设施架构图](角色控制基础设施架构图.md)
- [角色控制基础设施时序图](角色控制基础设施时序图.md)
- [角色控制基础设施数据流转图](角色控制基础设施数据流转图.md)
