# INF-3AA Weather Rain Water Resource Recovery Implementation Plan

**Goal:** Implement one exact `weather:rain -> unique water ResourceNode +10` Ecology vertical with project privacy, zero-write admission, append-derived receipt, and replay proof.

**Architecture:** Reuse `EcologyHazardAuthority`, the existing regional stream,
`GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`,
and regional replay. Add one immutable catalog contract/descriptor and one
fixed provenance partition on `gameplay.ecology.resource.recorded`; do not add
an Ecology consumer registry or cross-domain fragment.

---

1. Add focused RED tests for success, zero/multiple/full water resources,
   wrong/private/stale/non-rain source, idempotency/change mismatch, forged
   replay provenance, and full/checkpoint-tail equality.
2. Add one immutable `inf:ecology-weather-rain-water-resource-recovery@1`
   catalog contract and descriptor with the fixed predicate/effect refs.
3. Implement the owner-bound recovery method in `ecology_runtime.py`; derive
   the unique resource and all authority coordinates from committed facts.
4. Extend regional replay validation for only this `row_ref` partition.
5. Add independent verifier/Harness profile; run focused tests, Harness,
   continuation gate, docs check, compileall, and diff check.
6. Synchronize INF-3 README, completion audit, remaining-scope, blocker
   taxonomy, and checkpoint. Keep August INF A-D `not complete`.
