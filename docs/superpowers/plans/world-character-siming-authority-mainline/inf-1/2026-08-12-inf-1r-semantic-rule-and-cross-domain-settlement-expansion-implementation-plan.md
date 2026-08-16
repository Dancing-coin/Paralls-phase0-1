# INF-1R Semantic Rule And Cross-Domain Settlement Expansion Plan

Status: `INF-1R production-finish mapping implemented and verified; remaining generalization deferred to INF-1X/INF-2X`

Date: `2026-08-12`

## Preconditions

- Reconfirm INF-1 and INF-2 focused evidence is fresh.
- The first vertical is fixed: `SemanticSettlementAuthority` proposal bridge to
  `ConstructionProductionAuthority.build_due_finish_fragment`, targeting
  `gameplay:construction_production:{facility_ref}` and
  `gameplay.construction_production.run_finished`.
- Reject the package if that owner requires a new truth store, direct rule
  append, or an unbounded expression interpreter.

## Work sequence

1. **Contract lock.** Add failing tests for immutable ruleset/effect/resistance
   revisions, closed phase names, stable ordering, trace redaction, and plan
   digest. Document owner map and exact event payload extensions.
2. **Pure evaluator.** Implement fixed-precision proposal evaluation with
   conflict policy, causal visited-set, depth/budget checks, and no store
   dependency. Test every failure before an authority is called.
3. **Owner mapping.** Have `ConstructionProductionAuthority` convert the typed
   proposal to `OwnerAuthorizedFragment`. Assemble only that fragment through
   existing `SettlementPlan`/`append_batch`; test a declined/overlapping
   fragment leaves event count unchanged. Do not add a second target owner in
   this package.
4. **Lifecycle integration.** Emit scheduled-expiry proposals through INF-2,
   never from a projector or timer. Test duplicate due calls, stale policy,
   closed obligation, and compensating cancellation.
5. **Projection/replay.** Extend only existing causal/scoped projections.
   Prove full and checkpoint-tail equality, filtered traces, reader upcast, and
   a rollback that preserves historical events.
6. **Evidence.** Add `infra-semantic-cross-domain` with one distinct assertion
   per capability; update August status and report remaining owner coverage.

## Delivered scope

- [x] Closed `SemanticProductionFinishCommand` accepts only
  `effect:production_due_finish` and pins snapshot, rule, trace, chain, stream
  revision, run, recipe, and tick inputs.
- [x] `SemanticSettlementAuthority` calls the sole approved owner fragment
  builder, then the existing fragment batch adapter and event store append.
- [x] Focused tests prove success, owner rejection zero-write, idempotency,
  revision conflict zero-write, privacy zero-write, and replay equivalence.
- [x] `infra-semantic-cross-domain` runs each capability as a distinct Harness
  assertion and records its report under `.harness/verification/`.

No generic rule target, lifecycle obligation, retry, compensation, economy,
survival, or ecology mapping was introduced. Those are separate packages.

## Required verification

```powershell
python -m pytest backend/tests/test_infra_semantic_cross_domain.py -q
python scripts/verification/harness.py --profile infra-semantic-cross-domain
python -m pytest -q
git diff --check
```

No broad completion claim is allowed until each named assertion, report, and
owner-specific zero-write proof exists.
