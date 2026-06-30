# 当前项目角色智能体多模态链与 `Actor Scene Knowledge` 增量设计

- 日期：`2026-06-29`
- 状态：`awaiting-user-review`
- 上位规格：[2026-06-29-current-project-intelligence-upgrade-master-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-intelligence-upgrade-master-design.md)

## 1. 目标

在 `character mind core` 已经完成的前提下，让角色智能体不再主要依赖碎片 fact 和文本摘要，而是基于：

- 自己的多模态感知链
- 自己的场景知识层
- 自己的融合结果

去继续增强自己的局部世界理解和行动质量。

## 2. 角色专属多模态栈

角色多模态栈只服务当前角色主体。

它关注：

- 当前视野内局部空间
- 局部遮挡和路径
- 局部环境压力
- 当前身体限制
- 当前关注目标的局部可见性和可达性

它不读取：

- 司命上下文
- 全局局势上下文
- 其他角色私有 patch 缓存

## 3. 角色专属 Fusion

角色 fusion 负责融合：

- `L1` 高置信度结构化事实
- 角色专属多模态结果
- 当前身体反馈
- 最近失败与环境结果

输出：

- 角色版 `Canonical Percept Bundle`

## 4. `Actor Scene Knowledge`

这是角色自己的场景知识层。

它保存：

- 空间知识
- 障碍/遮挡/路径知识
- 环境变化经验
- 来源
- 置信度
- 新鲜度
- 冲突状态

它不是世界真相副本，而是角色对世界的主观知识层。

## 5. 更新原则

`Actor Scene Knowledge` 的更新不应简单覆盖，而应支持：

- 命中已有知识
- 修正已有知识
- 新增知识
- 记录冲突

这样才能支撑：

- 误判
- 修正
- 失败回流
- 主动感知

## 6. 主动感知

角色智能体需要支持：

- 换角度观察
- 靠近确认
- 暂停探查
- 失败后重查

这意味着感知不只是被动接收 fact，而应能回推新的 `Perception Query Frame` 请求。

## 7. 与现有设计关系

这份规格继承并扩展：

- `CharacterPrivateWorldSnapshot`
- `working_memory_state`
- `knowledge/social memory`

它不推翻这些对象，而是把它们逐步收束到更正式的场景知识层中。

## 8. 一句话收束

这份规格的目标，是让角色智能体真正拥有自己的局部世界和场景知识，而不是继续主要靠碎片事实和文本摘要行动。
