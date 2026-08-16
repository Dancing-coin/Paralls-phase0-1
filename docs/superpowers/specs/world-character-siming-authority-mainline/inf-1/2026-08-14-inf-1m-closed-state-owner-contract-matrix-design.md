# INF-1M Closed State Owner Contract Matrix

Status: `implemented and verified closed five-row matrix; generic routing remains incomplete`

## Problem

The verified INF-1 rows currently prove individual owner submissions, but the
authoritative state matrix is split between hard-coded SemanticRegistry
branches and one Ecology-local row. This is not sufficient evidence that the
same owner/stream/event/privacy/revision contract is consistently consumed at
each authoritative write boundary.

## Decision

INF-1M introduces one closed, immutable `StateOwnerContract` matrix in the
existing semantic registry module. It is a contract reader, not a new runtime,
writer, owner, scheduler, or dynamic registration API. Every row is fixed and
each existing authority must query the same row before building an append
fragment.

| row | effect/state | authority | stream | lifecycle family | privacy |
| --- | --- | --- | --- | --- | --- |
| survival-cold | `effect:cold_exposure -> state:cold` | `SurvivalAuthority` | `gameplay:survival:{actor_ref}` | `state_applied/obligation_opened/state_expired/obligation_settled` | project |
| survival-overheated | `effect:heat_exposure -> state:overheated` | `SurvivalAuthority` | `gameplay:survival:{actor_ref}` | same Survival family | project |
| survival-dehydrated | `effect:dehydration_exposure -> state:dehydrated` | `SurvivalAuthority` | `gameplay:survival:{actor_ref}` | same Survival family | project |
| construction-maintenance | `effect:maintenance_required -> state:maintenance_due` | `ConstructionProductionAuthority` | `gameplay:construction_production:{facility_ref}` | `maintenance_state_applied` | project |
| ecology-frost | `effect:frost -> state:frosted@1` | `EcologyHazardAuthority` | `gameplay:ecology:{region_ref}` | `crop_state_applied/crop_state_obligation_opened/crop_state_expired/crop_state_obligation_settled` | project |

Economy wage and Survival dispel/transform remain separate effect/action routes:
they do not claim `StateDefinition` semantics and are not silently folded into
this matrix.

## Required Owner Behavior

Each owner must obtain its exact row by `(effect_ref, state_ref)` and reject
before `append_batch()` when any of these differ: principal, stream pattern,
fixed StateDefinition, visibility, lifecycle event family, or expected
revision identity. The registry itself has no append capability and cannot
turn a proposal into truth. Semantic dispatch remains closed to rows which
explicitly accept semantic proposals; the Ecology row stays hazard-source
admitted and cannot be called through a semantic client command.

The pre-existing direct Survival compatibility surface may still record an
unregistered local state/effect input for legacy lifecycle tests. Such input is
not a matrix row, is never returned by this reader, and remains rejected by
the activation/semantic binding admission fence. INF-1M must not silently
change that compatibility behavior into a new authority or use it as matrix
coverage.

## Tests And Evidence

Focused RED tests must prove:

- all five rows are materialized from one contract reader;
- each of Survival, Construction, and Ecology rejects a mismatched row before
  append;
- existing valid owner writes, duplicate semantics, revision/privacy fences,
  scoped projections and replay remain intact;
- unknown rows remain zero-write; and
- the matrix cannot expose a caller-defined owner, stream, adapter or event
  family.

A dedicated Harness must have independent assertions for matrix shape, each
owner's enforced lookup, unknown-row rejection, write-path preservation,
privacy, full replay and checkpoint-tail replay.

Evidence: `.harness/verification/infra-closed-state-owner-contract-matrix-report.json`
records nine independent passing checks. Each existing authority performs the
lookup before its existing append path, and forged contract metadata is proven
zero-write for Survival, Construction and Ecology.

## Non-goals

No arbitrary effect registration, generic owner dispatch, user-authored rule
execution, new event store, background scheduling, cross-domain mutation or
additional Ecology consumer edge is admitted. This matrix is a finite policy
artifact over already approved owners, not a permission bypass.
