# Phase 0 Demo Asset Injection Guide

这份文档说明如何把当前 `Phase 0` 演示从灰盒占位体逐步替换成商业级 3D 资产，同时不破坏现有 Godot / backend 联调闭环。

## 目标

保留：
- 当前行为壳
- 当前协议字段
- 当前 Phase 0 联调能力

替换：
- 角色可视体
- 房间环境
- 道具模型
- 灯具 / 环境状态点的可视体

## 当前替换骨架

### 1. 角色

当前角色壳：
- `res://scenes/phase0/CharacterReplica.tscn`

必须保留的节点和职责：
- `CharacterReplica`
  - 行为壳
  - 挂 `CharacterReplica.gd`
- `SpatialVoiceController`
  - 空间音频 / 语音承接
- `Nameplate`
  - 调试和焦点提示
- `VisualRoot`
  - 可视层容器
- `VisualRoot/AssetMount`
  - 商业资产挂载点
- `VisualRoot/AssetMount/RotationOffset`
  - 角色朝向修正节点
- `VisualRoot/AssetMount/RotationOffset/ScaleOffset`
  - 角色缩放修正节点
- `VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel`
  - 实际导入模型的推荐挂载点
- `VisualRoot/GreyboxBodyRoot`
  - 当前灰盒占位体

你应当替换的是：
- `VisualRoot/AssetMount` 下的可视内容
- 优先把真正的模型挂到 `ImportedModel`

推荐做法：
- 导入 `glb/gltf` 后实例化到 `VisualRoot/AssetMount`
- 如果朝向不对，改 `RotationOffset`
- 如果比例不对，改 `ScaleOffset`
- 保持业务脚本仍在外层壳节点

### 2. 主场景

当前主场景：
- `res://scenes/phase0/MainDemo.tscn`

当前灰盒环境由这些节点组成：
- `RoomVisualRoot/RoomAssetMount`
- `RoomVisualRoot/RoomAssetMount/RotationOffset`
- `RoomVisualRoot/RoomAssetMount/RotationOffset/ScaleOffset`
- `RoomVisualRoot/RoomAssetMount/RotationOffset/ScaleOffset/ImportedRoom`
- `RoomVisualRoot/GreyboxRoomRoot`
- `RoomVisualRoot/TableVisualRoot/TableAssetMount`
- `RoomVisualRoot/TableVisualRoot/TableAssetMount/RotationOffset`
- `RoomVisualRoot/TableVisualRoot/TableAssetMount/RotationOffset/ScaleOffset`
- `RoomVisualRoot/TableVisualRoot/TableAssetMount/RotationOffset/ScaleOffset/ImportedTable`
- `RoomVisualRoot/TableVisualRoot/GreyboxTableRoot`

推荐替换方式：
- 把商业级房间资产挂到 `RoomVisualRoot/RoomAssetMount`
- 把商业级桌子资产挂到 `RoomVisualRoot/TableVisualRoot/TableAssetMount`
- 朝向修正统一放在 `RotationOffset`
- 缩放修正统一放在 `ScaleOffset`
- 灰盒节点逐个下线，而不是一次性删光

### 3. 交互物

当前交互物壳：
- `res://scenes/phase0/InteractiveObject.tscn`

必须保留：
- `InteractiveObject`
- `object_id`
- 当前脚本和状态回写
- `VisualRoot`
- `VisualRoot/AssetMount`
- `VisualRoot/AssetMount/RotationOffset`
- `VisualRoot/AssetMount/RotationOffset/ScaleOffset`
- `VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel`
- `VisualRoot/GreyboxPropRoot`

你应当替换的是：
- `VisualRoot/AssetMount` 下的可视内容

### 4. 环境状态点

当前环境壳：
- `res://scenes/phase0/EnvironmentStateNode.tscn`

建议最终替换成：
- 墙灯
- 吊灯
- 门边警示灯
- 灯槽 / 光源面板

保留：
- `EnvironmentStateNode`
- 当前脚本
- `target_environment_id` 的语义
- `VisualRoot`
- `VisualRoot/AssetMount`
- `VisualRoot/AssetMount/RotationOffset`
- `VisualRoot/AssetMount/RotationOffset/ScaleOffset`
- `VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel`
- `VisualRoot/GreyboxFixtureRoot`

## 推荐挂载规范

所有商业资产统一按这个层级挂：

```text
AssetMount
  RotationOffset
    ScaleOffset
      ImportedModel
```

用途：
- `AssetMount`：保留挂载入口
- `RotationOffset`：统一修正朝向
- `ScaleOffset`：统一修正比例
- `ImportedModel`：真正放导入场景或网格

这样后续你替换资产时不会把：
- 行为脚本
- 调试节点
- 状态节点
- 焦点逻辑

跟可视模型搅在一起。

## 资产导入顺序建议

1. 先替换 `EnvironmentStateNode`
2. 再替换 `InteractiveObject`
3. 再替换 `CharacterReplica`
4. 最后替换房间整体

原因：
- 灯具和道具最容易提升质感
- 风险最小
- 不容易破坏行为逻辑

## 文件夹约定

```text
assets/
  characters/
  environment/
  props/
  materials/
```

## 导入建议

- 优先 `.glb`
- 单个资产单独文件夹
- 角色、房间、道具分开管理
- 文件名尽量稳定，减少 Godot 引用抖动

## 不要做的事

- 不要把业务脚本直接挂到导入模型根节点
- 不要删除 `CharacterReplica` / `InteractiveObject` / `EnvironmentStateNode` 壳节点
- 不要改 `actor_id` / `object_id` / `target_environment_id` 这些协议相关字段
- 不要一口气把所有灰盒节点删掉后再慢慢补

## 每次替换后的验证

角色替换后至少验证：
- 场景能打开
- 焦点高亮仍然工作
- `dialogue_applied` 仍然出现

道具替换后至少验证：
- `phase0_interact_target:obj_letter`
- `object_state:obj_letter:...`

环境替换后至少验证：
- `environment_state:alerted`
- 场景里可见颜色 / 灯光 / 材质变化

## 当前最建议你先准备的三类资产

1. 一套双角色低多边形或半写实人形
2. 一套小型室内房间资产
3. 一个桌面核心证物道具

如果你把第一批 `.glb` 资产放进这些目录，我就可以继续帮你做：
- 节点挂载
- 材质和缩放修正
- pivot / 朝向修正
- 保留现有 Phase 0 行为闭环
