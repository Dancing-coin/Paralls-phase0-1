# 00-ESM总索引

- 状态：第一轮结构化入口
- 作用：作为《开本》`ESM` 体系的统一入口，承接主干设计、后续专项协议与工程约束
- 上游约束：
  - [ESM设计文档.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/ESM设计文档.md)
  - [技术架构总纲.md](/d:/Projects/Paralls/docs/phase1/core/00-总纲/技术架构总纲.md)
  - [Godot源码底层基础设施与运行时约束.md](/d:/Projects/Paralls/docs/phase1/core/00-总纲/Godot源码底层基础设施与运行时约束.md)
  - [事件总线与感知链路设计.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/事件总线与感知链路设计.md)
  - [司命设计文档.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/司命设计文档.md)
  - [角色智能体设计文档.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/角色智能体设计文档.md)

## 当前定位

当前 `ESM` 还处于“主干已收束、专题尚未完全拆开”的阶段。

因此本索引当前先承接两件事：

1. 作为后续 `ESM` 专题文档的正式入口预留
2. 明确现阶段真正的主真源仍是 [ESM设计文档.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/ESM设计文档.md)

## 当前建议阅读顺序

1. [ESM设计文档.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/ESM设计文档.md)
2. [Godot源码底层基础设施与运行时约束.md](/d:/Projects/Paralls/docs/phase1/core/00-总纲/Godot源码底层基础设施与运行时约束.md)
3. [事件总线与感知链路设计.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/事件总线与感知链路设计.md)
4. [司命设计文档.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/司命设计文档.md)
5. [角色智能体设计文档.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/角色智能体设计文档.md)

## 后续建议拆分方向

当 `ESM` 继续深化时，建议优先按以下方向拆分，而不是继续膨胀单一总稿：

1. `01-ESM总纲`
2. [02-动作结算与约束接口.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/ESM/02-动作结算与约束接口.md)
3. [03-状态机与材料模板.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/ESM/03-状态机与材料模板.md)
4. [04-区域环境场与传播规则.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/ESM/04-区域环境场与传播规则.md)
5. [05-ESM与事件总线契约.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/ESM/05-ESM与事件总线契约.md)
6. [06-ESM与角色智能体协作协议.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/ESM/06-ESM与角色智能体协作协议.md)
7. [07-ESM与司命协作协议.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/ESM/07-ESM与司命协作协议.md)
8. [08-ESM调试回放与工作台.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/ESM/08-ESM调试回放与工作台.md)

## 一句话收束

当前 `ESM` 已经不适合继续只靠单一总稿演进；从这一刻起，它应和角色智能体、司命、事件总线一样，进入“主干设计 + 协作协议 + 工程约束”的文档簇方向。
