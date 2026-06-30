# 当前项目司命多模态链与全局态势理解设计

- 日期：`2026-06-29`
- 状态：`awaiting-user-review`
- 上位规格：[2026-06-29-current-project-intelligence-upgrade-master-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-intelligence-upgrade-master-design.md)

## 1. 目标

让司命不再只依赖 authority 事件和规则判断，而具备自己的多模态全局态势理解能力。

## 2. 司命专属多模态栈

司命的关注对象不是角色局部世界，而是：

- 多角色空间分布
- 信息可见性失衡
- 环境变化趋势
- 证据链和暴露链
- 参与窗口是否被压制

它的 patch 范围和时间窗应大于角色智能体。

## 3. 司命专属 Fusion

司命 fusion 负责融合：

- authority event
- `world_result`
- `visual_fact`
- `environment_state_result`
- 司命专属多模态结果

输出：

- 司命版感知包

这个感知包进一步增强：

- `FairnessStateSnapshot`
- 干预候选
- 最小催化路径
- 工作台解释

## 4. 输出边界

即使司命拥有更强局势理解能力，它也仍然不直接：

- 控制角色低层动作
- 改写世界物理真相
- 越权替角色做最终行为选择

司命只增强：

- 判断
- 催化
- 解释

## 5. 与角色智能体的关系

角色和司命可以共享：

- 世界事实
- 公共模型平台
- 结构化输出契约

但不能共享：

- patch 上下文
- 私有多模态缓存
- 推理历史

## 6. 一句话收束

这份规格的目标，是让司命真正拥有自己的“导演视角世界理解”，而不是继续只靠结构化事件流做规则判断。
