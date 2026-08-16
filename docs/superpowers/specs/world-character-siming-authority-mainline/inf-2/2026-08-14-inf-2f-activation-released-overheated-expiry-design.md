# INF-2F Activation-Released Overheated Expiry Design

Status: `implemented and verified for one released Survival state:overheated@1 expiry row; generic activation-obligation binding remains incomplete`

## Scope

INF-2F admits exactly one third activation-pending to Survival consequence row.
It reuses the existing `ProfileActivationAuthority`, `SurvivalAuthority`,
`ScheduledObligation`, coordinator, event store, projections and receipt
boundaries. It does not create a generic pending queue, scheduler, clock,
population owner, cross-stream receipt, or target-domain writer.

| Concern | Contract |
| --- | --- |
| Activation owner/stream | existing `ProfileActivationAuthority` / `population:{world_ref}` |
| Pending kind | `survival_state_expiry` only |
| Admitted state | `state:overheated@1` only for this package |
| Obligation | `policy:survival_state_expiry@1`, `obligation:survival:state:{actor_ref}:state:overheated` |
| Target owner/stream | existing `SurvivalAuthority` / `gameplay:survival:{actor_ref}` |
| Target fragment | existing `SurvivalAuthority.build_state_expiry_fragment()` |
| Formal writes | activation pending/release append, then a separate existing-owner fragment append |
| Receipts | separate activation append receipt and Survival `SettlementReceipt`; never a cross-stream atomic receipt |
| Privacy | `project` only |

At release the merge consumer must derive the state only from the admitted
obligation identity, validate profile/actor/world/lock/policy/source lifecycle,
privacy and target revision, rebuild the canonical existing Survival obligation,
and invoke the existing Survival fragment through the existing
`ObligationSettlementCoordinator`. The consumer may not select an owner,
stream, event family, policy or fragment from caller data.

## Rejections

The exact state admission is closed. `cold` and `dehydrated` remain their own
already verified rows; every other state, pending kind, owner, stream, privacy
scope, forged payload, stale revision, terminal obligation or changed
idempotency payload is zero-write for the Survival target. Exact repeats must
replay only the event-derived settled record that matches obligation, owner,
stream, policy and due tick.

## Evidence

`infra-activation-overheated-expiry` independently proves success, exact
duplicate, changed duplicate zero-write, changed pending duplicate zero
activation write, revision conflict, privacy, unsupported-state and terminal
zero-write, scoped project outbox, full/checkpoint-tail replay and the two
separate append-derived receipt boundaries. Evidence is
`.harness/verification/infra-activation-overheated-expiry-report.json`.
The implementation retains:

`ProfileActivationAuthority -> pending/release event -> event-derived projection -> SurvivalAuthority fragment -> SettlementPlan -> GameplayEventStore.append_batch() -> outbox/replay -> scoped projection`.

No generic activation-obligation binding, payment/account lifecycle, branch
promotion, SOC, GAME, P6 or P7 is admitted.
