# P2C Payroll and Operating Window

Status: `implemented-and-verified`

## Purpose

工资只能由已完成 work evidence 触发；支付失败产生 due/overdue obligation。P2C 定义显式
operating window 与显式 close/due evaluation，绝不创建通用世界时钟、隐式 tick 或后台
角色唤醒器。P2 operating-window close 与既有 `BusinessPeriod` close 是两个有序事实：
前者负责工作到期评估，后者只有在工资结果已按 policy 结算或被明确标记为 recovery-required
时才可提交。

## Dependencies

P2A typed participation；P2B work lifecycle and evidence refs；P1D Economy/period settlement、
Organization/Government、Survival policy、现有 account/obligation/append batch/replay/mirror。

## Matrix

| 类别 | 内容 |
|---|---|
| 已实现 | Economy account/journal/obligation primitives、business period close、P1D fixed quote/sale/tax/rent/license、explicit command/revision/replay/outbox |
| 可复用 | `EconomicObligation`、period settlement owner、pure `SettlementPlan`、多 stream atomic append、P1D overdue/failure recovery evidence |
| 正式新增候选 | `WageAccrual` evidence reference、wage payment/overdue transition、`OperatingWindow` lifecycle、explicit close/due evaluation、payroll projection |
| 明确后置 | global `SimulationClock`、scheduler、offline catch-up、dynamic wage market、credit/financial system |

## Canonical owner matrix

| Owner | Owns | Reads | Must not write |
|---|---|---|---|
| Organization | operating window request/close and work-period summary | work evidence, obligations, domain receipts | account balances, wage posting, need values |
| Economy | wage accrual, payment, due/overdue obligation and account journal | completed evidence, pinned wage policy, organization budget | attendance, production completion, body/skill |
| Production/Organization | completion evidence | work order, window, slot/reservation | wage truth |
| Survival/Body | labor availability and needs | explicit policy/projection | payroll/window/attendance |
| Government | permit/tax/inspection | period evidence | payroll or character private state |
| Projection/Mirror | scoped payroll/window read views | committed events | canonical state |

## Candidate data/reference contract

```text
OperatingWindow:
  window_ref, organization_ref, opens_at_tick, closes_at_tick,
  policy_revision, source_revision, status=planned|open|closed|cancelled
WageAccrual:
  accrual_ref, organization_ref, payee_actor_ref, work_evidence_refs,
  wage_policy_revision, amount, status=accrued|paid|due|overdue
EconomicObligation extension:
  obligation_kind=wage, accrual_ref, payee_actor_ref, due_tick,
  status=due|paid|overdue|waived
```

这些是正式设计候选。金额、skill、need、产出质量不得在 WageAccrual 中复制；只能引用
owner-verified completed evidence（含 issuer、kind、source digest 和 verification state）以及
pinned policy revision。actor-declared completion 不能直接触发 accrual。`tick` 是 command 携带的
审计坐标，不是新时钟。

## Command/event/revision/idempotency

`open_window`、`close_window`、`evaluate_due`、`accrue_wage`、`pay_wage`、`mark_overdue` 均
必须使用既有 `GameplayCommandEnvelope` 版本化入口；window、organization、work evidence、
account/obligation streams 的 expected revisions 必须完整，policy/wage/permit/source revisions
必须 pinned。close 只能被显式 principal（玩家、Harness 或未来获批入口）调用一次；重复 close
按 idempotency 返回原 receipt。支付失败不得提交 paid event，只能提交规则允许的 due/overdue
事实。跨域 commit 由 shared settlement boundary 组合纯 `SettlementPlan` 后进入一个 atomic batch，
不允许先后独立 append 再声称原子。

固定顺序为：`close_window -> evaluate_due -> accrue_wage -> pay_wage|mark_overdue`。其中
`close_window` 不自动调用既有 `BusinessPeriod.close_period()`；若 `mark_overdue` 已提交，
business period summary 必须保持 `recovery-required/open`，直到新的 payment/recovery command
提交成功。这样不改变当前 period-close 对 overdue 的 fail-closed 语义。

候选事件可包括 `operating_window_opened/closed`、`due_evaluation_recorded`、`wage_accrued`、
`wage_paid`、`wage_overdue`；实际名称/version 必须注册后方可实现。所有事件携带 transaction、
command、causation/correlation、evidence、visibility 和 pinned revisions。

## Window rules and permissions

`planned` 只可 open/cancel；`open` 可 accept/start/finish/absence/break request；`closed` 只可
进行支付、补偿和恢复；`cancelled` 只可审计/重排。窗口外、跨组织、stale revision、重复 close
均零写入拒绝。actor 只见自己的 wage status；manager 见总计/预算占用和窗口结果，但不见他人
私有 need/memory 或不必要薪酬明细；Godot 只见 committed filtered mirror。

## Failure, recovery and replay

未完成 evidence、窗口关闭、政策 revision mismatch、资金不足、过期 obligation、重复命令和
projection scope denial 都返回可解释 failure，附 owner/revisions/retryability 和
`zero_write_guarantee=true`。资金不足保持 obligation due/overdue，不伪造转账；恢复通过新
payment/compensation command。full replay 和 checkpoint-tail replay 对 organization、economy、
obligation、window、payroll projection hash 必须一致。

## Acceptance and Harness evidence

- 未完成或计划中的工作无法产生工资应计；完成 evidence 可重放并只触发一次 accrual；
- 未经 owner 验证的 actor-declared evidence 无法产生工资应计；
- payment success 与 insufficient-funds overdue 均有 event/receipt，余额不被重复写入；
- open/close/due evaluation 由显式 command 产生，重复 close/窗口外写入零写入；
- actor/manager/Godot projection 按 scope 过滤，full/checkpoint-tail digest 相同；
- `phase2c-payroll-operating-window` Harness fresh-green；证据见
  `.harness/verification/phase2c-payroll-and-operating-window-report.{json,md}`，包含
  explicit open/close/due、verified-evidence accrual、原子 paid transfer、资金不足零写入及 overdue。

## Population Simulation handoff gate

人口模拟若要批量 close/pay，只能调用同一显式 command contract；在 materialization、预算、
continuity、batch revision、暂停/恢复和失败补偿证据完成前，不得增加时钟、scheduler 或离线
角色结算。
