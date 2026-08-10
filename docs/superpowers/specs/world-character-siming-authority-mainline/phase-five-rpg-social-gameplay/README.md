# Phase Five RPG And Social Gameplay Specification Tree

Status: `design-only; implementation not authorized`

Date: `2026-08-10`

## Purpose

P5 formalizes `docs/8月分析/第五阶段推进/` as gameplay-domain extensions on
P1-P4 contracts. It adds quests, evidence, relationships, knowledge,
investigation, stealth and bounded conflict without rebuilding Character Core,
ESM, Gameplay Foundation or a task/physics runtime.

## Boundary

Quest, social, knowledge and conflict authorities own their own projections and
typed proposals. CharacterAgent produces intent; Godot presents and predicts;
authority validates evidence, affordance, skill, status, ownership and policy,
then uses `SettlementPlan` and `GameplayEventStore.append_batch()`. Survival,
relationship and conflict rules remain optional mode/ruleset profiles.

## Dependency Order

```text
P4D fresh-green -> P5A quest/evidence -> P5B social/knowledge
                 -> P5C investigation/stealth/conflict -> P5D RPG slice
```

## Documents

1. [P5A quest and evidence](2026-08-10-p5a-quest-objective-and-evidence-design.md)
2. [P5B relationship and knowledge](2026-08-10-p5b-relationship-reputation-and-knowledge-design.md)
3. [P5C investigation, stealth and conflict](2026-08-10-p5c-investigation-stealth-and-conflict-design.md)
4. [P5D RPG vertical slice](2026-08-10-p5d-rpg-investigation-vertical-slice-design.md)

Matching plans: [P5A](../../../plans/world-character-siming-authority-mainline/phase-five-rpg-social-gameplay/2026-08-10-p5a-quest-objective-and-evidence-implementation-plan.md),
[P5B](../../../plans/world-character-siming-authority-mainline/phase-five-rpg-social-gameplay/2026-08-10-p5b-relationship-reputation-and-knowledge-implementation-plan.md),
[P5C](../../../plans/world-character-siming-authority-mainline/phase-five-rpg-social-gameplay/2026-08-10-p5c-investigation-stealth-and-conflict-implementation-plan.md),
[P5D](../../../plans/world-character-siming-authority-mainline/phase-five-rpg-social-gameplay/2026-08-10-p5d-rpg-investigation-vertical-slice-implementation-plan.md).
