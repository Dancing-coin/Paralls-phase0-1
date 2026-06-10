# 16-autoplan司命架构优化报告

## 1. 文档目标

本文档记录本轮 `gstack-autoplan` 对司命文档簇的架构审查结论，并把分散在 `02-15` 中的关键口径收束成一组可执行改进。

本轮审查采用：

- CEO 视角：收紧目标和阶段边界
- 设计视角：检查工作台信息层级与解释链
- 工程视角：检查 schema、时钟、幂等、审计、降级与存储
- DX 视角：检查实现者是否能从文档直接写出接口、测试和迁移计划

外部 Codex 只读审查已执行；Claude subagent 工具在当前宿主不可用，本轮按单外部声部降级。

## 2. 总结论

司命文档簇的方向正确，但 `Phase 1` 的最小范围已经出现扩张：

- `02` 把 `Phase 1` 定义为公平裁判链
- `15` 把叙事投影、事件链、戏剧优先级、插件注册和离线简报放入必做范围

本轮改进采用以下决策：

1. `Phase 1` 必须先落成公平裁判链。
2. 叙事投影相关能力保留为 `Phase 2+` 扩展或 `Phase 1` 可选 stub。
3. `world_ts` 不进入事件总线公共信封，只作为司命领域对象内的世界时间字段。
4. 公共信封排序依赖 `producer_ts/event_id`，司命领域排序依赖 `sim_tick_ts/world_ts`。
5. 五个公平维度对应五个 auditor，`conversation_access_auditor` 不再隐含在 participation 中。
6. 所有关键对象必须有 schema 版本、必填字段、枚举、分数范围、相关链和幂等键。
7. `visual_fact_path` 只能放大已成立事实的可观察性，不能制造事实。
8. Phase 0 司命仍只是一个 backend-owned high-level catalyst，不要求 Phase 1 存储、审计和工作台。

## 3. Phase 1 最小主链

`Phase 1` 必做主链固定为：

```text
权威事件 ingest
-> FactCore 边界校验
-> 5 auditor 生成 FairnessStateSnapshot
-> InterventionPolicyEngine 生成 InterventionCandidate
-> ExecutionFeasibilityLayer 生成 InterventionDecision
-> Dispatcher 只发高层催化消息
-> CheckpointAuditService 写审计链
-> NarrativeReadModelService 刷新薄读模型
```

`Phase 1` 不把以下能力作为验收阻塞项：

- 多步 `EventChainCandidate` 搜索
- `DramaticPriorityModel`
- `NarrativeObligationLedger`
- 长 horizon 叙事投影
- 离线世界持续后台运行
- 完整工作台 UI
- Redis/PostgreSQL 以外的部署/分片策略

这些可以作为 `Phase 1` stub 或 `Phase 2+` 扩展点保留，但不得成为最小验证前置条件。

## 4. 统一时钟口径

事件总线公共信封字段：

- `producer_ts`
- `event_id`
- `causation_id`
- `correlation_id`

司命领域对象字段：

- `world_ts`：房间世界时间，可用于复盘和剧情排序
- `sim_tick_ts`：司命 tick 时间，可用于同一房间内的裁判周期排序
- `created_at`：服务端持久化时间

规则：

1. `world_ts` 不得被提升为事件总线公共信封字段。
2. 同一 `sim_tick_ts` 内的事件按 `producer_ts`、`event_id` 稳定排序。
3. late event 到达时必须标记 `late_input=true`，不能悄悄重写已审计决策。
4. replay 使用 `correlation_id -> causation_id -> event_id` 串链，使用 `world_ts/sim_tick_ts` 解释时间关系。

## 5. Canonical Schema 要求

以下对象必须具备字段级 schema：

- `FairnessStateSnapshot`
- `InterventionCandidate`
- `ExecutionContextSnapshot`
- `InterventionDecision`
- `Checkpoint`
- `InterventionAuditRecord`
- `NarrativeReadModel`

每个 schema 至少声明：

| 项 | 要求 |
| --- | --- |
| `schema_version` | 必填，语义版本或整数版本 |
| id 字段 | 必填，带对象前缀，如 `fair_snap_` |
| `room_id` | 必填，所有跨房间对象隔离 |
| `correlation_id` | 必填，串起同一用户/系统链路 |
| `causation_id` | 必填，指向直接原因 |
| 枚举字段 | 必须列出所有合法值 |
| 分数字段 | 默认 `0.0-1.0`，除非文档另行声明 |
| 可选字段 | 必须说明缺省行为 |
| 幂等键 | 对 dispatch、audit、decision 必须显式声明 |

## 6. Dispatch 矩阵

| band | selected_path | owner | bus event | 允许 payload | 必须回流 |
| --- | --- | --- | --- | --- | --- |
| `impulse` | `character_input_path` | Character L2/L3 | `siming.impulse` | 目标、强度、原因、TTL | character ack/result |
| `opportunity` | `character_input_path` | Character L2/L3 | `siming.opportunity` | 行动窗口、资格、约束 | candidate/result feedback |
| `fact_reveal` | `character_input_path` | Character L2/L3 | `siming.fact_reveal` | fact ref、可见性原因 | knowledge/perception feedback |
| `environment_request` | `environment_change_path` | ESM/L1 | `siming.environment_request` | 环境目标、约束、期望效果 | ESM resolution + world fact |
| any | `visual_fact_path` | Visual fact / Godot presentation boundary | `siming.visual_observability_request` | established_fact_id、放大方式、预算 | observed presentation/fact visibility result |
| any | `l3_highlight_path` | L3/Godot presentation | `siming.presentation_highlight_request` | established_fact_id、镜头/高光提示 | presentation result |
| any | `no_action` | Siming | none | reject reason | audit only |

硬规则：

- `visual_fact_path` 必须引用已成立的 `established_fact_id`。
- `environment_request` 的成功事实只能由 `ESM/L1` 回写。
- `character_input_path` 不得直接写角色信念真值。
- `l3_highlight_path` 不得改变业务真值。

## 7. Canonical 降级表

| 失败原因 | 首选处理 | 次级处理 | 审计状态 |
| --- | --- | --- | --- |
| physical impossible | 降到 `visual_fact_path` 或 `character_input_path` | `no_action` | `rejected_physical_impossible` |
| autonomy risk | 降低 strength | `impulse` 或 `no_action` | `downgraded_autonomy_risk` |
| budget pressure | 禁用 `l3_highlight_path` | 薄 `visual_fact_path` 或 `no_action` | `downgraded_budget_pressure` |
| replay risk | 选可解释路径 | `no_action` | `rejected_unreplayable` |
| ESM rejection | 改 `opportunity` / `impulse` | `no_action` | `esm_rejected` |
| stale candidate | 重新 snapshot | 丢弃 candidate | `stale_snapshot` |
| cooldown collision | 延迟或 suppress | `no_action` | `duplicate_suppressed` |

## 8. 审计状态补全

`InterventionAuditRecord.result_status` 扩展为：

- `dispatched`
- `effective`
- `partially_effective`
- `ineffective`
- `harmful`
- `ack_timeout`
- `esm_rejected`
- `expired_ttl`
- `stale_snapshot`
- `duplicate_suppressed`
- `rolled_back`
- `unknown_effect`

after snapshot 规则：

1. 成功 dispatch 后，在结果事件或 TTL 到期后生成 after snapshot。
2. `no_action` 也要写 audit，但 `snapshot_after_ref` 可为空。
3. duplicate suppression 不重新 dispatch，只追加审计或计数。
4. late result 不得覆盖已有最终状态，只能追加修正记录。

## 9. 存储与幂等约束

数据层必须补充：

- `(room_id, correlation_id)` 查询索引
- `(room_id, causation_id)` 查询索引
- dispatch 幂等键：`room_id + decision_id + selected_path`
- audit 幂等键：`room_id + decision_ref + result_event_id`
- candidate 与 decision 的 FK/reference policy
- read model 只读投影不得反向写入世界事实

派发语义采用：

- 对外 dispatch：至少一次投递
- 幂等抑制：由 decision/audit idempotency key 保证
- replay：以审计链为真源，不以 Redis 热缓存为真源

## 10. Phase 0 兼容边界

当前仓库 Phase 0 / Phase 0.5 的司命实现仍允许保持为：

- backend-owned high-level `attention_prompt`
- 无 auditor
- 无 Redis/PostgreSQL 司命表
- 无工作台
- 无持续 tick
- 无叙事投影
- 可使用 stub voice / visual fact / catalyst 路径

Phase 0 禁止被这些 Phase 1 文档倒逼：

- 引入完整 `SimingOrchestrator`
- 引入持久化 schema
- 引入多 auditor 并发
- 引入 `EventChainCandidate`
- 引入完整工作台 UI

Phase 0 的验收仍以仓库 harness 为准；Phase 1 文档只能作为未来实现口径。

## 11. 决策审计轨迹

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | 收紧 Phase 1 到公平裁判链 | Mechanical | P1/P3 | 当前 repo 目标是可验证运行时切片，完整叙事投影会拖大范围 | 把 `EventChainCandidate` 等列为 Phase 1 必做 |
| 2 | Eng | 保留 `world_ts` 但降为领域字段 | Mechanical | P5 | 事件总线信封已经排除 `world_ts`，但复盘需要世界时间 | 删除 `world_ts` |
| 3 | Eng | 五维公平模型对应五个 auditor | Mechanical | P5 | 文档已有五维，隐含合并会让实现者分歧 | 继续写“四个 auditor” |
| 4 | Eng | 增加 dispatch 矩阵 | Mechanical | P1 | 解决 `visual_fact_path` 与高层回写边界不清 | 仅靠文字描述 |
| 5 | Eng | 增加审计边缘状态和幂等键 | Mechanical | P1 | replay/audit 必须覆盖重复、延迟、超时、拒绝 | 只保留成功/无效状态 |
| 6 | DX | 明确 Phase 0 兼容边界 | Mechanical | P3 | 避免 Phase 1 文档误伤当前 Phase 0 验收 | 让实现者自行推断 |

## 12. 第二轮 autoplan 补强

本轮继续使用 `gstack-autoplan` 对 `02-16` 做二次审查。Codex 只读外部声部可用；Claude subagent 工具在当前宿主不可用，仍按降级处理。

二次审查发现第一轮报告的结论正确，但部分结论尚未传播到所有文档：

| 问题 | 修正 |
| --- | --- |
| `07` / `14` 仍残留 4 auditor 口径 | 全部修正为 5 auditor，并明确 `conversation_access` 不得隐含 |
| `15` 的主循环仍把叙事投影写进 Phase 1 | 拆成 `Phase 1 fairness 主链` 与 `Phase 2+ projection 扩展链` |
| `05` 只有 score 字段，没有确定性算法 | 增加 hard veto、权重、阈值、tie-break 与 golden examples |
| `06` 缺少 retry / late result 状态机 | 增加 result lifecycle 与 append-only correction 规则 |
| `13` 只能展示 happy path | 增加链路状态模型，覆盖 pending / failed / stale / late / duplicate / partial |
| schema 仍不足以直接实现 | 新增 `17-司命Canonical Schema与验收对象.md` |
| DX / testability 不足 | 新增 `18-司命Phase1测试与验收计划.md` |

## 13. 第二轮决策审计轨迹

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 7 | Eng | 全文统一 5 auditor | Mechanical | P5 | 五维公平模型必须有清晰实现归属 | 继续允许 4 auditor 或隐含合并 |
| 8 | CEO/Eng | Phase 1 主循环剥离 narrative projection | Mechanical | P3/P5 | Phase 1 验收应证明公平裁判链，不应被 Phase 2 投影拖大 | 让 projection 继续出现在主链 |
| 9 | Eng | 为可执行性层增加确定性选路算法 | Mechanical | P1 | 同一输入必须得到同一 decision | 只保留抽象 score 字段 |
| 10 | Design/DX | 为工作台增加失败态链路模型 | Mechanical | P1 | 工作台必须能解释 timeout、late、duplicate、partial | 只展示成功链 |
| 11 | DX | 新增 schema 与测试计划文档 | Mechanical | P1 | 实现者需要可验证对象和 golden traces | 让实现者从分散文档推断 |

## 14. 一句话收束

本轮 autoplan 的核心改进不是增加司命能力，而是把司命从“宏大但可误读的设计簇”收束成“Phase 1 可实现、可验证、可审计，同时不误伤 Phase 0 的运行时裁判链”。
