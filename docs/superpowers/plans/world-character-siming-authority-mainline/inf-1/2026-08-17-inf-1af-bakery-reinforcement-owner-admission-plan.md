# INF-1AF Bakery Reinforcement Owner-Admission Plan

Status: `implemented narrow vertical; verified 2026-08-17`

## Preconditions

1. The federated owner/capability admission decision remains approved.
2. The INF-1AF exact transform audit remains durable evidence that a generic
   transform contract is incomplete.
3. The accompanying bakery-reinforcement contract receives separate explicit
   row approval. Approval of the governing mechanism or INF-1AE repair does
   not approve this transform.

## Completed Sequence

1. Wrote focused RED tests using only the existing facility-acquisition API;
   do not fabricate an acquisition, transform, or target fact with direct
   `append_batch()`.
2. Added one immutable catalog row after approval, fixing the Construction
   owner, single facility stream, `facility_transformed` event, project scope,
   receipt reader, and projector replay reader.
3. Extended only the existing `ConstructionProductionAuthority` projector and
   one fixed typed operation. Resolve the target `bakery_reinforced` inside
   the owner; never accept a caller-selected kind, stream, event, scope,
   material, payment, revision, receipt, retry, or compensation rule.
4. Built exactly one Construction owner fragment through the existing
   `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`
   spine. No other owner writes and no new runtime, router, registry, or
   coordinator is introduced.
5. Kept the transform terminal. No repair reuse, compensation, reopen,
   retry, material/payment settlement, or fanout.
6. Added an independent Harness profile proving success, zero-write rejection,
   project privacy, source/target revisions, exact/changed idempotency,
   append-derived receipt, full replay, checkpoint-tail replay, and no
   compensation. Run focused tests, the profile, affected regressions, and
   full pytest with repository-local `--basetemp` as environment permits.
7. Synchronized the formal audit, completion audit, remaining-scope matrix,
   package README, continuation checkpoint, Harness docs, and verification
   records only after evidence is green.

## Forbidden Scope

- no generic facility transform, action router, policy/blueprint registry, or
  caller-selected target kind;
- no new Construction truth owner, payment/material/permit fact, generic
  settlement, compensation, fanout, or second runtime/store/bus/clock/scheduler;
- no reinterpretation of repair compensation as transform reversal; and
- no implementation occurred before explicit approval of this exact row.
