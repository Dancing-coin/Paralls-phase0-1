# P1D Econ-1 Bakery Reference Game Design

Status: `implemented-and-verified; matching plan and phase1d Harness evidence fresh on 2026-08-09`

Date: `2026-08-07`

## Purpose

定义第一阶段第一款完整可玩的参考游戏：`bakery-single-owner`。它把现有技能、资源、
身体、背包、产权、账户、固定报价、债务/合同和事件回放基础，与新增的建造生产、生存、
经营周期、许可证和税费领域组合起来。

本规格不是通用经济系统，也不是 Population Simulation。完整的含义是一个小范围、可
重复、从开店到经营结果的闭环，而不是完整商业文明。

## Dependencies

- P1A Gameplay Foundation Shared Contract Closure；
- P1B Contract Verification And Evidence；
- P1C Frost Farm sample or equivalent approved contract fixture；
- existing resource/body/status/state-group；
- inventory/container/encumbrance/equipment；
- ownership/economy/fixed-offer/debt/contract；
- skill/ability/affordance；
- Patch/package/revision and Godot mirror paths。

## Runtime Configuration

### `bakery-single-owner` required configuration

- one player/owner `CharacterRecord`;
- one bakery `Organization`;
- one facility and one operating jurisdiction;
- three item definitions, one recipe and one fixed supplier quote source;
- aggregate customer demand, not customer NPC state;
- two parameterized public competitor profiles, not competitor NPC state;
- one permit, one tax policy and one inspection outcome;
- zero or more employee records only when the CharacterRecord already exists outside this spec。

真实员工、顾客、供应商、竞争对手和监管人员的角色化生活推进属于后续 Population
Simulation Authority。不得用 seed fixture、`NpcState` 或隐藏脚本提前伪造。

## Complete Player Loop

```text
create/take over bakery
-> acquire facility/initial capital
-> apply for permit
-> purchase material quote
-> reserve and receive material lot
-> run construction/production
-> use skill and consume material
-> place output in inventory
-> publish fixed quote
-> serve aggregate customer demand
-> settle account/custody/ownership and tax
-> settle rent/license/payroll obligations
-> settle optional Survival need
-> close business period
-> continue, recover or fail
```

每个阶段是 owning authority 的明确状态迁移。经营周期不伪装成不可重试的超大事务；
跨周期结果通过 obligation、period record 和 append-only events 保存。

## Shared Domain Owner Matrix

| Domain | Owns | Reads | Must not write |
| --- | --- | --- | --- |
| Skill | qualification、quality、completion evidence | actor state、recipe、work item | account、inventory、facility |
| Inventory | item、lot、custody、reservation、capacity | recipe、purchase/production proposals | account、tax、body |
| Construction/Production | plot、facility、blueprint、recipe、run、condition、yield | skill、inventory reservation、permit、schedule | balance、payroll、body |
| Survival | need、consumption plan、body consequence、labor availability projection | state group、inventory options、price projection | direct payment、inventory transfer |
| Economy | account、journal、quote、hold、sale、tax posting、wage/rent/license obligations | organization plan、purchase/sale evidence、policy | inventory/facility/body |
| Organization | organization、role、plan、budget、period close | actor qualifications、account/inventory/facility projections | duplicate account/inventory/body facts |
| Government | jurisdiction、permit、tax policy、inspection、assessment | organization evidence、public quote | delete assets or edit private character state |
| Projection/Mirror | scoped views and traces | committed events | canonical world truth |

## Required Domain Contract

P1D depends on the separate sub-specifications in `econ1/`:

- construction/production defines facility, recipe, lot consumption and run completion;
- survival defines four modes and one food need;
- economy defines fixed quote, sale, period posting, payroll/rent/tax/license;
- organization/government defines one bakery organization, permit and inspection.

Sub-specifications may add domain schemas and authorities, but all cross-domain writes must map
to P1A `SettlementPlan` rules and the existing `GameplayEventStore.append_batch()` path.

## Failure And Recovery

The game must make these outcomes observable and replayable:

- material shortage;
- skill/qualification failure;
- inventory capacity failure;
- insufficient funds;
- quote expired or quantity exhausted;
- permit missing/expired;
- production facility unavailable;
- wage/rent/tax/license obligation overdue;
- Survival disabled or insufficient food;
- stale revision and duplicate command;
- failed period close with recovery option。

Failure records facts and obligations; it does not delete history. Recovery may reduce production,
reopen a quote, borrow through an existing debt primitive, pay an overdue obligation, pause
operations or start a new period.

## Acceptance

P1D is ready for implementation planning when the game can be specified to:

1. start from a new bakery and complete at least three business periods;
2. perform purchase, lot receipt, production, sale, tax and period close;
3. prove the four Survival modes without hidden ticks;
4. prove zero-employee and existing-CharacterRecord employee paths separately;
5. replay all committed events and rebuild projections/mirror views;
6. keep all NPC ecosystem claims marked `blocked-by-population-simulation`;
7. pass the P1B predecessor profiles and its own focused vertical profile。
