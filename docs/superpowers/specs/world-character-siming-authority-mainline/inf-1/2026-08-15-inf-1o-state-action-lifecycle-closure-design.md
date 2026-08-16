# INF-1O State Action Lifecycle Closure Design

Status: `implemented and verified 2026-08-15; bounded Survival action closure only`

## Scope

INF-1O closes the missing action semantics for the already-admitted Survival
state rows. It extends the existing pure `EffectLifecycleEvaluator` with
owner-neutral, constrained decisions for `dispel` and `transform`, then makes
the existing `SurvivalAuthority` action fragments consume those decisions.
The evaluator remains proposal-only; only `SurvivalAuthority` may append to
`gameplay:survival:{actor_ref}`.

```text
semantic proposal -> constrained lifecycle decision
-> SurvivalAuthority owner fragment -> append_batch -> outbox/replay/projection
```

The admitted rows remain exactly `state:cold`, `state:overheated`, and
`state:dehydrated` with their existing `actor_gameplay.survival_domain` owner,
stream, event family, privacy scope, revision checks, and receipts. No new
state owner, dynamic transform script, caller-open registration, or arbitrary
effect router is admitted.

## Contract

- `StateDefinition` retains `add`, `replace`, `refresh`, and `reject` stack
  policies and stack limits, and explicitly describes whether dispel is allowed
  and which fixed transform targets are admitted.
- `EffectLifecycleEvaluator` returns a pure action decision for apply, dispel,
  and transform. Unknown action/target combinations are rejected without a
  write. Selectors remain finite registered predicates; no Python, lambda, or
  free expression is evaluated.
- A dispel decision clears only the named existing state. A transform decision
  must name one registered target state and retains the source causal chain.
- Survival action fragments remain the only formal write path. A rejected,
  stale, private, forged, duplicate, or changed-duplicate action yields zero
  events and zero outbox entries.

## Evidence

Focused tests must independently prove apply stack semantics, dispel decision
and owner settlement, transform decision and owner settlement, unknown target
rejection, idempotency, revision/privacy zero-write, and full/checkpoint-tail
replay for each admitted Survival row. Harness selectors must map one-to-one to
those capabilities.

Evidence: `.harness/verification/infra-state-action-lifecycle-closure-report.json`
records thirteen independently executed selectors. The focused suite is
`backend/tests/test_semantic_effect_lifecycle.py` and
`backend/tests/test_infra_semantic_survival_state_action.py`.

## Non-goals

This package does not add a generic state writer, open owner registration,
Construction/Ecology action rows, arbitrary transforms, scheduler, second
store, or population/social truth. The broader cross-owner effect/state matrix
remains blocked until each target owner supplies its own event/projection/receipt
contract.
