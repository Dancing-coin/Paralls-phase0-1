# Mainline Capability Implementation Plan

Status: `active plan; implementation begins at INF-1`

## Delivery sequence

1. **INF-1A: contracts and registry.** Extend the existing semantic models with
   tag categories, assignments, constrained selectors, parent-graph validation,
   deterministic parameter merge and immutable snapshot digests. Reject unknown
   fields, inheritance loops, unknown parameters and equal-priority conflicts.
2. **INF-1B: entity and causal projection.** Add a projection over committed
   events for stable entity dossiers and append-only causal parents. Do not add
   a new truth store; snapshots are derived/rebuildable from registered input
   plus committed events.
3. **INF-1C: proposal bridge.** Let closed handlers create typed owner fragments
   and a `SettlementPlan`; only existing owners call `append_batch`. Produce a
   filtered causal explanation projection after commit.
4. **INF-1D: verification.** Add focused tests and `infra-semantic-entity-causal`
   Harness profile. Its report must enumerate each assertion instead of turning
   one pytest result into many capability booleans. Update August guidance with
   actual scope and remaining gaps.
5. **INF-2.** Implement caller-driven clock/obligation evaluation only after
   INF-1D. The first slice is now `backend/app/world_runtime/simulation_clock.py`
   with `infra-time-obligation`; next add owner lifecycle events, activation
   locks/pending changes and a receipt adapter over `GameplayEventStore`.
6. **INF-3.** Move frost-farm from a bounded sample to the ecology first vertical
   slice, using region/hazard records and INF-2 due evaluation.
7. **INF-4.** Expand population continuity only with existing profile identity
   and projection-derived family/organization input; add branch-preview replay.
8. **SOC-1 and GAME-1.** Split each subsystem into a separate spec/plan/profile
   before code: social graph before rumor/disclosure; action registry before
   combat; needs scheduling before long-cycle survival; package-specific
   construction and cultivation after generic action/resource contracts.
9. **CREATOR-1 then COST-1.** Creator publishing cannot precede package
   validation/activation proof. Metering cannot authorize or bypass domain
   writes.

## INF-1 verification commands

```powershell
python -m pytest backend/tests/test_infra_semantic_entity_causal.py -q
python scripts/verification/harness.py --profile infra-semantic-entity-causal
python scripts/verification/harness.py --profile all
git diff --check
```

## Stop conditions

Do not start INF-2 if INF-1 is only model definitions without an event-derived
causal projection, zero-write rejection proof and standalone Harness evidence.
Do not start P6/P7 from a contract-sample profile.
