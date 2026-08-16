# P3A Profile Activation And Population Identity Implementation Plan

Status: `implemented-and-verified; bounded profile activation and identity slice`

## Ordered Work

1. Re-run P2 and add failing tests for resolution, grants, idempotency, stale
   revisions, suspend/requeue and zero-write rejection.
2. Add the typed proposal/schema only at the existing shared-contract and event
   schema boundary; do not introduce a profile writer.
3. Extend the existing world-runtime projection to derive activation from
   committed facts; do not persist a second character state.
4. Add full/checkpoint-tail replay and scope-filtered mirror assertions.

## Completion Gate

Run focused tests, P2 predecessor Harness, P3A Harness, docs Harness and
affected mainline regressions. Stop if a new store, scheduler owner or shadow
character state is required.
