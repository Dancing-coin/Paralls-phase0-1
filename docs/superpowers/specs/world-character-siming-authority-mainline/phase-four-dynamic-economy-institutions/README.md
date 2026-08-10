# Phase Four Dynamic Economy And Institutions Specification Tree

Status: `implemented-and-verified; P4A-P4D focused Harness evidence fresh on 2026-08-11`

Date: `2026-08-10`

## Purpose

P4 formalizes `docs/8月分析/第四阶段推进/`. It grows P3's continuous
district into constrained dynamic commerce: versioned public quotes/orders,
deterministic clearing, multi-organization delivery/labor and governed limited
credit. It is not a market runtime, financial ledger or macroeconomic model.

## Existing Owners

| Fact | Existing owner | P4 extension boundary |
| --- | --- | --- |
| accounts, fixed offers, debt, contracts | Economy / Account / Contract / Debt | reusable settlement primitives |
| custody, reservation, output | Inventory / Production / Ownership | delivery and capacity references |
| membership, budget, work | Organization | business decision and relationship projection |
| permit, inspection, tax, policy | Government | policy revision and due evaluation |
| command and atomic commit | `GameplayCommandEnvelope`, Gameplay authority, `SettlementPlan` | one `append_batch()` path |

Price models, organization planners, government scripts and agents can produce
typed proposals but never direct account, inventory, permit or debt writes.

## Dependency Order

```text
P3D fresh-green -> P4A quotes/clearing -> P4B organization commerce
                 -> P4C government/credit -> P4D commercial ecosystem
```

P4 consumes [P3D population continuity](../phase-three-population-continuity/2026-08-10-p3d-bakery-district-population-vertical-slice-design.md)
and the P1/P2 owner contracts; it does not replace their event, identity or
settlement paths.

## Documents

1. [P4A dynamic quote and deterministic clearing](2026-08-10-p4a-dynamic-quote-and-deterministic-clearing-design.md)
2. [P4B multi-organization commerce](2026-08-10-p4b-multi-organization-commerce-design.md)
3. [P4C government, credit and public obligations](2026-08-10-p4c-government-credit-and-public-obligations-design.md)
4. [P4D commercial ecosystem vertical slice](2026-08-10-p4d-commercial-ecosystem-vertical-slice-design.md)

Matching plans: [P4A](../../../plans/world-character-siming-authority-mainline/phase-four-dynamic-economy-institutions/2026-08-10-p4a-dynamic-quote-and-deterministic-clearing-implementation-plan.md),
[P4B](../../../plans/world-character-siming-authority-mainline/phase-four-dynamic-economy-institutions/2026-08-10-p4b-multi-organization-commerce-implementation-plan.md),
[P4C](../../../plans/world-character-siming-authority-mainline/phase-four-dynamic-economy-institutions/2026-08-10-p4c-government-credit-and-public-obligations-implementation-plan.md),
[P4D](../../../plans/world-character-siming-authority-mainline/phase-four-dynamic-economy-institutions/2026-08-10-p4d-commercial-ecosystem-vertical-slice-implementation-plan.md).
