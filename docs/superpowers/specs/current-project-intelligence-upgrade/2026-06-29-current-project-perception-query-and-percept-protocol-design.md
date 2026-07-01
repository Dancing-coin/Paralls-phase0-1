# 当前项目 `Perception Query Frame` 与感知结果协议设计

- 日期：`2026-06-29`
- 状态：`implemented-and-verified`
- 上位规格：[2026-06-29-current-project-intelligence-upgrade-master-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-intelligence-upgrade-master-design.md)

## 1. 目标

建立当前项目多模态链的统一取样协议和统一感知结果协议。

要解决的问题是：

- 不同模态时间不一致
- 不同模态空间参考不一致
- Godot 局部截图、空间 patch、听觉窗口、身体状态没有统一封装
- 角色和司命后续消费对象不统一

## 2. `Perception Query Frame`

定义：

> 当前主体在某一时间窗、某一局部空间中，对世界进行的一次感知查询。

它必须包含：

- 主体 id
- 时间窗
- actor/camera/listener 参考系
- attention context
- visual inputs
- spatial inputs
- auditory inputs
- embodied inputs
- environment inputs
- structured fact refs

它不是感知结果，而是感知请求对象。

## 3. 单模态解释结果

统一对象名：

- `Modality Interpretation Result`

必须支持四类：

- `visual_spatial`
- `auditory`
- `embodied`
- `environmental`

这一层的职责是：

- 各模态先把自己的输入解释成结构化发现
- 不做最终高层综合

## 4. 跨模态理解结果

统一对象名：

- `Cross-Modal Understanding Result`

职责：

- 形成世界假设
- 做置信度修正
- 登记冲突与缺失
- 更新注意力

这层才是真正的多模态理解层。

## 5. 最终统一输入对象

统一对象名：

- `Canonical Percept Bundle`

它是：

- 角色智能体真正消费的统一感知对象
- 司命真正消费的统一感知对象

它不直接保留全部原始输入，而保留：

- 局部空间状态
- 目标状态
- 环境状态
- 身体状态
- 注意力状态
- 世界假设
- 结构化事实引用
- 不确定性

## 6. 时间与空间要求

不要求模态在原始层完全同一点对齐，但要求：

- 同一时间窗
- 同一空间参考系
- 同一主体视角下可解释

也就是说，目标是工程可对齐，而不是理论上的完美同时同点。

## 7. 与其他规格关系

- 依赖 `Godot` 取样前端提供输入
- 依赖 `L1` 世界事实层提供结构化真相引用
- 服务角色专属多模态链
- 服务司命专属多模态链

## 8. 一句话收束

这份规格的目标，是让当前项目所有多模态输入和多模态理解结果都有一套统一协议，不再靠零散对象和隐式字段流转。
