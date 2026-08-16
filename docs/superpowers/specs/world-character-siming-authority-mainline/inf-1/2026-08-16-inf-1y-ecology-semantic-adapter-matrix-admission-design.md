# INF-1Y Ecology Semantic Adapter Matrix Admission

Status: `implemented and verified; generic effect/state matrix remains incomplete`

## Purpose

INF-1Y extends the existing immutable semantic lifecycle adapter matrix with
one already implemented, fully contracted owner row:
`effect:frost -> state:frosted@1`. It does not create a general semantic
writer or make `SemanticEffectCommand` a substitute for the strict Ecology
frost command.

## Existing-Owner Contract

| Field | Value |
| --- | --- |
| owner | `EcologyHazardAuthority` / `authority:ecology` |
| semantic entry | `SemanticSettlementAuthority.settle_closed_ecology_frost()` |
| command | strict `SemanticEcologyFrostCommand` |
| stream | `gameplay:ecology:{region_ref}` derived by Ecology from committed hazard/crop facts |
| events | existing `gameplay.ecology.crop_state_applied` and crop-state obligation lifecycle family |
| projection / privacy | existing project-scoped Ecology crop-state projection and outbox |
| revision / idempotency | existing Ecology expected stream head and application digest |
| replay / receipt | existing `crop_state_replay()` and sole append result |

The adapter row admits `apply` only. Expiry, settlement, cancellation and any
future action remain Ecology-owner obligation operations; they are not semantic
proposal operations. The strict command continues to reject proposal-supplied
owner, stream, event type and visibility fields.

## Implementation Boundary

The closed matrix is read-only. `settle_closed_ecology_frost()` must require
the exact matrix row before it constructs an Ecology-principal envelope. The
generic `settle_registered_state()` path remains unavailable for this row,
because its input does not carry the committed hazard/crop/region evidence
needed by Ecology. No registration API, callback, direct append, new stream,
event family, projection or scheduler is admitted.

## Completion Evidence

The package is complete only when focused tests separately prove the exact
matrix row, apply-only operation fence, matrix-gated semantic entry, and the
existing INF-1X success/revision/privacy/replay evidence. A new report must
record each assertion independently. It does not complete the general
effect/state matrix.

## Verification Evidence

`infra-ecology-semantic-adapter-matrix-admission` independently proves the
matrix row and apply-only fence, matrix-gated zero-write entry rejection,
strict input, owner append, stale revision, snapshot, exact duplicate,
changed duplicate, privacy, source-relation and checkpoint-tail replay.
Evidence is at
`.harness/verification/infra-ecology-semantic-adapter-matrix-admission-report.json`.
