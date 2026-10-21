# 十月中旬分析批次规则

本目录是 2026-10-12 之后针对“全体角色社会生命、MiroFish 式派生图谱、混合群体模拟与 Laya 心智快循环协同”的独立分析批次。它不是对 `docs/10月分析/` 的物理迁移，也不授权代码实现。

## 文档边界

- `规格/` 只写 architecture spec，状态统一为 `analysis/planned/non-authorizing`。
- `计划/` 只写 implementation plan，必须引用 `规格/`，不能重新定义对象或 owner。
- `审查/` 只写现有代码、测试、原始设计和本批规格之间的映射、缺口与阻断。
- `回写/` 登记本批相对十月分析原文的补充、修正、范围变化和需回写原文的事项。
- 本批不修改 `backend/`，不引入第二套 event store、clock、scheduler、authority、角色心智链或图数据库。

## 设计真相

- 现有十月分析是来源材料；本目录是对其开放世界目标的中旬整合方案。
- `[current]` 只能由代码、测试或现有正式架构文档证明。
- `[planned]` 表示有来源依据但尚未完成实现或验收。
- `[deferred]` 只能表示原始设计允许暂缓的能力；永久禁止项单独列为 `[forbidden]`。
- Laya 是角色智能体中的快思考、低延迟、typed decision 模型；不能写成只服务高影响事件的模型。
- B0/B1/B2/B3 是角色连续性/模拟精度层；Laya/慢思考/Deep 是模型路由层，两组概念不能混用。

## 图表要求

每份实质规格必须包含架构图、主流程时序图、数据流图，并标明 current/planned/deferred。图中必须把 proposal、preview、model output、authority commit 和 Godot presentation 分开。

## 计划要求

计划必须按依赖顺序写任务、责任文件、接口、测试、Harness 证据、回滚点和阻断条件。验证结论不得把静态映射写成运行时完成。


