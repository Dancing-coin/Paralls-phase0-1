# INF-3 Weather Rain To Crop Health Recovery Blocker Plan

Status: `blocked pending minimum business decisions; no implementation authorized`

## Scope

Evaluate one possible Ecology-owned row:

```text
committed project-visible weather:rain front
  + one exact current damaged CropRecord in the target region
-> one Ecology crop health recovery record
```

This plan is not a generic crop recovery plan. It excludes
`drought_process_advanced` as a source, fanout, arbitrary crop selection,
inventory/output/payment/production effects, new owners, routers, registries,
and alternate write paths.

## Gate 0: Existing-Fact Audit

- [x] Confirm the committed source event is
      `gameplay.ecology.weather_front.propagated@1`.
- [x] Confirm only `weather_ref=weather:rain` is admissible.
- [x] Confirm source and target are project-scoped Ecology streams.
- [x] Confirm current `CropRecord` fields and regional projection behavior.
- [x] Confirm no existing row supplies crop identity, damage predicate, rain
      recovery delta, or lifecycle semantics.
- [x] Preserve existing Ecology/weather regression baseline (`16 passed`).

## Gate 1: Business Decisions Required

- [ ] Approve an exact one-crop selector or a committed source binding.
- [ ] Approve a named owner-derived damaged predicate.
- [ ] Approve an immutable rain recovery policy revision and deterministic
      health result.
- [ ] Approve whether existing `crop.recorded` can carry the fixed provenance
      contract, or separately admit an exact event family.
- [ ] Approve repeat/terminal/reversal/compensation semantics.

Until all five decisions are explicit, the row is zero-write and remains
`owner-contract blocked`.

## Gate 2: Contract And Admission

After Gate 1, write the row-specific Owner-Admission Contract, then obtain
the corresponding immutable catalog admission if the existing catalog model
requires it. Pin source event/revisions, target crop revision, policy and
predicate revisions, project privacy, idempotency, receipt, and replay.

No default selector, delta, policy, terminal rule, or caller-selected
authority coordinate is permitted.

## Gate 3: TDD And Runtime, Only If Reopened

Only after a complete contract is approved:

1. Write focused RED tests for success and every zero-write boundary.
2. Verify RED fails for the missing row behavior.
3. Implement the exact owner-bound verifier and fixed reducer/append vector in
   `EcologyHazardAuthority`.
4. Reuse `GameplayCommandEnvelope -> SettlementPlan ->
   GameplayEventStore.append_batch()`.
5. Add no generic crop recovery surface.
6. Verify receipt, privacy, revisions, idempotency, full replay, and
   checkpoint-tail replay with an independent Harness.

## Stop Conditions

Stop without runtime changes if:

- source event payload cannot prove the exact crop identity;
- the target region has zero or multiple eligible crops under the approved
  selector;
- the existing event schema cannot carry fixed provenance without a new
  platform/schema decision;
- replay cannot distinguish this row from ordinary crop writes;
- any requested behavior implies fanout, cross-domain facts, compensation,
  or a generic recovery API.

