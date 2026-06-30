# 当前项目交互编排层设计

- 日期：`2026-06-29`
- 状态：`implemented-and-verified`
- 上位规格：[2026-06-29-current-project-intelligence-upgrade-master-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-intelligence-upgrade-master-design.md)

## 1. 目标

统一管理：

- 语义驱动交互
- 物理驱动交互

避免把“并行模式”和“协作模式”做成两套独立系统。

## 2. 正确抽象

统一抽象为：

- `Interaction Orchestration Layer`

它只是一个交互编排层，不是新的主脑。

## 3. 主要职责

它负责：

- 判断交互意图
- 判断可用通道
- 指定每条通道的职责
- 决定单通道还是多通道协作
- 决定结果如何合并回世界

## 4. 支持的策略形态

### A. 单通道

只启用：

- 语义通道
或
- 物理通道

### B. 多通道协作

例如：

- 语义负责目标和策略
- 物理负责真实作用
- 结果统一回流

## 5. 核心输入

- 交互意图
- 当前主体状态
- 当前世界状态
- 当前玩法模式
- 当前性能预算

## 6. 核心输出

- 通道选择
- 通道职责映射
- 结果合并策略

## 7. 一句话收束

这份规格的目标，是让当前项目长期保留两类交互系统，但它们不是平行乱长，而是由一套统一编排层调度。
