# 当前项目 VLA 与多模态感知增量设计

- 日期：`2026-06-28`
- 状态：`awaiting-user-review`
- 适用范围：仅适用于当前项目 `paralls-phase-0-demo`
- 不适用范围：不直接用于未来 `Robot OS` 项目
- 上位规格：[2026-06-29-current-project-intelligence-upgrade-master-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-intelligence-upgrade-master-design.md)

## 1. 文档目标

本文档定义当前项目在 mainline 已闭合之后，围绕 `L1` 事实上抛主链、角色智能体、司命、VLA 与多模态感知继续展开的增量专题设计。

这份设计不是为了把当前项目改造成通用机器人系统，也不是为了重写已闭合的 mainline，而是为了在以下主线事实成立后继续补强：

- `world-character-siming-authority` mainline 已闭合
- `character mind core` 已是完成真相

在此前提下，把当前项目继续补强为：

- 结构化事实上抛主链
- VLA 空间视觉理解子链
- 多模态慢通路辅助理解
- 角色与司命各自独立的融合与感知上下文
- 更完整的局部世界感知与场景知识

一句话：

> 当前项目继续只服务游戏场景；在 mainline 已闭合之后，这份专题设计负责继续补强角色与司命如何基于结构化事实、多模态空间理解和统一感知对象来运行。

## 2. 设计前提

### 2.1 当前项目继续只服务游戏场景

当前项目不承担通用机器人运行时职责。

它的目标仍然是：

- 游戏内具身角色
- 游戏内世界状态与权威结算
- 游戏内司命催化
- 游戏内多角色戏剧运行时

### 2.2 不推翻现有主链

当前已经成立的这条主链继续保留：

`L1 事实上抛 -> authority/backend -> 候选感知 -> 角色私有感知 -> 角色智能体运行时`

本设计是在此基础上补厚，而不是废弃重来。

### 2.3 运行时性能是硬约束

以下约束必须成立：

- 不能让 `Godot` 重扫描重建模
- 不能让 `Godot` 跑重体素化
- 不能让 `Godot` 跑大模型推理
- 不能让多模态能力阻塞角色智能体和司命的主循环
- 慢通路永不反压快通路

### 2.4 上下文隔离是硬约束

角色智能体和司命智能体的多模态上下文必须完全隔离：

- 不共享推理历史
- 不共享缓存上下文
- 不共享隐状态
- 不共享私有 patch 会话

可以共享：

- 世界事实
- 结构化输出契约
- 调度与 trace 基础设施

不能共享：

- 脑内上下文

## 3. 当前项目的核心问题

当前项目不是没有世界，也不是没有感知链。

当前问题在于：

1. `L1` 的事实上抛器还不够完整
2. 候选感知编译层还是“一条事实 -> 一条候选”
3. `Per-Character` 过滤器过薄
4. 角色拿到的是碎片事实，不是局部世界
5. LOS / 可达性 / 遮挡 / 环境压力很多还是在前端执行时才发现
6. VLA 和多模态能力还没有被正式纳入当前项目主架构

因此，角色现在更像“听汇报”，而不是“自己在看、听、记、修正世界”。

## 4. 总体设计

当前项目的升级总方向定义为：

`L1 世界事实层 + VLA 空间视觉理解子链 + 角色/司命独立多模态栈 + 各自融合层 + 统一感知对象 + 场景知识层 + 角色/司命运行时`

### 4.1 顶层数据流

```text
Godot 场景 / 玩家输入 / ESM / 事实上抛器
    ->
L1 世界事实层
    ->
Perception Query Frame
    ->
角色智能体专属多模态栈 ----\
                             -> 角色专属 Fusion -> Canonical Percept Bundle -> CharacterAgentRuntime
司命专属多模态栈 ----------/

L1 结构化事实 / world_result / siming_input ------\
                                                   -> 司命专属 Fusion -> Siming Percept Bundle -> SimingRuntime
司命专属多模态栈 ----------------------------------/
```

注意：

- `VLA` 只属于专属多模态栈的一部分，不取代整个感知系统
- `Fusion` 不是全局单例，角色和司命各有自己的 fusion
- 结构化事实上抛与多模态结果在各自内部融合后，才进入各自智能体

## 5. L1 世界事实层

### 5.1 正确认知

当前项目中的 `Godot` 世界本体已经存在：

- 场景
- 建模
- 物体
- 角色
- 碰撞
- 区域
- 环境节点

本设计不是从零造一个新世界。

需要补的是：

> 把现有 `Godot` 世界整理成 `L1` 内部统一可计算的空间语义层，并从中稳定导出结构化事实。

### 5.2 `L1` 内部新增两个显式层

#### A. `Scene 3D Space Model`

这是 `L1` 的静态空间真相底座。

它不是人工逐个模型建表，而是：

- 利用建模文件中的节点命名、子节点命名、资源路径、场景结构
- 利用碰撞体、导航区、区域体积、环境节点
- 自动抽取
- 多模态自动补语义
- 人工只做审核

它至少表达：

- 静态障碍
- 门洞/连接点
- 区域划分
- 遮挡候选
- 对象实例
- 环境节点

#### B. `Runtime Spatial Occupancy Field`

这是 `L1` 的动态空间真相底座。

它表达：

- 动态占据
- 可通行/不可通行
- 遮挡变化
- 环境场变化
- 临时阻挡

### 5.3 生成策略

采用混合策略：

- 静态部分离线生成
- 动态部分运行时增量更新

理由：

- `Godot` 中场景建模很重
- 不能让实时渲染被重扫描和重体素化拖累
- 需要保留运行时动态环境变化的表达能力

## 6. Godot 侧能力：取样器而非理解器

### 6.1 Godot 的职责

`Godot` 在多模态链中的职责不是“理解世界”，而是“按主体视角取样世界”。

它负责：

- 按角色当前视野截取局部视觉样本
- 按角色当前位置和朝向裁局部空间 patch
- 提供短时间窗听觉上下文
- 提供身体状态切片

它不负责：

- 大模型推理
- 大规模场景理解
- 高层语义综合

### 6.2 需要的 Provider

#### A. `Visual Patch Provider`

提供：

- 当前角色视野截图
- 目标局部截图
- 多角度局部截图
- 必要的 camera pose 元数据

#### B. `Spatial Patch Provider`

提供：

- occupancy patch
- voxel patch
- BEV patch
- 局部障碍/通路/遮挡引用

#### C. `Auditory Context Provider`

提供：

- 短时间窗听觉上下文
- 声源引用
- 听觉可达性
- 背景噪声等级

#### D. `Embodied State Provider`

提供：

- 身体位姿
- 移动状态
- grounded
- LOS 失败
- reachability 失败
- 接触状态

## 7. Perception Query Frame

`Perception Query Frame` 是多模态/VLA链的统一取样协议。

它定义的是：

> 当前主体在某一时间窗、某一局部空间内，对世界进行了一次感知查询。

### 7.1 作用

- 统一时间参考
- 统一空间参考
- 统一关注目标
- 统一模态输入窗口

### 7.2 包含内容

至少包含：

- 主体 id
- query 时间窗
- actor frame / camera frame / listener frame
- attention context
- visual inputs
- spatial inputs
- auditory inputs
- embodied inputs
- environment inputs
- structured fact refs

它不是感知结果，而是感知请求对象。

## 8. 事实上抛器族补全

当前项目的事实上抛器族还没做全。

### 8.1 环境视觉事实

不能只停在：

- `light_level_drop`

还应补：

- `light_level_restore`
- `visibility_drop`
- `visibility_restore`
- `smoke_occlusion`
- `noise_field_shift`
- `thermal_field_shift`
- 一般区域环境状态变化

### 8.2 空间/遮挡/可达性事实

应补：

- `line_of_sight_blocked`
- `line_of_sight_restored`
- `path_blocked`
- `path_detour_required`
- `target_reachable`
- `target_unreachable`
- `cover_entered`
- `cover_left`
- `occlusion_band_changed`

### 8.3 对象可供性事实

应补：

- `movable`
- `immovable`
- `grabbable`
- `blocked`
- `recently_manipulated`
- `interaction_affordance_changed`
- `accessibility_changed`

### 8.4 听觉事实

应补：

- 声源方向
- 多声源并发
- 遮挡导致的听觉衰减
- 持续声与瞬时声区分
- 听不清、模糊听见

### 8.5 失败与负事实

应补：

- 目标消失
- 预期看到但没看到
- 预期可达但失败
- 预期可听但只听到模糊信号

## 9. 角色与司命的多模态结构

### 9.1 不是统一一个多模态脑

当前项目不应做成：

- 一个统一多模态脑服务所有组件

而应做成：

- 一个共享基础设施平台
- 多个独立上下文的多模态运行时栈

### 9.2 共享的是平台，不是脑

共享：

- 模型注册与路由
- 输入编码接口
- 输出 schema
- 调度
- tracing / replay / eval

不共享：

- 角色上下文
- 司命上下文
- 私有缓存
- 推理历史

### 9.3 两个运行时专属栈

#### A. `Character-Agent Multimodal Stack`

只服务角色智能体。

关注：

- 局部空间理解
- 角色视角下的路径与遮挡
- 角色局部环境压力
- 角色当前身体限制

#### B. `Siming Multimodal Stack`

只服务司命。

关注：

- 多角色全局分布
- 局势可见性失衡
- 环境变化对公平的影响
- 全局态势理解

## 10. 感知结果三层结构

当前项目建议采用三层结果对象：

### A. `Modality Interpretation Result`

单模态解释结果。

分别针对：

- 视觉/空间
- 听觉
- 身体状态
- 环境状态

### B. `Cross-Modal Understanding Result`

真正的多模态理解层。

它负责：

- 世界假设
- 置信度修正
- 模态冲突与缺失
- 注意力更新

### C. `Canonical Percept Bundle`

最终统一输入对象。

这是角色智能体和司命各自运行时真正消费的感知结果。

## 11. Fusion 结构

### 11.1 不是只有一个最终 Fusion

至少分三步：

1. `Perception Query Framing`
2. `Modality Interpretation`
3. `Cross-Modal Understanding + Decision Fusion`

### 11.2 角色和司命各有自己的 Fusion

角色专属 fusion：

- 消费角色自己的多模态结果
- 融合 `L1` 结构化事实
- 输出角色版 `Canonical Percept Bundle`

司命专属 fusion：

- 消费司命自己的多模态结果
- 融合 authority / world / environment / evidence 事件
- 输出司命版感知包

### 11.3 性能要求

- 小模型或规则+小模型混合
- 严格超时
- 超时不阻塞主循环
- 慢通路结果只影响下一拍，不反压当前帧

## 12. 角色智能体侧升级

### 12.1 输入升级

角色智能体不再只吃：

- 单条 fact
- 单条 candidate
- 文本摘要

而是吃：

- `Canonical Percept Bundle`
- `Actor Scene Knowledge`
- memory bundle

### 12.2 场景知识层

引入：

`Actor Scene Knowledge`

保存：

- 空间知识
- 障碍/遮挡/路径知识
- 环境变化经验
- 来源
- 置信度
- 新鲜度
- 冲突状态

### 12.3 主动感知

角色智能体应支持：

- 换角度观察
- 靠近确认
- 暂停探查
- 失败后重查

不能始终只是被动听汇报。

## 13. 司命侧升级

### 13.1 多模态能力

司命也需要自己的多模态栈。

它不是读取角色局部世界，而是读取：

- 全局空间态势
- 多角色分布
- 环境变化趋势
- 证据链和可见性变化

### 13.2 司命专属感知输出

应支持增强：

- `FairnessStateSnapshot`
- 干预候选
- 最小催化路径选择
- 工作台解释

## 14. 非运行时两类工具链

### 14.1 非运行时工具

服务：

- 审核
- 回放
- 调试工作台
- 结果分析

### 14.2 非运行时生产工具

服务：

- 场景语义抽取
- 建模注入
- 资产处理
- 空间知识生成
- 数据集构建

### 14.3 自动化原则

场景空间语义的形成采用：

- 建模命名语义
- 节点树结构
- 自动空间抽取
- 多模态语义识别
- 人工只审核

不走人工逐项补全。

## 15. 总体模块表

当前项目未来目标模块包括：

- `L1` 世界事实层
- `Scene 3D Space Model`
- `Runtime Spatial Occupancy Field`
- `Visual Patch Provider`
- `Spatial Patch Provider`
- `Auditory Context Provider`
- `Embodied State Provider`
- `Perception Query Frame`
- `Character-Agent Multimodal Stack`
- `Siming Multimodal Stack`
- `Character-Agent Fusion`
- `Siming Fusion`
- `Modality Interpretation Result`
- `Cross-Modal Understanding Result`
- `Canonical Percept Bundle`
- `Actor Scene Knowledge`
- `CharacterAgentRuntime` 升级版
- `SimingRuntime` 升级版
- `Multimodal Capability Platform`
- `Non-Runtime Tool Multimodal Stack`
- `Non-Runtime Production Multimodal Stack`

## 16. 一句话收束

当前项目的正确升级方向不是从“结构化事实链”跳到“纯多模态 agent”，而是：

> 保留 `L1` 世界事实主链，把 `Godot` 升级为视角化取样前端，引入 `Scene 3D Space Model` 与 `Runtime Spatial Occupancy Field` 作为空间底座，再为角色智能体和司命分别建立独立多模态栈、独立融合层和统一感知对象，最终让它们在游戏场景里真正基于局部世界而不是碎片文本运行。
