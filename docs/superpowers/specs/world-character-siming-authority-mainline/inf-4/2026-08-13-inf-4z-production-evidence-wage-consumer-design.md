# INF-4Z Production Evidence Wage Consumer

Status: `implemented and verified narrow consumer package; generic work remains rejected`

## Scope

This package admits one and only one `work` consumer row:

```text
ProductionCompletedEvidenceView (matching worker actor scope)
  -> frozen source input
  -> PopulationPlanner work proposal
  -> EconomyAuthority wage accrual fragment
  -> existing gameplay:economy:wage:{worker_ref} stream
```

It does not admit generic work, non-production evidence, payroll payment,
organization-owned attendance truth, population truth, retry, compensation,
civilization input, P6, or P7.

## Owner matrix

| Element | Contract |
| --- | --- |
| Source owner | existing `ConstructionProductionAuthority` / `actor_gameplay.construction_production_domain` |
| Source stream/event | existing `gameplay:construction_production:{facility_ref}` / `gameplay.construction_production.work_completion_evidence_recorded` |
| Source reader | `ProductionCompletedEvidenceView` for the matching worker actor only; the population planner receives only a frozen input, never authority scope |
| Consumer owner | existing `EconomyAuthority` / `actor_gameplay.econ1_economy_domain` |
| Target stream/event | existing `gameplay:economy:wage:{worker_ref}` / `gameplay.economy.wage_accrued` |
| Formal write path | planner proposal -> `EconomyAuthority.settle_production_evidence_wage_accrual` -> `GameplayCommandEnvelope` / `SettlementPlan` -> `GameplayEventStore.append_batch()` -> outbox/replay -> scoped projection |
| Receipt | existing `AppendBatchResult` under the Economy principal; Population merge returns only the owner receipt reference |

The frozen source input pins worker recipient, source owner, exact canonical
view digest, source event refs, source revision vector, and the source evidence
refs. The merge re-reads Production's scoped worker view, rejects any mismatch
or stale source before calling Economy, and pins the source vector, digest,
event refs, wage policy revision, and target wage stream revision in the wage
event. The event is `actor:{worker_ref}` scoped and its outbox projection
contains only accrual/evidence references.

## Rejections and replay

Only a candidate whose `intent_kind == "work"`, profile/worker ref matches the
source recipient, evidence refs exactly match the frozen source, and policy,
source and wage revisions are pinned may reach Economy. Empty/forged source,
authority/public source recipient, another evidence kind, stale production or
wage revisions, privacy mismatch, duplicate mutation, and any unlisted work
candidate are zero-write.

Full and checkpoint-tail replay must reproduce the same target wage event and
the frozen source input must validate to the same view digest/vector at merge.
Corrections remain future owner events; no compensation is introduced.

## Completion evidence

Focused tests and the dedicated `infra-production-evidence-wage-consumer`
Harness profile independently prove:
source freeze/owner scope, envelope-plan wage write, source event/vector/digest
pins, event/outbox privacy, forged/stale/privacy zero-write, duplicate and
changed duplicate, source/target revision conflict, and full/checkpoint-tail
replay. `generic work` remains rejected outside this one source/consumer row.
