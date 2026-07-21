# 美术资源替换与更新工作流手册

这份手册定义本项目如何把场景、角色、道具和材质做成可替换、可更新的资产层，而不破坏 `world-character-Siming-authority unified runtime` 的 Godot 表现、后端 authority、角色智能体、ESM 交互和 Siming 链路。

## 结论

当前项目不是只能绑定现有王座厅和骑士资源。真正需要保留的是运行时壳、结构化 ID 和协议边界；美术资源应当作为可替换的 presentation pack 接入。

可换的是：

- 环境模型、贴图、灯光和碰撞来源
- 角色模型、材质、骨架、动画和外观状态
- 物体模型、证物外观和环境状态点外观
- 角色站位、巡逻点、交互锚点和相机构图

不能随意换掉的是：

- `LocalPresentationBus`、`BackendBridge` 等 autoload
- `actor_id`、`object_id`、`environment_id`、`scene_id`、`zone_id`
- `CharacterReplica`、`InteractiveObject`、`EnvironmentStateNode` 这类运行时壳节点
- 后端返回的结构化 result 驱动 Godot 可见变化的边界

## 目标形态

美术资源应当分成四层：

1. `Art Pack`：一批外部导入资源，保持相对路径稳定。
2. `Adapter Scene`：把外部资源包适配成项目内部可消费的场景。
3. `Runtime Shell`：当前项目已有的行为壳和协议节点。
4. `Binding Profile`：记录资源包如何绑定到角色、物体、环境和动作语义。

推荐长期目录：

```text
assets/
  artpacks/
    apartment_test/
      source_manifest.md
      import_report.md
      environment/
      characters/
      props/
      textures/
  runtime_bindings/
    apartment_test/
      scene_binding.md
      character_binding.md
      object_binding.md
scenes/
  artpacks/
    apartment_test/
      ApartmentImported.tscn
      ApartmentRuntimeAdapter.tscn
      ApartmentNpcRoleSkin.tscn
      ApartmentObjectAnchors.tscn
```

近期开工时可以不一次性建全自动资产库，但新资源都应当朝这个目录和绑定模型靠拢。

## 项目内稳定接口

### 主场景壳

主运行场景可以换环境，但应保留这些节点职责：

- `PlayerCharacter`：玩家控制壳。
- `CharacterA` / `CharacterB`：AI 角色壳，必须保留 `actor_id`。
- `InteractiveObject`：交互物壳，必须保留 `object_id`。
- `EnvironmentStateNode`：环境状态壳，必须保留 `environment_id` 或现有等价字段。
- `VisualFactEmitter`：事实上抛入口。
- `ObservatoryRoot`：导演观察和调试入口。

如果新场景不叫 `ThroneRoomImported`，应优先新增一个场景适配层，而不是把所有旧代码直接改名。适配层负责把新场景暴露成当前运行时需要的导航、碰撞、锚点和可见状态。

当前已有可复用模板：

- `res://scenes/phase0/SceneRuntimeAdapter.tscn`
- `res://scripts/phase0/SceneRuntimeAdapter.gd`

`MainDemo.tscn` 已默认实例化该节点并命名为 `SceneRuntimeAdapter`。`MainDemoController.gd` 会优先通过它解析 imported root、collision root、灯光策略和碰撞 bootstrap 策略；没有该节点时才自动回退旧王座厅节点名。当前旧王座厅只是 adapter 的默认绑定，不是运行时代码必须绑定的美术资源。

### 角色壳

`CharacterReplica` 是角色运行时壳，不应被外部模型根节点替代。新角色模型应当挂在：

```text
CharacterReplica
  VisualRoot
    AssetMount
      RotationOffset
        ScaleOffset
          ImportedModel
            RoleAssetRoot
              <RoleSkinScene>
```

当前 `CharacterReplica.gd` 会调用 role skin 的方法。一个新角色 skin 至少应支持：

- `configure_role(actor_id)`
- `set_state(state_name)`
- `set_motion_profile(state_name, profile_name)`
- `set_focus_highlight(is_focused)`，可选但推荐
- `apply_presentation_input(presentation_input)`，可选
- `consume_root_motion_delta()`，有 root motion 时需要
- `reset_root_motion()`，有 root motion 时需要
- `get_current_clip_name()`，用于验证和调试
- `get_current_motion_profile_name()`，用于验证和调试

如果新模型暂时没有完整动作集，可以先用空实现或 fallback idle，但必须明确记录缺口。

当前 `CharacterReplica.gd` 已支持 `role_asset_scene_path`。新角色 skin 可以通过 inspector 指到任意 `RoleAssetRoot` 子节点；未配置时仍回退到旧 `KnightRoleSkin`，再回退到 `RoleAssetRoot` 下第一个子节点。

### 物体和环境状态壳

`InteractiveObject` 和 `EnvironmentStateNode` 的业务脚本不要挂到导入模型根节点。外部模型只作为可视层，运行时壳继续负责：

- ID 暴露
- 焦点/射线可命中
- 后端 result 回写
- 可见状态变化
- L1 fact 采样

推荐层级：

```text
InteractiveObject
  VisualRoot
    AssetMount
      RotationOffset
        ScaleOffset
          ImportedModel
```

## 日常替换流程

### 接入一批新美术资源

1. 把外部资源先放到暂存目录，不直接覆盖现有 `scenes/phase0` 和 `scripts/`。
2. 盘点资源引用：
   - 主场景路径
   - `.tscn/.scn` 引用的 `res://` 路径
   - 贴图、材质、GLB/GLTF、脚本
   - 缺失文件
3. 将可用运行时资源复制到 `assets/artpacks/<pack_id>/`。
4. 在 `scenes/artpacks/<pack_id>/` 建 adapter 场景。
5. 只把 adapter 场景实例化进主 demo，不替换 `project.godot`。
6. 保留旧灰盒可见层，先隐藏，不急着删除。
7. 逐项验证环境、角色、物体、状态变化。

### 更新已有资源包

更新资源时优先保持路径和文件名稳定。Godot 的场景引用依赖路径，频繁改文件名会制造不必要的 `.tscn` 抖动。

推荐顺序：

1. 替换同名源资源。
2. 打开 Godot 触发重新导入。
3. 检查 `.import` 是否更新。
4. 运行静态完整性检查。
5. 打开 adapter 场景确认材质、比例和碰撞。
6. 再打开主 demo 验证 runtime 链路。

### 替换环境场景

环境替换不要理解为“换主场景”。更稳的做法是：

1. 新环境作为 `ApartmentImported` 之类的子树进入主场景。
2. 地面、墙体、障碍物碰撞优先验证。
3. 把玩家出生点、相机初始朝向、两个角色站位移到新空间。
4. 给可交互物和环境状态点放置锚点。
5. 让 `SceneSpaceModelExtractor` 能看到新空间里的 zone/object/environment anchor。
6. 等新场景完整承担职责后，再下线旧环境可见层。

### 替换角色美术

1. 为新角色建立独立 role skin 场景，例如 `ApartmentNpcRoleSkin.tscn`。
2. 在 role skin 内部实例化导入的 GLB/GLTF。
3. 用 `RotationOffset` 和 `ScaleOffset` 修正朝向和比例。
4. 在 role skin 脚本里实现角色 skin 方法契约。
5. 把 `CharacterReplica` 的 `RoleAssetRoot` 子节点替换为新 role skin。
6. 角色仍保留原来的 `actor_id`，不要因为换模型改协议 ID。
7. 验证 idle、walk、speak、inspect、alert 至少有 fallback。

### 替换交互物

1. 保留 `InteractiveObject` 根节点和 `object_id`。
2. 将新物体模型挂到 `VisualRoot/AssetMount/.../ImportedModel`。
3. 调整碰撞或射线命中体，保证焦点可以锁定。
4. 确认成功交互和失败交互都仍由后端 result 驱动。

### 替换环境状态点

1. 保留 `EnvironmentStateNode` 根节点和环境 ID。
2. 把新灯具、门、屏幕或状态装置挂到可视层。
3. 将 `alerted`、`stable` 等状态映射到材质、灯光或可见变化。
4. 不要让 Godot 本地直接伪造成功状态；状态变化必须来自后端 result 或 approved stub path。

## 针对 `E:\下载\测试文件` 的接入建议

这批资源已作为新 art pack 隔离接入，pack id 为 `apartment_test`。

静态检查结果显示它包含：

- `三室一厅测试_AutoCollision.scn`
- 三个 NPC 角色场景和对应 GLB/贴图
- 简单第三人称控制脚本
- `goblend`、`godot_mcp`、`blender_auto_collision_pipeline` 插件文件

当前项目内落位：

- 源资源：`res://assets/artpacks/apartment_test/source/`
- 外部 wrapper 参考：`res://assets/artpacks/apartment_test/reference/`
- 当前项目角色 wrapper：`res://scenes/artpacks/apartment_test/characters/`
- 当前项目环境 adapter wrapper：`res://scenes/artpacks/apartment_test/environment/ApartmentEnvironment.tscn`

已验证可加载的角色 skin：

- `NpcDefaultSkin.tscn`
- `NpcCh01Skin.tscn`
- `NpcCh22Skin.tscn`
- `NpcCh31Skin.tscn`

已发现风险：

- 主 `.scn` 引用 `res://goblend/scenes/texture_pbr_20250901...` 系列贴图，但当前目录缺 `goblend/scenes/`。
- 目标 `project.godot` 没有当前项目的 `LocalPresentationBus` 和 `BackendBridge`。
- 目标场景是二进制 `.scn`，不适合直接手工批量改路径。

当前处理方式：

1. 不复制目标 `project.godot`、`.godot/` 导入缓存或外部 MCP 插件。
2. 只复制源美术到 `assets/artpacks/apartment_test/source/`。
3. 角色 GLB 在当前项目重新导入，并通过当前项目 wrapper 场景暴露为 skin。
4. `ApartmentEnvironment.tscn` 先保留 `ImportedRoot`、`CollisionRoot` 和 `SceneRuntimeAdapter`，但不直接实例化有缺失依赖的二进制 `.scn`。
5. `SceneRuntimeAdapter.source_scene_path` 记录原始公寓 `.scn` 路径，`import_notes` 记录修复要求。

后续把公寓场景接成真实运行环境时：

1. 优先从原始 Blender/Godot 工程重新导出一个不依赖外部 `goblend` 路径的 `.glb`/`.tscn`。
2. 如果只能使用当前 `.scn`，先补齐缺失贴图和它引用的 NPC wrapper，再在 Godot 中另存为可维护 `.tscn`。
3. 在 `ApartmentEnvironment.tscn` 里实例化修复后的场景。
4. 在 adapter 里添加或暴露：
   - 玩家出生点
   - `char_a` / `char_b` / `char_c` 站位
   - `obj_letter` 或新物体锚点
   - `env_lamp` 或新环境状态锚点
   - `zone_focus` 或新空间 zone
5. 再把 adapter 接入当前 `MainDemo.tscn` 或建立 `MainDemoApartment.tscn` 分支场景。

## 推荐改造路线

### 阶段 A：文档和手工规范

目标：今天就能按手册换资源。

- 固定 `assets/artpacks/<pack_id>/` 和 `scenes/artpacks/<pack_id>/` 目录。
- 每个资源包必须有 `source_manifest.md` 和 `import_report.md`。
- 每次接入先跑静态 `res://` 引用完整性检查。
- 所有替换都从 adapter 场景进入，不覆盖主项目配置。

### 阶段 B：把硬编码节点名收敛到 adapter

目标：让主 runtime 只依赖抽象入口。

当前 `MainDemoController.gd` 已有第一阶段 adapter 查询入口，但仍保留 `ThroneHallWalkPreview` 作为旧王座厅碰撞 fallback。后续应继续收敛成：

```text
MainDemoController
  -> SceneRuntimeAdapter
     -> get_imported_root()
     -> get_collision_root()
     -> get_spawn_point(actor_id)
     -> get_object_anchor(object_id)
     -> get_environment_anchor(environment_id)
     -> apply_lighting_profile(profile_id)
```

这样主场景不再知道当前用的是王座厅、公寓还是其他空间。

### 阶段 C：角色 skin 查找从固定节点改为 profile

目标：角色资源更新时不用改 `CharacterReplica.tscn`。

当前 `CharacterReplica.gd` 默认找：

```text
VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/KnightRoleSkin
```

后续应改为：

- `@export_node_path("Node") var role_asset_scene_path`
- 或 `@export var role_asset_profile_id`
- 找不到指定 skin 时回退到当前 `KnightRoleSkin`

这样换角色只需要改 inspector 或 profile，不需要改脚本硬编码。

### 阶段 D：资源包 manifest 和验证脚本

目标：资源包是否可用可以被机器检查。

每个 art pack 应产生：

```text
source_manifest.md
import_report.md
scene_binding.md
character_binding.md
object_binding.md
```

后续可以加一个验证脚本检查：

- 所有 `res://` 引用存在
- 主 adapter 场景能加载
- 必需 ID 存在
- 角色 skin 方法存在
- 碰撞和 spawn point 存在
- 资源包没有覆盖 `project.godot`

## 最低验证清单

每次换美术或更新资源包后，至少完成：

- [ ] 不覆盖 `project.godot`
- [ ] 新资源包没有缺失 `res://` 引用
- [ ] Godot 主场景能打开
- [ ] 玩家出生点在有效碰撞面上
- [ ] `CharacterA` / `CharacterB` 仍有 `actor_id`
- [ ] 玩家角色或观察角色仍能对焦目标
- [ ] 对话请求能发到后端
- [ ] 后端 dialogue response 能驱动角色表现
- [ ] 成功交互由后端 result 驱动
- [ ] 失败交互由 structured constraint result 驱动
- [ ] 环境或物体状态变化可见
- [ ] Siming catalyst 能触发至少一个可观察反应

## 推荐验证命令

静态和后端基础验证：

```powershell
python -m pytest -v
python scripts/verification/harness.py --profile godot-project
python scripts/verification/harness.py --profile backend-contract
```

主线聚合验证：

```powershell
python scripts/verification/harness.py --profile mainline-unified-runtime
```

如果确认要声明大范围完成：

```powershell
python scripts/verification/harness.py --profile all
```

Godot editor/runtime 不可用时，只能报告为：

- 静态已写入
- adapter 已装配
- 未经 Godot editor/runtime 验证

不能报告为“运行时已完成”。

## 常见错误

- 直接用外部 `project.godot` 覆盖当前项目。
- 把业务脚本挂到导入模型根节点。
- 为了新模型修改 `actor_id` / `object_id`，导致后端协议断开。
- 删除旧壳节点后才发现焦点、交互或状态回写没有替代入口。
- 把 `.scn` 二进制场景当成可手工批量替换路径的文本文件。
- 忽略缺失贴图，只看几何能打开就认为资源包完整。
- 只在空白测试场景验证角色，不放回主 runtime 场景验证对话、交互和 Siming。

## 一句话原则

换美术不是换 runtime。美术资源应当通过 adapter 和 binding profile 接入；运行时继续依赖稳定壳节点、结构化 ID 和后端 authority result。
