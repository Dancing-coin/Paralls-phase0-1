# Phase Three Population Continuity Plan Tree

Status: `design-only; implementation not authorized`

Date: `2026-08-10`

Implement only after P2 evidence is re-run and implementation authorization is
recorded. Preserve one `GameplayEventStore.append_batch()` commit path, the
existing `world_runtime` cadence boundary, CharacterProfile identity and
per-domain ownership. No plan authorizes `NpcState`, a global simulation
clock, planner writes or dynamic market clearing.

## Gate

```text
P2 fresh-green -> P3A -> P3B -> P3C -> P3D
```

Every step starts with focused contract tests and ends with full/checkpoint-tail
replay, idempotency and stale-revision rejection, scope-filtered mirror, and
zero events after denied input.

## Plans

1. [P3A plan](2026-08-10-p3a-profile-activation-and-population-identity-implementation-plan.md)
2. [P3B plan](2026-08-10-p3b-world-mode-cadence-and-obligation-continuity-implementation-plan.md)
3. [P3C plan](2026-08-10-p3c-batch-intent-and-continuity-merge-implementation-plan.md)
4. [P3D plan](2026-08-10-p3d-bakery-district-population-vertical-slice-implementation-plan.md)

阶段级执行提示词：
[Phase Three Population Continuity Execution Prompt](2026-08-10-phase-three-population-continuity-execution-prompt.md)
