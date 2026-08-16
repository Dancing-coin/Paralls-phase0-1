# INF-1F Registered Survival State Owner Matrix Design

Status: `implemented and verified for three existing Survival rows; generic cross-domain matrix remains incomplete`

## Scope

INF-1F removes the duplicate hard-coded effect-to-state mapping from the semantic
bridge. Every registered scheduled `StateLifecyclePolicy` now includes an
`effect_ref`, and `SemanticRegistry.scheduled_state_owner_row()` returns the
single exact policy row only when its state/effect pair matches.

| State | Effect | Owner | Stream | Events | Privacy |
| --- | --- | --- | --- | --- | --- |
| `state:cold` | `effect:cold_exposure` | `SurvivalAuthority` | `gameplay:survival:{actor_ref}` | existing state/obligation lifecycle | `project` |
| `state:overheated` | `effect:heat_exposure` | `SurvivalAuthority` | same | same | `project` |
| `state:dehydrated` | `effect:dehydration_exposure` | `SurvivalAuthority` | same | same | `project` |

No new owner, stream, event family, state/effect, runtime, clock, scheduler or
store is created. `SemanticSettlementAuthority` still produces a proposal and
calls the existing `SurvivalAuthority`, which is the sole writer through the
existing command/envelope and `GameplayEventStore.append_batch()` path.

## Admission

The registration predicate remains closed over the three table rows above. An
effect/state mismatch, an unknown state, a wrong owner/stream/event/privacy
tuple, or any cross-domain owner is rejected before append. The matrix is a
deterministic read model of registered rows, not a facility for callers to
register arbitrary owner mappings.

## Completion evidence

`infra-semantic-state-owner-matrix` independently asserts exact row lookup,
effect/state mismatch, unregistered owner denial, deterministic enumeration,
owner append, duplicate idempotency, revision conflict, privacy zero-write and
checkpoint-tail replay. Evidence is
`.harness/verification/infra-semantic-state-owner-matrix-report.json`.

This package does not complete generic effect/state lifecycle, generic owner
matrix, new resistance owners, or cross-domain semantic settlement.
