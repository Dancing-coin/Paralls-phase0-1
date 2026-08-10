# Phase Three Population Continuity Specification Tree

Status: `design-only; implementation not authorized`

Date: `2026-08-10`

## Purpose

P3 formalizes `docs/8月分析/第三阶段推进/` after the implemented
`bakery-authored-agents` slice. It adds profile-backed population activation
and continuous-world modes without creating an NPC runtime, shadow character
state, or a second world clock.

## Baseline And Owners

| Concern | Current owner / entry point | P3 use |
| --- | --- | --- |
| committed facts, revision, replay, checkpoint, outbox | `GameplayEventStore.append_batch()` | only committed writer |
| identity and cognition | CharacterProfile registry; Character Core L1-L4 | lookup and typed intent only |
| cadence and load policy | `world_runtime`; `RuntimePopulationPolicy` | extend governed entry point |
| business and needs | Organization, Production, Inventory, Economy, Survival, Government | preserve domain ownership |
| cross-domain commit | `GameplayCommandEnvelope`, `SettlementPlan` | validate then atomically append |

`PopulationPlanner`, CharacterAgent, Godot and any model are not canonical
writers. `NpcState`, duplicate household accounts, a universal scheduler and a
parallel settlement path are prohibited.

## Dependency Order

```text
P2 fresh evidence -> P3A activation/identity -> P3B modes/cadence
                  -> P3C batch intent/continuity merge -> P3D district slice
```

Hard predecessors are [P1D Econ-1 bakery](../phase-one-gameplay/2026-08-07-p1d-econ1-bakery-reference-game-design.md)
and [P2D authored-agents bakery](../phase-two-bakery-authored-agents/2026-08-09-p2d-authored-agents-bakery-vertical-slice-design.md).
Their owner contracts and fresh Harness reports are evidence inputs, not APIs to
be re-created in P3.

Each predecessor needs fresh focused replay, permission and zero-write-on-reject
evidence. P3D is the only population-backed vertical claim.

## Documents

1. [P3A profile activation and population identity](2026-08-10-p3a-profile-activation-and-population-identity-design.md)
2. [P3B world mode, cadence and obligation continuity](2026-08-10-p3b-world-mode-cadence-and-obligation-continuity-design.md)
3. [P3C batch intent and continuity merge](2026-08-10-p3c-batch-intent-and-continuity-merge-design.md)
4. [P3D bakery district population vertical slice](2026-08-10-p3d-bakery-district-population-vertical-slice-design.md)

Matching plans: [P3A](../../../plans/world-character-siming-authority-mainline/phase-three-population-continuity/2026-08-10-p3a-profile-activation-and-population-identity-implementation-plan.md),
[P3B](../../../plans/world-character-siming-authority-mainline/phase-three-population-continuity/2026-08-10-p3b-world-mode-cadence-and-obligation-continuity-implementation-plan.md),
[P3C](../../../plans/world-character-siming-authority-mainline/phase-three-population-continuity/2026-08-10-p3c-batch-intent-and-continuity-merge-implementation-plan.md),
[P3D](../../../plans/world-character-siming-authority-mainline/phase-three-population-continuity/2026-08-10-p3d-bakery-district-population-vertical-slice-implementation-plan.md).
