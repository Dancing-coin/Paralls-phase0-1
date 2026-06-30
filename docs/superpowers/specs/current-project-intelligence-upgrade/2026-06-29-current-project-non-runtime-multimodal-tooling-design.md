# 当前项目非运行时多模态工具链与生产工具链设计

- 日期：`2026-06-29`
- 状态：`awaiting-user-review`
- 上位规格：[2026-06-29-current-project-intelligence-upgrade-master-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-intelligence-upgrade-master-design.md)

## 1. 目标

明确当前项目中的非运行时多模态能力，不再把多模态只看成角色智能体私有能力。

## 2. 两类工具链

### A. `Non-Runtime Tool Stack`

服务：

- 审核
- 回放
- 调试工作台
- 结果分析

### B. `Non-Runtime Production Stack`

服务：

- 场景语义抽取
- 建模注入
- 资产处理
- 场景知识生成
- 数据集构建

## 3. 推荐模块

### `Scene Semantic Extractor`

从：

- 节点命名
- 子节点结构
- 资源路径

提取语义初稿。

### `Spatial Structure Baker`

从：

- 碰撞
- 导航
- 区域体积

烘焙静态空间结构结果。

### `Multimodal Semantic Classifier`

对规则和几何不够确定的对象做语义判别。

### `Scene Knowledge Generator`

自动生成：

- `Scene 3D Space Model` 初稿
- 其他空间知识底稿

### `Review Workbench`

人类只做审核，不做逐项补全。

### `Dataset and Replay Builder`

从运行时和场景输出中构建训练、评估和回放数据。

## 4. 自动化原则

优先顺序：

1. 建模命名语义
2. 场景结构自动提取
3. 多模态自动识别
4. 人工审核

人工不作为主要补全手段。

## 5. 与运行时关系

这些工具链可以共享底层多模态能力平台，但不与运行时角色智能体、司命共享运行时上下文。

## 6. 一句话收束

这份规格的目标，是让当前项目的多模态能力同时服务运行时和生产工具，而不是只服务角色智能体。 
