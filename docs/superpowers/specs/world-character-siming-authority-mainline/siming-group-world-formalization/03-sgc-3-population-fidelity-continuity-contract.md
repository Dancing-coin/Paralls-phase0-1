# SGC-3 Population Fidelity Continuity Contract

Status: `proposed; cadence source and owner-bound consumer required`

## Scope

This package defines how one `CharacterRecord` moves between far, mid and near
fidelity while preserving identity, memory and owner boundaries. It does not
create population truth, shadow NPCs, a second clock or a universal scheduler.

## Contract

The state machine is `dormant -> batch_planned -> prewarm -> active ->
pending_merge`, with requeue to `batch_planned` on stale reads/conflicts and
release to `dormant` on budget/attention loss. A batch pins world-mode ref and
revision, cadence source ref and revision, scoped source vector, policy/ruleset
revision, seed, selector revision, budget and report scope.

Cadence must come from an existing committed world-mode/activation/schedule
projection. Wall-clock time, process order and model improvisation cannot
advance a batch. Missing, private, revoked or stale cadence is an audited
no-op/requeue.

Far output is one of `presentation_seed`, `activation_candidate` or
`owner_bound_intent`. The first is a rebuildable PresentationView input and
never an event; the second changes scheduling only; the third reaches one
static catalog capability and then the existing owner path. Prewarm cannot
load private memory. Active requires the existing activation lock.

## Evidence contract

Tests and Harness must prove deterministic cohort order, fairness/starvation
credit, prewarm privacy, activation-lock conflict, stale merge/requeue,
zero-write presentation-only output, owner receipt and full/tail replay.

## Dependencies and non-goals

Depends on one existing cadence projection and one approved owner-bound
consumer. Broad population/social/civilization truth remains unimplemented or
blocked; this package does not generalize it.
