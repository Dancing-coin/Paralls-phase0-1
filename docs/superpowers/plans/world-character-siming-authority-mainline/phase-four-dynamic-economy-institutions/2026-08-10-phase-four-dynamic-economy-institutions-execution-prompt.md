# Phase Four Dynamic Economy And Institutions Execution Prompt

仅在 P4 套件整体获得实现授权且 P3D fresh-green 后使用。

```text
你负责 Paralls Phase Four Dynamic Economy And Institutions 的完整执行套件。目标是在
P3 continuous district 和 P1 fixed quote/account/contract/debt 基础上，增加受限动态报价、
确定性 clearing、多组织商业协作、政府监管和有限信用。P4 不是 market runtime、金融总账
或宏观经济系统。

开始前读取：
- AGENTS.md、docs/INDEX.md、docs/harness.md、docs/ai-engineering-workflow.md；
- P1D、P2D、P3D specs/plans 和 fresh Harness reports；
- phase-four-dynamic-economy-institutions spec/plan README；
- P4A-P4D specs 与 matching plans；
- docs/8月分析/第四阶段推进全部文件；
- 真实 Economy/Account/Contract/Debt、Inventory/Production/Ownership、Organization、
  Government、GameplayCommandEnvelope、SettlementPlan、GameplayEventStore/replay/checkpoint/outbox。

前置门禁：运行 P3D、P2、P1D predecessor profiles；任一非 fresh-green 则停止。

唯一顺序：
P4A dynamic quote/deterministic clearing
  -> P4B multi-organization commerce
  -> P4C government/credit/public obligations
  -> P4D commercial ecosystem vertical slice

P4A：
- 先测 quote version/expiry/cancel、integer/fixed-point rounding、stock race、stale policy、
  deterministic ordering、partial reject、idempotency、zero-write；
- quote/order/candidate 必须 pin issuer/item/side/quantity/window/policy/reservation/public digest；
- clearing 只能生成 proposal/explanation，authority 重新验证后构造 SettlementPlan 并通过
  GameplayEventStore.append_batch() 提交；
- 禁止隐藏 order-book truth、AI 直写价格、float/random clearing、auction、汇率和宏观 index。

P4B：
- 先测 organization grant/budget、reservation/capacity、delivery/quality/cancel、labor contract、
  stale revision、privacy 和 recovery；
- CommerceCommitment 只引用买卖组织、账户义务、inventory custody、delivery/quality、labor
  contract 和 policy，不复制 warehouse/payroll；
- Organization、Inventory/Production、Economy、Government 保留各自事实 owner；
- 每个 accepted result 必须用 GameplayCommandEnvelope + complete revision vector +
  SettlementPlan + append_batch() 原子提交；
- 禁止 ERP、组织 mega-coordinator、shadow account/inventory、partial commit。

P4C：
- 先测 jurisdiction/policy pin、permit denial、inspection evidence、tax due、bounded credit
  grant/repay/default、overdue、privacy、zero-write；
- Government 只拥有 policy/permit/inspection；Economy/Debt/Contract 拥有 assessed amount/
  claim/repayment/overdue；
- 禁止货币发行、银行、证券、利率市场、汇率、系统性风险、法院、文明公共秩序。

P4D：
- 仅用已有 profiles、organizations、facilities、accounts、contracts/debt、government facts
  组装两家 bakery、supplier、customer、landlord/service party、regulator；
- 覆盖 quote competition、procurement/delivery、labor、permit/inspection/tax、limited credit/
  default、structured reject、scope/replay/no-new-owner；
- 禁止宏观指标、全局经济 scheduler、自治组织 writer、第二 settlement path。

每阶段必须执行 failing tests、focused Harness、全部 predecessor Harness、docs/mainline，
并汇报 policy/quote digest、atomic receipt、revision vector、replay hash、privacy/redaction、
failure zero-write。发现跨域事实没有既有 owner，停止而不是新增万能 coordinator。
只有 P4A-P4D 全绿后才可请求 P5 授权。
```

## Usage Constraint

这份提示词对应整个 P4 plan set，不应把 P4A-P4D 当成可并行独立市场系统。
