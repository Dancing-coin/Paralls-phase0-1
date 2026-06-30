# 当前项目智能体与世界交互增量专题母规格

- 日期：`2026-06-29`
- 状态：`implemented-and-verified`
- 适用范围：仅适用于当前项目 `paralls-phase-0-demo`
- 文档类型：`mainline 已闭合后的增量专题母规格`
- 上位主线：[2026-06-29-world-character-siming-authority-mainline-master-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-world-character-siming-authority-mainline-master-design.md)
- 主线闭合审计：[2026-06-30-mainline-plan-closure-matrix.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-30-mainline-plan-closure-matrix.md)

## 1. 文档目标

本文档是当前项目在 dedicated mainline plan tree 已闭合之后，继续推进增量智能体能力时使用的专题母规格。

它不替代 mainline 主规格，而是负责：

1. 定义总目标
2. 固定术语
3. 固定分层边界
4. 给各子规格建立统一上下文
5. 解释在 mainline 已闭合之后，哪些感知、多模态、交互和工具链升级仍值得继续展开，并为后续新的增量计划提供设计基础

这份母规格的口径必须始终满足四个前提：

- 当前项目继续只服务游戏场景
- 当前项目不直接转成机器人项目
- `character mind core` 已是完成真相
- `world-character-siming-authority-mainline` 已是仓库主线真相

因此，这份规格树不再承担“定义仓库主线目标”的责任，而只承担“定义 mainline 之后的增量专题升级方向”的责任。

## 2. 当前专题树的目标

当前专题树的目标不是重新定义“当前项目做什么”，因为这个问题已经由 mainline 主规格回答。

当前专题树的目标是：

- 在 `world-character-siming-authority` 主线已闭合的前提下
- 为后续增量任务提供一组专题设计
- 重点展开主线中尚未细写透的感知、多模态、空间协议、双通道交互与工具链能力

一句话说：

> 这套专题规格树不负责重新定义主线，而负责定义“主线之后还要继续补强哪些能力，以及这些能力之间如何组织”。

## 3. 非目标

当前项目的升级不追求：

- 直接变成通用机器人系统
- 直接变成未来 `Robot OS`
- 用一套端到端大模型替代全部运行时分层
- 一次性实现完整真实物理世界
- 一次性实现全通用抓取、全通用战斗、全通用环境交互

同时，本项目也不应误走两条路：

1. 只继续堆 `MainDemoController` 和局部 glue code
2. 直接为了未来机器人系统而破坏当前游戏项目的验证边界

## 4. 为什么在主线闭合后仍然需要这套专题规格

主线闭合并不等于：

- 全仓库所有潜在升级都已完成
- 感知、多模态、局部世界协议都已设计完毕
- 司命与角色的多模态专题都已收口

根据主线闭合矩阵，当前明确已闭合的是 dedicated mainline plan-tree scope，
而不是“更广泛的一切后续能力探索”。

因此，这套专题规格仍然有必要，因为它继续回答：

1. 如何把角色的局部世界感知做厚
2. 如何把 `Godot` 升级为真正的取样前端
3. 如何把 VLA 和多模态能力以不污染上下文、不拖慢运行时的方式接入
4. 如何让司命拥有自己的多模态态势理解
5. 如何把 `ESM` 从语义结算主导继续演进成双通道世界作用层

## 5. 总体设计原则

### 5.1 继续服从现有主线

主线已经固定的这条 runtime 主链不推翻：

`L1 事实上抛 -> authority/backend -> 候选感知 -> 角色私有感知 -> 角色智能体运行时`

本专题树的所有工作，都是在这条主链之上补层、补对象、补能力。

### 5.2 Godot 是具身前端，不是认知宿主

`Godot` 的定位保持：

- 本地具身表现宿主
- 本地高频执行层
- 取样前端
- 世界局部观察前端

但它不应承担：

- 重体素化
- 重多模态推理
- 大模型空间理解

### 5.3 结构化事实上抛与多模态链并存

未来当前项目不走：

- 纯文本智能体
- 纯视觉大模型智能体

而走：

- 结构化事实上抛主链
- VLA 空间视觉理解子链
- 多模态慢通路辅助理解
- 统一感知对象

### 5.4 角色与司命必须上下文隔离

角色智能体和司命智能体可以共享：

- 世界事实
- 公共接口
- 模型调度基础设施

但不能共享：

- 多模态运行时上下文
- 私有 patch 会话
- 推理历史
- 中间缓存

### 5.5 语义驱动与物理驱动必须长期并存

当前项目未来不应只保留一种交互方式。

必须长期支持：

- `语义驱动交互系统`
- `物理驱动交互系统`

并通过统一交互编排层管理它们，而不是让两套系统平行失控。

## 6. 总体分层

当前专题树覆盖的增量分层如下：

1. `L1 世界事实层`
2. `Scene 3D Space Model`
3. `Runtime Spatial Occupancy Field`
4. `Godot 取样前端`
5. `Perception Query Frame`
6. `角色智能体专属多模态栈`
7. `司命专属多模态栈`
8. `角色专属 Fusion`
9. `司命专属 Fusion`
10. `Modality Interpretation Result`
11. `Cross-Modal Understanding Result`
12. `Canonical Percept Bundle`
13. `Actor Scene Knowledge`
14. `CharacterAgentRuntime`
15. `SimingRuntime`
16. `Interaction Orchestration Layer`
17. `ESM` 双通道世界作用层

下面给每层做简要摘要。

## 7. `L1` 世界事实层摘要

`L1` 不再只是“一组 emitter”。

升级后它应包含两大内核：

### 7.1 静态空间真相

即：

- `Scene 3D Space Model`

来源不是手工逐个模型建表，而是：

- 节点命名
- 子节点结构
- 碰撞体
- 导航区
- 环境节点
- 自动空间语义抽取
- 多模态自动补语义
- 人工只审核

### 7.2 动态空间真相

即：

- `Runtime Spatial Occupancy Field`

它维护：

- 动态占据
- 可通行状态
- 遮挡变化
- 环境场变化
- 临时阻挡和局部世界变化

### 7.3 `L1` 继续输出事实

在这两个底座之上，`L1` 继续输出结构化事实上抛：

- `raw_fact_event`
- `visual_fact`
- `auditory_fact`
- `spatial_access_fact`
- `world_result`
- `state_machine_transition`

但未来的事实上抛不应只来自局部脚本判断，而应更多来自统一空间和世界状态表示。

## 8. Godot 取样前端摘要

`Godot` 在升级后的系统里，不是重理解器，而是取样器。

它通过四类 Provider 为多模态链提供输入：

- `Visual Patch Provider`
- `Spatial Patch Provider`
- `Auditory Context Provider`
- `Embodied State Provider`

它们共同生成：

- 局部截图
- 局部空间 patch
- 听觉时间窗
- 身体状态切片

这些内容不会直接给角色智能体，而是先进入统一取样协议。

## 9. `Perception Query Frame` 摘要

`Perception Query Frame` 是多模态链的统一取样协议。

它的作用是：

- 统一时间窗
- 统一空间参考系
- 统一主体视角
- 统一关注上下文
- 把视觉、空间、听觉、环境、身体输入收成一次“这一拍如何看世界”的查询对象

它不是感知结果，而是感知请求对象。

## 10. 多模态栈摘要

### 10.1 不做统一多模态脑

当前项目不做一个全局共享的统一多模态脑。

正确方式是：

- 共享多模态能力平台
- 角色智能体有自己的多模态栈
- 司命有自己的多模态栈
- 非运行时工具有自己的工具栈
- 非运行时生产工具有自己的生产栈

### 10.2 角色智能体专属多模态栈

关注：

- 局部空间理解
- 遮挡与路径判断
- 局部环境压力
- 身体可达性
- 局部目标可见性

### 10.3 司命专属多模态栈

关注：

- 多角色全局分布
- 信息可见性失衡
- 环境变化对戏剧公平的影响
- 全局态势变化

### 10.4 `VLA` 的位置

`VLA` 在当前项目里不是主脑，而是：

- 空间视觉理解子链

它主要处理：

- occupancy / voxel / BEV / 局部视觉 patch

输出：

- 参数化结构化空间理解结果
- 可选文本摘要

### 10.5 `SIMA2` 风格慢通路的角色

`SIMA2` 风格多模态能力更适合在当前项目中承担：

- 高歧义局势理解
- 长程全局多模态辅助判断
- 慢通路顾问

不适合进入实时主执行链。

## 11. 感知结果三层摘要

当前项目建议采用三层结果：

### 11.1 `Modality Interpretation Result`

单模态解释结果。

分别针对：

- 视觉/空间
- 听觉
- 身体状态
- 环境状态

### 11.2 `Cross-Modal Understanding Result`

真正的多模态理解层。

输出：

- 世界假设
- 置信度修正
- 模态冲突与缺失
- 注意力更新

### 11.3 `Canonical Percept Bundle`

最终统一输入对象。

这是角色智能体和司命真正消费的感知结果。

## 12. 角色智能体升级摘要

当前角色智能体未来不应继续主要依赖：

- 单条 fact
- 文本摘要

而应依赖：

- `Canonical Percept Bundle`
- `Actor Scene Knowledge`
- memory bundle

### 12.1 `Actor Scene Knowledge`

这是角色自己的场景知识层。

它保存：

- 空间知识
- 障碍/遮挡/路径知识
- 环境变化经验
- 来源
- 置信度
- 新鲜度
- 冲突状态

### 12.2 主动感知

角色智能体还需要：

- 换角度观察
- 靠近确认
- 暂停探查
- 失败后重查

不能总是被动吃输入。

## 13. 司命升级摘要

司命未来也要有自己的感知中间层，而不是只吃 authority 事件和规则。

它需要：

- 自己的多模态栈
- 自己的 Fusion
- 自己的感知包

并用这些能力增强：

- `FairnessStateSnapshot`
- 干预候选
- 最小催化路径
- 工作台解释

## 14. 交互系统升级摘要

### 14.1 语义驱动与物理驱动并存

当前项目未来必须长期支持：

- `语义驱动交互系统`
- `物理驱动交互系统`

### 14.2 不做两套互不相干系统

这两条路不能成为两套平行世界。

它们必须：

- 共享世界状态底座
- 共享结果协议
- 共享认知回流接口

### 14.3 统一抽象：`Interaction Orchestration Layer`

不再把并行模式和协作模式当成两个大系统。

统一抽象为：

- `Interaction Orchestration Layer`

它负责：

- 判断交互意图
- 判断可用通道
- 分配通道职责
- 决定单通道还是多通道协作
- 决定结果如何合并回世界

### 14.4 `ESM` 的演进方向

当前 `ESM` 仍主要是：

- 语义驱动 authority settlement layer

未来应演进成：

- `Semantic Interaction Channel`
- `Physical Interaction Channel`

共存的世界作用层。

## 15. 身体模块升级摘要

### 15.1 现状

当前骨骼空间真相主要掌握在：

- `CharacterReplica`
- `KnightRoleSkin`
- `Skeleton3D`

后端角色智能体只掌握粗粒度动作和状态，不掌握完整骨骼空间。

### 15.2 未来新增

新增：

- `Embodied Skeletal State Provider`

它应在本地完整掌握骨骼空间真相，并分三层导出：

1. 高层具身状态
2. 中层骨架参数
3. 低层骨骼快照

它的输出将进入：

- `Perception Query Frame`
- 角色多模态链
- 复杂具身判断

## 16. 非运行时两类工具链摘要

当前项目未来还需要明确区分：

### 16.1 `Non-Runtime Tool Stack`

服务：

- 审核
- 回放
- 分析
- 调试工作台

### 16.2 `Non-Runtime Production Stack`

服务：

- 场景语义抽取
- 建模注入
- 资产处理
- 场景知识生成
- 数据集构建

### 16.3 自动化原则

场景空间语义形成采用：

- 建模命名
- 场景结构
- 自动抽取
- 多模态自动识别
- 人工只审核

不走人工逐项补全。

## 17. 专题子规格体系

当前母规格之下，专题增量工作拆成以下子规格：

1. `当前项目 VLA 与多模态感知升级设计`
   - 已存在：
   - [2026-06-28-current-project-vla-multimodal-upgrade-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-28-current-project-vla-multimodal-upgrade-design.md)

2. `L1 世界事实层与空间底座设计`
3. `Perception Query Frame 与感知结果协议设计`
4. `角色智能体多模态链与 Actor Scene Knowledge 设计`
5. `司命多模态链与全局态势理解设计`
6. `ESM 双通道世界作用层设计`
7. `Interaction Orchestration Layer 设计`
8. `Godot 取样前端与 Provider 设计`
9. `Embodied Skeletal State Provider 设计`
10. `非运行时工具链与生产工具链设计`

说明：

第 1 份子规格已经写出，但它不是 mainline 总纲，只是本专题树中的第一份增量设计。

## 18. 与主线规格的关系

这套规格树与主线规格的关系是：

- `world-character-siming-authority-mainline` 定义主线真相
- 本专题树定义 mainline 之后的增量专题工作

因此：

- 本树不能重写 `character mind core completed truth`
- 本树不能重定义 repo-mainline mission
- 本树不能把已闭合的 dedicated mainline plan tree 再说成“待补主线”

它只能：

- 补充主线尚未细写的专题设计
- 为未来新的增量任务做准备
现有：

- [2026-06-28-current-project-vla-multimodal-upgrade-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-28-current-project-vla-multimodal-upgrade-design.md)

现在应视为：

- 本专题树下的第一份专题子规格

其内容有效，但后续应按“mainline 已闭合后的增量工作”口径继续拆细。

## 19. 一句话收束

当前专题树的正确定位不是：

- 重新定义当前项目主线
- 重新补做已经闭合的 dedicated mainline tree

而是：

> 在已闭合的 `world-character-siming-authority` 主线之上，把世界真相底座、Godot 取样前端、多模态/VLA链、角色与司命各自独立的融合层、场景知识层、双通道交互系统和具身身体状态层继续专题化补齐，作为后续 mainline 增量任务的设计储备。
