# INF-3Q Drought Weather-Front To Survival Dehydration Owner-Admission Plan

Status: `implemented narrow vertical; verified 2026-08-17`

## Preconditions

1. The federated owner/capability admission decision is approved.
2. The INF-3Q bounded audit confirms the existing-owner discovery lane is
   exhausted without treating the Ecology drought process as a weather front.
3. This exact target-edge design received explicit row approval. Approval of
   the federated mechanism alone would not have been sufficient.

## Executed Sequence

1. Focused RED tests were written for the exact `weather:drought` source event,
   committed actor-region assignment, Survival dehydration lifecycle, and
   zero-write rejection boundary. The tests must not call `append_batch()` to
   fabricate future source or target facts.
2. One immutable catalog entry fixes the Survival
   owner, target stream/event family, project scope, receipt reader and replay
   reader. No runtime registration API is allowed.
3. Only the existing `SurvivalAuthority` was extended with the fixed typed intent
   operation. Resolve the source event and assignment pins from committed
   store evidence; never accept caller-selected stream/event/privacy/revision
   values or a `drought_process_advanced` substitute.
4. Exactly one Survival owner fragment is built for
   `state_applied` + `obligation_opened` through the existing envelope,
   SettlementPlan, and `append_batch()` spine. Do not write Ecology facts,
   fan out to multiple actors/regions, or add a router.
5. The actor-safe append-derived receipt and scoped replay reader prove
   full and checkpoint-tail equality using the same Survival events and keep
   source/assignment facts as read-set evidence only.
6. Expiry is verified as the only terminal path. No
   compensation, source retraction, reopen, generic retry, or state routing.
7. The independent Harness profile covers success, zero-write rejection,
   privacy, revision, idempotency, receipt, full replay and checkpoint-tail
   replay selectors, plus the no-compensation boundary.
8. Focused tests (`9 passed`), the independent Harness (green), and affected
   regressions (`54 passed`) ran with repository-local `--basetemp`.
   Completion audit, remaining scope, package README, checkpoint, Harness docs
   and verification records are synchronized. Full pytest remains subject to
   the documented workspace environment limitation.

## Forbidden Scope

- no new truth owner, generic Ecology-to-Survival router, or consumer registry;
- no drought-process reinterpretation as a weather-front source;
- no caller-selected owner, stream, event, state, privacy, revision, receipt,
  retry or compensation rule;
- no multi-target fanout, population/social truth, branch input, or second
  runtime/store/bus/clock/scheduler; and
- no implementation before explicit approval of this exact row.
