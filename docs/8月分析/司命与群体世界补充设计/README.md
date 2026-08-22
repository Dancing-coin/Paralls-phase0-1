# 司命与群体世界补充设计

状态：`proposed future-mainline amendment; analysis/design only; no runtime authorization`

本工作区把“司命知识图谱、角色记忆、群体模拟、近场演出和场景表现”拆成可审核的未来主线修订包。它不创建新 truth owner、store、bus、clock、scheduler、generic writer 或 generic router。

## 阅读与执行顺序

1. [00-影响矩阵与状态登记](00-影响矩阵与状态登记.md)
2. [01-司命受控能力面](01-司命受控能力面.md)
3. [02-知识图谱记忆与故事线桥](02-知识图谱记忆与故事线桥.md)
4. [03-群体模拟与角色分级连续性](03-群体模拟与角色分级连续性.md)
5. [04-世界真相到场景表现投影](04-世界真相到场景表现投影.md)
6. [05-性能回放观测与渐进交付](05-性能回放观测与渐进交付.md)
7. [06-GitHub成熟实现参照与采纳边界](06-GitHub成熟实现参照与采纳边界.md)
8. [07-群体世界本体与状态模型](07-群体世界本体与状态模型.md)
9. [08-时间空间与推进内核](08-时间空间与推进内核.md)
10. [09-行为分层与信息传播](09-行为分层与信息传播.md)
11. [10-校准性能与故障恢复](10-校准性能与故障恢复.md)
12. [11-创作工具与观测闭环](11-创作工具与观测闭环.md)
13. [12-角色模拟记忆种子与连续性设计](12-角色模拟记忆种子与连续性设计.md)

## 约束

- 领域 owner 才能结算生产世界事实；司命、图谱、群体 planner、角色和 Godot 都只能消费投影、提出候选或表现结果。
- 图谱是带来源、隐私、revision 和时间有效期的派生认知层，不是第二份世界真相。
- 同一 `CharacterRecord` 在远场、中场和近场切换，不创建影子 NPC 身份、影子记忆或平行生产状态。
- 所有未来生产写入复用 `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch() -> outbox/replay -> scoped projection`。

## 三维文档链

本目录回答“为什么、继承什么、改变什么”。后续必须在 `docs/superpowers/specs/world-character-siming-authority-mainline/` 写 matching contract，并在 matching plan 中列出 RED tests、Harness、依赖、执行状态和验证证据。任何分析设计不得单独授权实现。

## 使用方式与完成门

本包按五个可独立推进的正式化分包组织：`SGC-1` 司命能力、`SGC-2` 认知图谱、`SGC-3` 群体连续性、`SGC-4` 场景投影、`SGC-5` 性能与证据。详见 [00-影响矩阵与状态登记](00-影响矩阵与状态登记.md) 的替代登记。它们可以共享术语和证据模型，但不能共享一个新的运行时总控层。

每个分包进入实现前必须同时具备：

1. 已批准的具体 owner/capability、source/event/stream/revision/privacy/idempotency/receipt/replay/compensation 合同；
2. 对应的正式 spec 和按依赖拆分的 plan；
3. 先失败后转绿的 focused tests，以及独立 Harness 的 success、zero-write rejection、privacy、revision、idempotency、receipt、full replay、checkpoint-tail replay 证据；
4. 性能 profile 的固定输入、seed、预算与测量字段。

任何一项缺失即保持 `owner-contract blocked`、`owner-admission design` 或 `proposed`，不得以图谱、群体报告、场景表现或模型输出绕过既有生产提交脊柱。
