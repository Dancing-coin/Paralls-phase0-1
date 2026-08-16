# INF-3R-A Frost Production Admission Implementation Plan

Status: `implemented and verified; no production propagation write is in scope`

## Owner map

- Ecology owner: `EcologyHazardAuthority`, existing crop stream
  `crop:{id}` and existing `semantic.effect.settled` event.
- Construction owner: `ConstructionProductionAuthority`, existing
  `gameplay:construction_production:{facility_ref}` stream and existing
  facility/run projection.
- Formal write path in this package: ecology frost settlement only, through
  its existing `SemanticSettlementAuthority -> GameplayEventStore.append_batch
  -> outbox/replay` path. Construction target selection is strictly read-only.

## Steps

1. Add focused failing tests for the committed frost source and deterministic
   construction target query, including each zero-write rejection.
2. Extend the existing ecology frost event payload with owner-supplied plot and
   provenance fields; add a committed-event source reader with scope filtering.
3. Extend the existing construction projection with a deterministic due-run
   selection query. Do not add a construction outcome event.
4. Add a separate Harness profile/report for every admitted source/target
   capability, plus full/checkpoint-tail replay proof. Construction's replay
   proof rebuilds its immutable projection prefix plus ordered tail through
   the existing projector and never writes a checkpoint.
5. Update INF-3R admission state only after the profile, focused suite, full
   pytest, and `git diff --check` pass.

## Non-goals

No hazard propagation edge, generic selector, delayed obligation, compensation,
market/body/social write, regional truth store, second clock/scheduler, or
Godot work is authorized.

## Completion record

The independent `infra-frost-production-admission` Harness profile passed its
nine capability assertions on 2026-08-13. Its focused suite passed 18 tests,
full repository pytest passed `2551 passed`, and `git diff --check` passed.
The next package must create its own consequence-settlement tests; R-A tests
are admission evidence only.
