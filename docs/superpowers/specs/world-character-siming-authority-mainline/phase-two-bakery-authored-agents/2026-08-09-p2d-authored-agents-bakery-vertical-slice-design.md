# P2D Authored-Agents Bakery Vertical Slice

Status: `implemented-and-verified`

## Purpose

定义 `bakery-authored-agents` 三角色参考包，证明至少两个已存在 authored actors 在同一条
Gameplay authority/replay/mirror 事实链中协作经营。P2D 是垂直验证包，不是新的 runtime 或
Population Simulation 入口。

## Dependencies

硬前置：P1D `phase1d-econ1-bakery` fresh-green（及 P1B/P1C、四个 Econ-1 child profiles）；
P2A actor participation、P2B organization lifecycle、P2C payroll/window 的 focused tests、
replay、permission 和 zero-write evidence 全部 fresh-green。

## Matrix

| 类别 | 内容 |
|---|---|
| 已实现 | P1D `bakery-single-owner`、aggregate demand、fixed supplier quote、public competitor profile、committed Godot mirror、full/checkpoint-tail replay |
| 可复用 | P1D package/owner matrix、facility/recipe/reservation/sale/period close、existing profile registry and mirror grants、Harness runner/evidence storage |
| 正式新增候选 | 三角色 authored package、multi-actor composition、actor/manager scoped mirror、P2 success/failure/replay matrix、`phase2-bakery-authored-agents` profile |
| 明确后置 | customer/supplier/competitor NPC state、dynamic market、Population authority、global clock、automatic agent wakeup |

## Reference package

内容包必须声明三个已授权的 `character:<profile_id>` actor refs、一个 bakery Organization、
owner/jurisdiction/permit、`operator`、`baker/production`、`counter/procurement` role、一个
共享 facility slot、stock container、既有 bakery accounts、一个 fixed supplier quote、
`CustomerDemandAggregate`、public competitor profiles、wage/survival/permit policies 和
committed-only mirror scopes。`char_a`/`char_b`/`char_c` 仅能作为 harness actor refs，不能覆盖
其 authored identity、occupation、memory 或状态；正式内容包必须提供自己的授权 profile。

## Canonical owner matrix

| Owner | Owns | Reads | Must not write |
|---|---|---|---|
| Character registry/agent | three authored identities and local mind | actor scope | organization/economy truth |
| Organization | role/shift/work/attendance/window | profile and domain evidence | customer/supplier/competitor private state |
| Production/Inventory | slot, reservation, run, output | work evidence, recipe, skill | wage/account |
| Economy/Government | quote/sale/account/tax/wage obligation/permit | committed work and period evidence | profile or work lifecycle |
| Mirror/Harness | evidence and filtered views | committed events | canonical runtime facts |

## Observable scenario and contracts

```text
open W1
-> operator publishes two offers
-> baker accepts production work; counter accepts procurement/counter work
-> counter completes a procurement WorkOrder; the existing fixed-quote authority performs the
   organization-authorized purchase, causally linked to that WorkOrder (no new procurement intent)
-> baker start_work passes skill/survival/slot/reservation checks
-> finish_work commits run/output plus worker contribution evidence
-> aggregate demand consumes bread; sale/account posting follows inventory result
-> close W1; wage is paid on the success path
-> actor/manager scoped projections and Godot mirror show committed results
```

第二窗口必须覆盖一次可恢复失败（absence、slot/reservation conflict 或 insufficient funds）。
若 insufficient funds 产生 overdue，operating window 可以 closed，但既有 business period
summary 必须保持 recovery-required，直到新 payment/recovery command 成功；不要把 overdue
伪装成既有 `BusinessPeriod.closed=true`。恢复用新 command/window，不编辑旧事件。所有
command 复用 `GameplayCommandEnvelope`，所有
cross-domain result 先形成纯 `SettlementPlan` 再由 `GameplayEventStore.append_batch()` 以
完整多 stream expected revisions 原子提交；同一 idempotency retry 返回原 receipt。

## Permissions, replay and failure matrix

必须证明 profile lookup、assignment authorization、offer stale、insufficient skill/labor、
facility/reservation conflict、window closed、invalid evidence、insufficient funds、duplicate、
stale revision 和 projection scope denial。每个 rejection 都必须带 owner scope、source refs、
pinned revisions、retryability 和 `zero_write_guarantee=true`。manager mirror 不得泄露角色私有
need/memory/wage detail；actor mirror 仅自己的 scope；Godot 只消费 committed snapshot/delta。

full replay 与 checkpoint-tail replay 对 organization、production、inventory、economy、survival
和所有 scoped projection digest 必须一致，outbox 只有 commit 后可 delivery。

## Acceptance and Harness evidence

P2D 通过门禁必须有：

1. P1D fresh-green report 与前置 profile report refs；
2. 三个 package actor refs 均能回查 registry 且保持 authored identity；至少两个 actor 各有
   assignment、accepted shift、独立 work evidence，operator 的 manager principal 也必须可审计；
3. 成功和失败两个窗口的 event/owner diff、atomic commit/zero-write trace；
4. wage accrual 只引用 completed evidence，payment/overdue 可 replay；
5. full/checkpoint-tail hashes、idempotency、causation/correlation/revision evidence；
6. actor/manager/Godot mirror scope redaction evidence；
7. no-new-owner audit：无 Population authority、NpcState、dynamic order book、第二 store/bus/
   scheduler、CharacterAgent append path。

`phase2-bakery-authored-agents` Harness fresh-green；证据见
`.harness/verification/phase2-bakery-authored-agents-report.{json,md}`，包含 65 个 committed
events、三期 bakery、双角色工作 evidence、full/checkpoint-tail replay、outbox 与 Godot
mirror checksum。

## Population Simulation handoff gate

进入 `bakery-population-ecosystem` 前，Population authority 必须证明既有 profile/record
materialization、家庭/职业/预算/知识/连续性 owner、批量同 envelope/append batch、catch-up/
pause/resume/compensation 和 customer/supplier/competitor private account inventory grant。
在门槛关闭前，P2D 是本阶段终点，不能作为人口模拟暗门。
