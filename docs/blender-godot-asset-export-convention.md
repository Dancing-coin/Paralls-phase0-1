# Blender -> Godot Asset Export Convention

这份文档定义当前仓库里 Blender 资产进入 Godot 的默认路径、目录约定和验证标准。

适用范围：

- `Phase 0` 演示期的角色、环境、道具资产
- 本地 Blender -> Godot 导入验证
- `goblend`、直接 `glTF` 导出、Blender MCP 导出三条路径

不适用范围：

- Phase 1 生产级 DCC 管线设计
- 多人协作下的资产版本管理平台
- 自动化构建服务器上的完整 DCC 流程

## 结论先行

当前项目里，默认推荐资产导入路径是：

1. **首选：直接导出 `.glb/.gltf` 到 `res://assets/...`**
2. **次选：通过 Blender MCP 导出 `.glb/.gltf` 到 `res://assets/...`**
3. **保留：`goblend` 仅用于场景级试验或需要它特定扩展时**

原因：

- `glTF` 资产文件在项目树里清晰可见
- Godot 导入行为稳定，可直接验证
- 可实例化结果明确，便于后续挂到 `VisualRoot/AssetMount/...`

`goblend` 当前在本项目里是可用的，但它这次实测更偏向：

- 让 `.blend` 资源在 Godot 中表现为 `PackedScene`
- 导入缓存主要落在 `.godot/imported/`
- 不保证生成显式可见的 `res://goblend/scenes/*.tscn`

因此，**不要把 `goblend` 当成当前项目默认资产流**。

## 三条已验证路径

### 1. 直接 Blender CLI 导出 glTF

已验证样例：

- `res://assets/props/direct_cli/direct_cli_test.gltf`

结果：

- Blender 导出成功
- Godot 可导入
- `load()` 返回 `PackedScene`
- 可实例化为 `Node3D`

这是当前最推荐的默认路径。

### 2. Goblend 路径

已验证样例：

- `res://goblend/codex_goblend_test.blend`

结果：

- `goblend` 导出流程执行完成
- Godot 将 `.blend` 资源导入为 `PackedScene`
- 可实例化为 `Node3D`
- 但没有生成显式 `res://goblend/scenes/*.tscn`

适用场景：

- 你明确要保留 `.blend` 作为场景资源入口
- 你需要 `goblend` 的额外扩展逻辑

不适合作为默认资产流。

### 3. Blender MCP 导出 glTF

已验证样例：

- `res://assets/props/blender_mcp/blender_mcp_test.gltf`

结果：

- Blender MCP 导出成功
- Godot 经过一次导入延迟后可正常识别
- `load()` 返回 `PackedScene`
- 可实例化

适用场景：

- 需要在当前 Codex/Blender 联机会话里直接控制导出
- 需要边修改 Blender 场景边测试 Godot 导入

## 默认目录约定

### 运行时资产目录

运行时真正要被 Godot 使用的资产，统一放在：

```text
assets/
  characters/
  environment/
  props/
  materials/
```

细分建议：

```text
assets/
  characters/<asset_name>/
  environment/<asset_name>/
  props/<asset_name>/
```

示例：

```text
assets/props/letter/
assets/environment/room_a/
assets/characters/char_a/
```

### Blender 场景暂存目录

如果需要保留 Blender 场景副本或 `goblend` 试验资源，使用：

```text
goblend/
```

这里只用于：

- `.blend` 副本
- `goblend` 试验资源
- 非默认运行时入口

不要把团队默认运行时模型入口放在 `goblend/` 下。

## 默认文件格式约定

### 角色 / 环境 / 道具

默认首选：

- `.glb`
- `.gltf` + `.bin`

推荐顺序：

1. 单文件优先用 `.glb`
2. 需要显式拆分调试时用 `.gltf` + `.bin`

### 什么时候用 `.blend`

仅当你明确要：

- 在 Godot 中直接把 `.blend` 当 `PackedScene` 资源导入
- 或继续走 `goblend` 的特定工作流

否则不要把 `.blend` 当成默认交付格式。

## 命名规范

### 目录命名

- 小写
- 下划线分隔
- 避免空格
- 避免中文

示例：

- `char_a_guard`
- `room_demo_core`
- `obj_letter_small`

### 文件命名

导出文件名应直接表达用途：

- `char_a_idle.glb`
- `room_demo_core.glb`
- `obj_letter_small.gltf`

避免：

- `final.glb`
- `new_scene.gltf`
- `test2.glb`

## 导出策略

### 默认策略

对于要真正进项目的资产：

- **导出到 `res://assets/...`**
- **让 Godot 自动导入**
- **在 Godot 侧验证可 `load()`、可 `instantiate()`**

### 场景壳挂载策略

资产进入项目后，不要直接替换业务壳节点。

应继续遵守现有挂载约定：

```text
VisualRoot
  AssetMount
    RotationOffset
      ScaleOffset
        ImportedModel
```

也就是说：

- 资产负责可视表现
- `CharacterReplica` / `InteractiveObject` / `EnvironmentStateNode` 继续负责行为和协议

## Godot 导入验证标准

每个新资产进入项目后，至少验证以下 3 项：

1. 文件已落盘到 `res://assets/...`
2. Godot 侧 `load(path)` 返回非空资源
3. 如果是场景资源，`instantiate()` 成功

对于 `.gltf/.glb`：

- 如果刚导出完 `load()` 还失败，不要立刻判定坏掉
- 先执行一次文件系统刷新
- 再次验证

当前项目里，Godot MCP 已可用于这类验证。

## Goblend 使用规则

### 允许使用的情况

- 验证某个 `.blend` 资源能否在 Godot 中作为 `PackedScene` 使用
- 需要 `goblend` 特有扩展字段时
- 你明确接受产物主要体现在 `.godot/imported/`

### 不推荐作为默认路径的原因

在当前项目实测中：

- `goblend` 流程是通的
- 但没有给出显式 `res://goblend/scenes/*.tscn`
- 最终更像“Godot 直接导入 `.blend`”

所以除非你明确要这一行为，否则应优先选择纯 `glTF` 路径。

## 本地工具约定

### Godot MCP bridge

项目里提供了一键启动脚本：

- `scripts/start_godot_mcp_bridge.cmd`
- `scripts/start_godot_mcp_bridge.ps1`

使用方式：

```bat
scripts\start_godot_mcp_bridge.cmd
```

作用：

- 启动或复用本地 `godot-mcp-pro` WebSocket bridge
- 让 Godot 编辑器插件能够连接到本地 Node bridge

### Blender MCP

Blender MCP 适合：

- 在当前会话里驱动 Blender
- 执行导出
- 回读场景
- 做可视验证

但它不是默认资产规范本身，只是导出工具。

## 推荐工作流

### 道具 / 环境资产

1. 在 Blender 整理模型
2. 直接导出 `.glb/.gltf` 到 `assets/props/...` 或 `assets/environment/...`
3. 在 Godot 里刷新导入
4. 用 Godot MCP 验证 `load()` / `instantiate()`
5. 挂到现有 `AssetMount/.../ImportedModel`

### 角色资产

1. 在 Blender 整理角色模型
2. 导出到 `assets/characters/...`
3. 按当前项目角色挂载约定挂到 `CharacterReplica` / `KnightRoleSkin`
4. 继续保留外层 `CharacterReplica`

### Goblend 试验流

1. 把 `.blend` 副本放到 `goblend/`
2. 运行 `goblend`
3. 只把它当“可用性验证”
4. 如果最终要进入正式资产流，转为 `.glb/.gltf`

## 不要做的事

- 不要把 `.blend` 作为当前项目唯一默认运行时资产格式
- 不要把 `goblend` 结果和正式 `assets/...` 流混为一谈
- 不要把测试导出文件塞到最终角色/环境正式目录里
- 不要直接让导入资产替代行为壳节点
- 不要把朝向、缩放修正写死在业务脚本里

## 当前默认决策

当前仓库的默认资产导出约定如下：

- **默认交付格式：`.glb` / `.gltf`**
- **默认目标目录：`res://assets/...`**
- **默认导出优先级：直接 Blender 导出 > Blender MCP 导出 > Goblend**
- **默认运行时挂载位置：`VisualRoot/AssetMount/.../ImportedModel`**
- **`goblend/` 目录只作为试验和中间资源区，不作为正式资产交付入口**

如果未来 `goblend` 被验证能稳定生成我们需要的显式场景资源，再更新这份规范。
