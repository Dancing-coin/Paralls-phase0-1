# Spec 总入口

## 当前入口

| 层级 | 目录 | 作用 | 当前口径 |
|---|---|---|---|
| 主线 | [world-character-siming-authority-mainline](world-character-siming-authority-mainline/README.md) | 世界、角色、司命统一运行时 | 当前主线真相 |
| 增量专题 | [current-project-intelligence-upgrade](current-project-intelligence-upgrade/README.md) | 感知、多模态、VLA、具身和工具链增量 | 不重定义主线 |
| 历史平铺 | 本目录根部的日期文件 | 早期设计、迁移记录和历史方案 | 默认只读、仅作追溯 |

## 文档分类

- `master / program`：母规格或程序级设计。
- `design / subspec`：可执行边界、接口和验收设计。
- `audit / closure / baseline / decision / freeze`：状态、审计、冻结和决策记录；不能替代设计规格。
- `README`：树级入口、依赖和导航；不承载逐条实现日志。
- `historical / superseded`：保留历史证据，但不作为当前实现依据。

## 状态字段

后续统一按四个维度记录状态，避免把多个含义拼成一行：

- 生命周期：`draft` / `approved` / `active` / `superseded`
- 实现：`unplanned` / `planned` / `partial` / `implemented`
- 证据：`unverified` / `focused-verified` / `runtime-verified`
- 阻塞：`none` / `deferred` / `owner-contract-blocked`

现有文档中的自由文本状态暂不改写；阶段 2 再逐文件映射。

## 近期保护范围

2026-09-10 至 2026-09-24 新增的 12 份 spec 已列入保护清单。在关系索引和链接迁移完成前，它们保持现有路径和文件名。

详见 [_governance/protected-recent-2026-09.md](_governance/protected-recent-2026-09.md)。

## 重要限制

- 本阶段不移动 501 份 spec。
- 不把“窄垂直已验证”升级为“整个领域完成”。
- 不把 plan、audit 或 completion record 当成 spec 的替代品。
- 不在没有链接验证和用户复核的情况下做批量重命名。
