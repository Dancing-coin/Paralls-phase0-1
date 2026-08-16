# 第四阶段推进：动态经济与社会制度扩展

状态：`phase-four bounded scope implemented-and-verified; this directory remains non-authorizing guidance`

第四阶段建立在 P3 的持续角色与组织生态之上，把第一阶段的固定 quote、聚合需求和单店
经营扩展为受约束的动态商业生态。它仍然复用既有 Economy、Organization、Government、
Contract、Debt、Inventory 和 EventStore owner，不建立独立 market runtime 或金融总账。

```text
P3 bakery district population
  -> P4A quote/order and deterministic market clearing
  -> P4B multi-organization procurement/sales/labor
  -> P4C permit/tax/inspection/public-order policies
  -> P4D limited credit and commercial ecosystem vertical slice
  -> P5 broader RPG gameplay domains
```

## 1. 当前基线与新增

| 已有/可复用 | 尚未实现 | P4 只新增什么 |
| --- | --- | --- |
| account、fixed offer、sale/purchase posting、debt、contract、tax/permit primitives | 多方供需、quote lifecycle、订单/报价竞争、组织间结算 | 动态报价的 typed contract、清算 proposal、跨组织 settlement adapter |
| inventory reservation、production output、ownership | 供应链交付、订单取消、质量/交期影响 | 引用既有 reservation/custody 的贸易流程 |
| Organization `RoleAssignment`、P2 work/evidence | 多组织预算、劳务合同、组织关系和营业策略 | 组织间关系 projection、预算和可审计经营决策 |
| Government permit/inspection/tax assessment | 监管周期、处罚执行、公共秩序影响 | policy revision、inspection/penalty obligation 与 scoped public policy view |

## 2. 范围

### 包含

- 固定 quote 到 versioned public quote/order 的渐进迁移；
- 供给、需求、库存、生产能力和营业窗口驱动的确定性清算；
- 多 bakery、supplier、customer organization 的采购、销售、交付和取消；
- 工资、合同、债务、税费、许可证和检查在同一 period/obligation spine 上结算；
- 有限信用与逾期，不实现宏观金融系统；
- 公开竞争 profile、声誉和监管结果的可见投影。

### 排除

- 宏观货币、汇率、股票、证券化、系统性金融风险；
- 跨洲贸易、文明级产业链和无限精度价格预测；
- 让市场模型、AI 或政府脚本直接写账户、库存或许可事实；
- 不可回放的浮点/随机清算和隐藏的第二条交易路径。

## 3. 正式化路径

建议拆成 P4A market contract、P4B organization commerce、P4C governance/finance、P4D
commercial-ecosystem vertical slice。每份 spec 需先引用 P3 population continuity evidence，
再定义事件目录、revision pinning、migration 和 Harness profile。

文档导航：

1. [01-第四阶段范围与制度边界.md](01-第四阶段范围与制度边界.md)
2. [02-动态报价、清算与跨组织结算契约.md](02-动态报价、清算与跨组织结算契约.md)
3. [03-政府监管、信用与公共义务契约.md](03-政府监管、信用与公共义务契约.md)
4. [04-商业生态参考包与第四阶段门禁.md](04-商业生态参考包与第四阶段门禁.md)

正式 SDD 入口：
[Phase Four Dynamic Economy And Institutions Specification Tree](../../superpowers/specs/world-character-siming-authority-mainline/phase-four-dynamic-economy-institutions/README.md)
；对应实施计划见同名 plan tree。P4A-P4D 已有 focused Harness 证据；动态经济仍是受限确定性切片，不是宏观市场或金融系统完成。
INF-4O 另外单独证明了一个固定 Organization `supply` 推广行，但它仍然只是既有 owner 的受限 promotion 证据，不把本目录升级成泛化 promotion 面。
