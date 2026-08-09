# Econ-1 Domain Specification Tree

Status: `approved; matching plans authorized by user on 2026-08-07; domain specs depend on P1D`

本目录把面包店参考游戏所需的领域基础设施拆开，避免把 Construction、Survival、
Economy、Organization 和 Government 误写成一个超级 authority。每个子域拥有自己的
canonical stream，并通过 P1A contract 和 P1D 经营周期组合。

对应实施计划位于
`docs/superpowers/plans/world-character-siming-authority-mainline/phase-one-gameplay/econ1/`。

## Domain Specs

1. [Construction and Production](2026-08-07-econ1-construction-production-design.md)
2. [Survival Profile](2026-08-07-econ1-survival-profile-design.md)
3. [Economy and Business Period Settlement](2026-08-07-econ1-economy-period-settlement-design.md)
4. [Organization and Government](2026-08-07-econ1-organization-government-design.md)

## Shared Rules

- No sub-domain creates a second event store, bus, scheduler or cross-domain god object.
- Inventory, account, ownership, body, skill and permit facts remain with their owners.
- Cross-domain reservation/obligation references are not duplicated balances or quantities.
- Every command includes principal, idempotency key, expected revisions and causation/correlation.
- Every rejection is typed, replayable and zero-write for the rejected batch.
- The first configuration is `bakery-single-owner`; real NPC lifecycle is blocked by Population
  Simulation Authority.
