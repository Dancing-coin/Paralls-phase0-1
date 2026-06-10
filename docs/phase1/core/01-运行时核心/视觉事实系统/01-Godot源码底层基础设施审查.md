# 01-Godot源码底层基础设施审查

## 状态

- 状态：入口页 / 引用页
- 上位正文： [Godot源码底层基础设施与运行时约束.md](/d:/Projects/Paralls/docs/phase1/core/00-总纲/Godot源码底层基础设施与运行时约束.md)

## 说明

本文件不再承载完整正文，只作为 `视觉事实系统` 文档簇中的入口页与引用点存在。

原因：

- `Godot` 源码底层可用基础设施不是只服务“视觉事实系统”
- 它同时约束：
  - 角色智能体本地执行层
  - 事件总线与线程安全边界
  - `AnimationTree` / `SkeletonModifier3D` 双轨结构
  - `Godot` 客户端接线方式
- 因此它应提升为 `00-总纲` 层的上位运行时约束文档

## 建议阅读顺序

1. [Godot源码底层基础设施与运行时约束.md](/d:/Projects/Paralls/docs/phase1/core/00-总纲/Godot源码底层基础设施与运行时约束.md)
2. [02-角色驱动方案A-B裁决与双总线架构.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/视觉事实系统/02-角色驱动方案A-B裁决与双总线架构.md)
3. [03-视觉事实系统总纲.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/视觉事实系统/03-视觉事实系统总纲.md)

## 一句话收束

`Godot` 源码底层基础设施文档已提升为 `00-总纲` 层约束文档；本页仅保留为运行时核心文档簇中的入口和引用页。
