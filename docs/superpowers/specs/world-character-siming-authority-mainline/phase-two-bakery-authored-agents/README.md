# Phase Two: `bakery-authored-agents` Specification Tree

Status: `implemented-and-verified; Phase Two plan closed`

Date: `2026-08-09`

## Purpose

本目录把 `docs/8月分析/第二阶段推进/` 正式化为 Phase Two SDD。第二阶段只验证 2-4 个
已经存在的 `CharacterProfile`/`CharacterAgent`，通过既有 Gameplay authority 协作经营
一个组织；参考配置名称为 `bakery-authored-agents`。八月分析仍是增量设计指导，不能直接
被当作 API、schema 或实现授权。

## Non-goals and hard boundary

本阶段不创建 Population Simulation、NPC materialization、动态市场、全局
`SimulationClock`、第二 event store、第二 settlement path、第二 bus、后台 scheduler、
`EmployeeState`/`NpcState` 或 CharacterAgent 直写 store 的路径。顾客仍为
`CustomerDemandAggregate`，供应商仍为固定公开 quote，竞争者仍为公开 profile。

## Baseline evidence

- P1B/P1C、四个 Econ-1 子 profile 与 P1D fresh-green evidence 位于 `.harness/verification/`；
  P1D 报告日期为 2026-08-09。
- 前置设计真相是 [P1B contract verification](../phase-one-gameplay/2026-08-07-p1b-contract-verification-and-evidence-design.md)、
  [P1C frost-farm contract sample](../phase-one-gameplay/2026-08-07-p1c-frost-farm-contract-sample-design.md)、
  [P1D bakery reference game](../phase-one-gameplay/2026-08-07-p1d-econ1-bakery-reference-game-design.md)，
  以及四个 Econ-1 child specs：
  [construction/production](../phase-one-gameplay/2026-08-07-econ1-construction-production-design.md)、
  [survival](../phase-one-gameplay/2026-08-07-econ1-survival-profile-design.md)、
  [economy/period settlement](../phase-one-gameplay/2026-08-07-econ1-economy-period-settlement-design.md)、
  [organization/government](../phase-one-gameplay/2026-08-07-econ1-organization-government-design.md)。
  Matching implementation plans 与报告必须一一对应；旧报告不能替代 fresh run。
- 当前可复用的真实 owner 与入口如下（这是审计结果，不是 P2 新 API 授权）：

  | 事实/边界 | 当前 owner / 入口 | P2 使用方式 |
  | --- | --- | --- |
  | committed event、multi-stream revision、idempotency、replay、checkpoint、outbox | `backend/app/gameplay/event_store.py:GameplayEventStore.append_batch()` 及 `backend/app/gameplay/replay.py`、`dispatcher.py` | 继续作为唯一 writer 与 replay source |
  | command 与纯 settlement mapping | `backend/app/gameplay/shared_contracts.py:GameplayCommandEnvelope`、`SettlementPlan`；`backend/app/gameplay/settlement_plan.py` 的纯 batch adapter | P2 adapter 只生成 envelope；authority 产生 plan/batch 后提交 |
  | domain authority | `organization_government_runtime.py`、`construction_production_runtime.py`、`inventory_runtime.py`、`econ1_economy_runtime.py`/`economy_runtime.py`、`survival_runtime.py`、`government` owner | 只扩展对应 owner 的事实或稳定引用 |
  | authored actor 与意图 | `character_agent/profile/registry.py`、L1-L4 services、`character_agent/execution/l4_adapter.py` | 仅做 registry lookup、scope-filtered input 与 typed intent 输出 |
  | Godot committed mirror | `gameplay/godot_mirror_delivery.py:GameplayMirrorSubscriptionRegistry` 与现有 projector | 只消费 committed、按 grant 过滤的 snapshot/delta |

- `.harness/verification/phase1b-contract-verification-report.*`、`phase1c-frost-farm-report.*`、
  `phase1d-econ1-bakery-report.*` 与 Econ-1 child reports 是当前证据；本次 docs Harness 与
  P1D focused Harness 必须重新运行并在最终报告中记录结果。
- 八月分析中的 `ShiftOffer`、`WorkOrder`、`WageAccrual`、`operating_window` 等均为本阶段
  的正式设计候选名；本次实现仅落在 matching plan 列出的既有 owner 文件，未创建平行 owner。

### Naming and candidate contract rule

`SettlementPlan` 在现有代码中同时有 shared value model 与纯 batch adapter 两个实现位置；
正式实现前必须由 P1 shared-contract owner 选择扩展点并保持单一 boundary。P2 文档中的
`ProfileBackedActorRef`、`ShiftOffer`、`WorkOrder`、`AttendanceEvidence`、`WageAccrual`、
`OperatingWindow` 和事件名都只是候选逻辑记录/事件，不能直接导入、序列化或作为现有 API
断言。任何需要新 owner、store、bus、scheduler 或隐式 NPC state 的实现请求必须回到 spec
评审，而不是在计划执行中自行补充。

## Dependency order

```text
P1D fresh-green
  -> P2A Actor-to-Gameplay Participation
  -> P2B Organization Work Lifecycle
  -> P2C Payroll and Operating Window
  -> P2D Authored-Agents Bakery Vertical Slice
```

P2A-P2C 可在设计阶段并行审阅，但实现必须严格按上述顺序；P2D 只有前三项 focused tests、
replay、permission 和 zero-write evidence fresh-green 后才能开始。

## Documents

1. [P2A Actor-to-Gameplay Participation](2026-08-09-p2a-actor-to-gameplay-participation-design.md) / [plan](../../../plans/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/2026-08-09-p2a-actor-to-gameplay-participation-implementation-plan.md)
2. [P2B Organization Work Lifecycle](2026-08-09-p2b-organization-work-lifecycle-design.md) / [plan](../../../plans/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/2026-08-09-p2b-organization-work-lifecycle-implementation-plan.md)
3. [P2C Payroll and Operating Window](2026-08-09-p2c-payroll-and-operating-window-design.md) / [plan](../../../plans/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/2026-08-09-p2c-payroll-and-operating-window-implementation-plan.md)
4. [P2D Authored-Agents Bakery Vertical Slice](2026-08-09-p2d-authored-agents-bakery-vertical-slice-design.md) / [plan](../../../plans/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/2026-08-09-p2d-authored-agents-bakery-vertical-slice-implementation-plan.md)

## Completion language

P2A-P2D focused tests、四个 phase2 Harness、P1D predecessor Harness、docs Harness 与全量
pytest 均已 fresh-green；可以使用“已有角色的多智能体组织协作已通过 authority、replay、
scope-filtered mirror 和 Harness 门禁”的完成表述。Population Simulation handoff gate 仍未满足。
