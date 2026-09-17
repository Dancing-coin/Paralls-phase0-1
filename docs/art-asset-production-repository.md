# 美术资源生产仓库关联说明

## 仓库职责

项目现在分成两个明确的仓库：

| 仓库 | 职责 |
| --- | --- |
| `paralls-art-assets` | Blender 源文件、制作参考、版本化导出包、manifest、导出报告 |
| `paralls-phase-0-demo` | Godot runtime、backend authority、通用集成场、资格场、显式激活和资格报告 |

默认本机布局：

```text
D:/Users/User/Documents/paralls-art-assets
D:/Users/User/Documents/paralls-phase-0-demo
```

机器可读关联见仓库根目录的 `art-assets-repository.json`。

## 生产仓库做什么

GPT-6 在 Blender 中工作时，应在 `paralls-art-assets` 完成：

- 角色建模、普通绑骨、动作和装备锚点；
- 小型环境、碰撞代理、导航输入和空间锚点；
- 道具、UI、音频和特效资源；
- manifest、导出报告和已知限制；
- `exports/<pack_id>/<version>/` 下的可移动交付包。

生产仓库不放当前 Godot 的 `project.godot`、`.godot/`、backend、运行时脚本
或 Godot 插件。它是源资产仓，不是第二个游戏运行时。

## 交接流程

```text
Blender source
  -> versioned export package
  -> explicit copy to assets/active/<pack_id>
  -> CharacterAssetQualification or EnvironmentAssetQualification
  -> qualified report
  -> approved binding
  -> dedicated integration/showcase scene
```

只有显式复制到 `assets/active/` 的候选包才会进入 Godot 导入和资格验证；它
不会自动改变 `Unified3DIntegrationValidation.tscn`。默认集成场继续使用通用
procedural fallback。

## 旧资源如何处理

旧资源继续留在当前仓库的 `archive/`，并由 `.gdignore` 退出默认 Godot 项目。
生产仓库不复制大批旧二进制文件，而是在
`references/current-project-asset-index.md` 和
`references/current-project-asset-inventory.json` 中保留可追踪的参考索引。

当前参考包括：

- `throne_room_existing`：旧王座厅环境参考；
- `crusader_knight`：角色骨架、动作和装备参考，但当前资格尝试因旧贴图路径
  失败；
- `throne_room_fresh`、`astra_room`、`apartment_test`：环境/角色候选参考；
- `import_fixtures`、`goblend_source`：导入工具和测试夹具，不是产品资产。

## 资源准入底线

- GLB 优先，GLTF + BIN 仅在需要拆分调试时使用。
- 角色允许普通人体绑骨；手指、面部、眼球和 FACS 骨骼不是 v1 必需项。
- 角色最低骨架和动作标签必须在 manifest 中显式记录。
- v1 允许 `root_motion_profile: none`，移动仍由 Godot motor 负责。
- gameplay collision、authority truth、角色 ID 和运行时壳不由 Blender 资源
  接管。
- 不能有绝对路径、外部工程依赖、旧活动目录或隐式缺失资源。

详细规范的生产仓库副本位于其 `references/` 和 `production/` 目录；当前仓库
的资格实现和报告仍以本仓库文件为准。
