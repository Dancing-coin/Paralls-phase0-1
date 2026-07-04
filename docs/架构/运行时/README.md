# 运行时架构文档索引

状态：当前运行时架构入口

本目录承接运行时级架构文档。它属于 `docs/架构/`，不是普通运行手册，也不是历史计划文档。

## 文件结构

| 层级 | 文件 | 作用 |
| --- | --- | --- |
| 总纲 | `运行时总览.md` | 运行时级架构、时序和数据流入口 |
| 覆盖 | `运行时覆盖矩阵.md` | 运行时领域、owner、契约、验证和缺口矩阵 |
| 边界 | `运行时命名边界审计.md` | `Runtime` 命名和 L1/ESM 边界审计 |
| 图表 | `图表/整体运行时时序图.md` | 可渲染 Mermaid 时序图 |
| 图表 | `图表/整体运行时数据流图.md` | 可渲染 Mermaid 数据流图 |
| 模块 | `模块/世界运行时.md` | `backend/app/world_runtime/` 基础设施大类 |
| 模块 | `模块/SystemL1.md` | System L1 |
| 模块 | `模块/SystemL6事件总线.md` | System L6 authority event bus、路由、回放、审计辅助边界 |
| 模块 | `模块/Siming.md` | Siming 全局态势、高层 catalyst 与 L6 事件边界 |
| 模块 | `模块/角色智能体.md` | 角色智能体 |
| 模块 | `模块/ESM与交互编排.md` | ESM、交互编排、物理通道 |
| 模块 | `模块/Godot表现与角色入口.md` | Godot 输入、表现、角色入口 |
| 模块 | `模块/VLA运行时通道.md` | 已实现的 VLA 慢路径运行时 |
| 模块 | `模块/模型服务通道.md` | 模型 provider readiness 与真实调用证明 |
| 模块 | `模块/Harness验证证据.md` | Harness profile 与证据产物 |

## 维护规则

- 新增跨域图表放 `图表/`。
- 新增运行时 owner 或模块放 `模块/`。
- 不把历史 plan/spec 移入本目录；那些继续留在 `docs/superpowers/`。
- 不把操作 runbook 移入本目录；运行和验证入口继续由 `docs/harness.md` 等文档承接。
