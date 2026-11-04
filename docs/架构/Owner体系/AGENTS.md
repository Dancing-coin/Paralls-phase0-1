# Owner 体系文档规则

本目录收敛 Owner 分类、事实归属、角色对接和跨领域协作规则。文档属于架构设计与实现对照，不直接授权新增代码。

## 文档边界

- `[current]` 只能由当前代码、测试、Harness 或正式运行时文档证明。
- `[planned]` 表示本目录确定的目标或已有规格中的待建能力，不得写成已完成。
- `[deferred]` 表示明确延后或禁止采用的方向。
- Owner 是事实权威边界；projection、workflow、WRK、角色智能体和 UE 表现都不能越权写入别的领域事实。
- 每个实质主题必须包含架构图、关键时序图和数据流图，并标出 `current`、`planned`、`deferred`。

## 命名规则

- `Owner` 只用于对一组 canonical facts 负责、能验证并提交事件的领域权威。
- `Foundation Owner` 表示被多个领域复用的基础事实 Owner；`Atomic Owner` 表示最小独立不变量和提交边界；`Composite Owner` 表示组织跨 Owner 过程但不吞并下层事实。
- `EventStore`、`Projection`、`Workflow`、`WRK`、`CharacterAgent`、`UE Adapter` 不因参与结算而自动成为 Owner。
- `Need` 相关术语必须区分 `SurvivalMetric`（客观生理指标）、`PhysiologicalCondition`（阈值条件/效果）和 `MotivationalPressure`（角色主观动机压力）。

## 证据要求

代码映射优先引用 `backend/app/gameplay/*`、`backend/app/character_agent/*` 和现有运行时模块文档。设计中的跨 Owner 协作必须说明输入、输出、revision、receipt、失败和恢复边界。
