# INF-3R-B Production Recipe Admission Implementation Plan

Status: `implemented and verified; no frost consequence write is in scope`

## Admission gate

1. Add focused failing tests for a committed recipe snapshot on the existing
   construction `run_started` event and a read-only authority-scoped result.
2. Extend `ConstructionProductionAuthority.settle_start_run` to carry only
   immutable fragment inputs in that existing event, and extend its existing
   projector with the corresponding snapshot map.
3. Add an authority-only recipe query with source revision checking. Missing,
   legacy, stale, and public-scope inputs reject without a write; no caller
   fallback, registry, stream, runtime, or scheduler is permitted.
4. Prove full and prefix-plus-tail projector rebuild equivalence, then add one
   independent Harness assertion per admitted capability and update evidence.

## Future verification, only after admission

The package must establish failing tests before production code and give each
capability an independent Harness assertion: committed recipe retrieval,
public/authority privacy, missing/legacy/stale zero-write rejection,
idempotency, and full/checkpoint-tail replay. Its report becomes an additional
predecessor for INF-3R; it does not write a production outcome.

## Completion record

The independent profile passed all five declared assertions on 2026-08-13.
Focused evidence passed 25 tests, full pytest passed `2556 passed`, and
`git diff --check` passed. The next package must still add its own frost
consequence tests and Harness profile.
