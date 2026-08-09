# 世界基础设施增量指导

状态：`guidance-only; extends existing world_runtime/ESM/event-replay paths; no new runtime is authorized`

本目录不是新的“世界运行时”模块，也不授权创建第二套 world loop、event store、
clock、scheduler、authority 或持久化真相源。它只记录如何在现有
`backend/app/world_runtime/*`、ESM、`raw_fact_event`、`GameplayEventStore`、
outbox、checkpoint/replay 和既有领域 authority 上做增量扩展。

内容按三类阅读：

- `implemented`：代码和 Harness 已证明的现有路径；
- `reusable`：可以直接复用的协议、投影或边界，但目标业务能力尚未完成；
- `planned`：必须进入正式 spec/plan 并通过验证后才能实现的扩展。

这里的“世界”是共享事实、语义、调度和环境基础设施的职责范围，不是一个拥有
所有领域写入权的总运行时。文明能力、制度采用和六轴传导属于
[社会与制度玩法](../玩法系统/社会与制度玩法/README.md) 的后期玩法层；本目录只
约束它们如何消费既有事件/revision/调度基础。

规范入口为 [../全域架构/00-系统边界与责任矩阵.md](../全域架构/00-系统边界与责任矩阵.md)。

1. [00-标签体系与元规则引擎.md](00-标签体系与元规则引擎.md)
2. [13-实体档案语义因果与元规则.md](13-实体档案语义因果与元规则.md)
3. [12-时间调度跨域结算与回放.md](12-时间调度跨域结算与回放.md)
4. [14-群体模拟世界模式与文明演进.md](14-群体模拟世界模式与文明演进.md)
5. [18-生态环境与灾害系统.md](18-生态环境与灾害系统.md)
