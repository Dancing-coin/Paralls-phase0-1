# 当前项目具身骨骼状态提供层设计

- 日期：`2026-06-29`
- 状态：`implemented-and-verified`
- 上位规格：[2026-06-29-current-project-intelligence-upgrade-master-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-intelligence-upgrade-master-design.md)

## 1. 目标

把当前项目里本地身体/骨骼链掌握的骨骼空间真相，抽象成正式 Provider 层。

## 2. 当前现状

当前骨骼空间真相主要掌握在：

- `CharacterReplica`
- `KnightRoleSkin`
- `Skeleton3D`

后端角色智能体不掌握完整骨骼空间信息。

## 3. 设计目标

新增：

- `Embodied Skeletal State Provider`

它在本地完整掌握骨骼空间真相，并分层导出。

## 4. 三层导出

### A. 高层具身状态

供：

- 角色智能体
- 司命
- fusion

例如：

- posture
- gait
- balance
- strain
- active behavior
- hand readiness

### B. 中层骨架参数

供：

- 多模态链
- VLA
- 复杂具身判断

例如：

- 头、手、骨盆、脚的关键 anchor
- 关键朝向向量
- reach envelope
- 姿态特征

### C. 低层骨骼快照

供：

- 调试
- 回放
- 审核
- 特殊分析

不进入主运行时认知链。

## 5. 与其他规格关系

- 进入 `Perception Query Frame`
- 服务角色专属多模态栈
- 未来服务复杂物理交互与抓取系统

## 6. 一句话收束

这份规格的目标，是让当前项目的身体模块从“局部知道骨骼怎么动”升级为“能向更高层稳定导出具身骨骼状态”。
