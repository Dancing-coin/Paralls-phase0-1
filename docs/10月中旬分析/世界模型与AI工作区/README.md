# 世界模型与 AI 工作区

状态：`architecture analysis; proposed and non-authorizing`

日期：2026-10-12

## 目的

把现有 3D 世界底座发展成一个可以承载多类 AI 模型协作的工作区：模型可以读取经过授权的视觉、空间、时间、实体、角色视角和游戏状态数据；可以提出预测、计划、内容、动作和资产修改；运行时可以把经过验证的结果投影回 3D 世界；所有结果都能审计、回放、撤销和重新规划。

这里的“工作区”不是让世界模型直接接管 Godot，也不是把 3D 场景变成模型的上下文窗口。它是一个有版本号的共享状态和工具边界：模型在其中工作，authority 在其中裁决，Godot 在其中表现。

## 白话结论

可以把系统想成一个真实城市的“市政档案、现场摄像、演员和施工审批”共同工作的地方：

1. Backend 保存“城市到底发生了什么”。
2. Godot 负责玩家眼前的建筑、角色身体、碰撞和声音。
3. LLM 负责理解目标、关系和长期计划。
4. 多模态模型负责从画面、声音和空间数据中提取观察。
5. 视觉世界模型负责补全或预测画面变化，隐空间世界模型负责更快地预测未来子目标。
6. 世界动作模型负责提出动作序列或动作块。
7. Harness 把它们放进同一个版本化工作区，检查权限、前置条件、物理和时效，再把结果交给 authority。

## 已找到的依据

| 材料 | 本批如何使用 | 不能推出的结论 |
|---|---|---|
| `docs/上下文不够用/LAWAM.md` | 记录 LaWAM 的隐空间视觉子目标、隐动作和低延迟预测路线 | 不能证明 LaWAM 能读写 Godot 实体、碰撞或世界真相 |
| P7C world-model proposal boundary | 复用 scope-filtered snapshot、proposal、expiry、calibration、zero-write 边界 | 不能推出完整 world model runtime 已实现 |
| `docs/上下文不够用/对话4.md` 1180-2154 段 | 复用 World Pack Compiler、分层模拟、World Action Harness 和 typed blackboard 思路 | 对话内容是设计来源，不是代码证据 |
| `docs/架构/运行时/模块/VLA运行时通道.md` | 复用 PQF、provider refs、scoped cache、advisory result、冲突记录和 no-authority-write | VLA 当前是感知 advisory 慢路径，不是世界动作闭环 |
| `backend/app/world_runtime/*` | 作为现有 adapter、L1、空间、时间、provider readiness 和人口 cadence 的接入点 | 没有统一的 world model contract 或动态资产准入闭环 |

## 文件结构

```text
世界模型与AI工作区/
  AGENTS.md
  README.md
  规格/
    00-多模型世界工作区总规格.md
    01-World-Runtime-Contract统一工作区契约.md
    02-模型类别适配与权限路由规格.md
    03-上下文窗口与时空数据分层规格.md
    04-实时交互预测预演与可逆提交规格.md
    05-World-Pack资产场景与实体绑定规格.md
    06-World-Action-Harness与机器人沙盒兼容规格.md
  计划/
    00-世界模型工作区分阶段实施计划.md
  审查/
    00-现有实现与外部研究映射.md
  回写/
    00-对十月分析原文的补充与修正登记.md
```

## 阅读顺序

1. [规格/00-多模型世界工作区总规格](规格/00-多模型世界工作区总规格.md)
2. [规格/01-World-Runtime-Contract统一工作区契约](规格/01-World-Runtime-Contract统一工作区契约.md)
3. [规格/02-模型类别适配与权限路由规格](规格/02-模型类别适配与权限路由规格.md)
4. [规格/03-上下文窗口与时空数据分层规格](规格/03-上下文窗口与时空数据分层规格.md)
5. [规格/04-实时交互预测预演与可逆提交规格](规格/04-实时交互预测预演与可逆提交规格.md)
6. [规格/05-World-Pack资产场景与实体绑定规格](规格/05-World-Pack资产场景与实体绑定规格.md)
7. [规格/06-World-Action-Harness与机器人沙盒兼容规格](规格/06-World-Action-Harness与机器人沙盒兼容规格.md)
8. [计划/00-世界模型工作区分阶段实施计划](计划/00-世界模型工作区分阶段实施计划.md)
9. [审查/00-现有实现与外部研究映射](审查/00-现有实现与外部研究映射.md)

## 当前决策

- 采用“统一合同 + 多 adapter + 现有 authority”混合架构。
- 视觉世界模型可先做表现和观察增强；隐空间/世界动作模型可做预测和动作候选；两者都不能直接提交事实。
- 近场交互由 Godot 物理和现有执行链确认，远场可以使用低成本抽象模拟或模型预测。
- 3D 资产不是模型输出后就可用；必须经过 World Pack Compiler、实体绑定、碰撞/导航/affordance/物理 profile 和 provenance 准入。
- 上下文窗口通过分层快照、角色私有视角、区域切片、摘要和可追溯引用解决，而不是把整个城市塞给模型。
- 机器人沙盒兼容通过环境 adapter 和相同的 observation/action/replay contract 实现；不把机器人控制频率混入游戏 LLM 决策频率。

## 范围

本批服务开放世界运行时。自走棋单局运行时、编辑器 control-plane、AD/Blender 正式动作资格链继续 deferred；它们不阻断本目录的合同设计，但会作为外部依赖记录。
