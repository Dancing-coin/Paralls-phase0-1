# Unified Bakery Gameplay Loop v1 Design

Status: `implementation-authorized`

## Goal

Provide one playable, owner-bound three-period bakery loop over the existing
Character, Skill, Survival, Inventory, Construction/Production, Economy,
Organization, Government and Contract authorities.

## Canonical flow

```text
period open -> permit/organization validation -> material purchase and custody
-> recipe run -> output certification/custody -> quote/sale -> wage/tax
-> survival update -> period close -> next period
```

The loop is a composition over existing owners, not a new bakery mega-owner.
Every cross-owner handoff uses committed source evidence, exact descriptors,
owner fragments, append-derived receipts and source revision pins.

## Scope

- one real `character:char_a` owner CharacterRecord and one `org:bakery` organization;
- three consecutive periods with deterministic period refs;
- fixed flour input, bread output, permit, wage/tax policies and aggregate demand;
- profile-backed employee work contributions and verified completion evidence feed
  the existing Economy wage obligation/accrual/payment path;
- success, insufficient material/funds/skill, expired permit, facility failure,
  production failure and recovery outcomes;
- read-only committed projection for Godot; speculative UI state is discarded
  on rejection;
- full replay and checkpoint-tail replay equality.

Population remains signal-only in v1; no hidden employee/customer NPC state is
created. Existing narrow rows and all owner boundaries remain compatible.

## Non-goals

No generic payment/transform/settlement writer, dynamic scheduler, second event
store/runtime, arbitrary recipe resolver, population shadow state, or automatic
compensation/reversal is introduced.

## Completion gate

The loop is complete only when a single command can run all three periods,
produce committed owner events and receipts, recover from one injected failure,
and yield identical full/tail replay and Godot read models. Focused tests,
independent Harness, repository regression and Godot headless/desktop smoke are
required evidence.
