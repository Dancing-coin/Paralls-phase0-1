# INF-2E Activation-Released Dehydration Expiry Design

Status: `implemented and verified; generic activation-obligation binding remains incomplete`

## Scope

INF-2E admits exactly one further activation-pending to Survival consequence
row. It reuses the existing two owners, streams, policy, projection and
append-derived receipt boundaries; it does not establish a generic
activation-obligation binding.

| Concern | Contract |
| --- | --- |
| Activation owner/stream | `ProfileActivationAuthority` / `population:{world_ref}` |
| Pending kind | `survival_state_expiry` only |
| Admitted state | `state:dehydrated@1` only for this package |
| Obligation | `policy:survival_state_expiry@1`, `obligation:survival:state:{actor_ref}:state:dehydrated` |
| Target owner/stream | `SurvivalAuthority` / `gameplay:survival:{actor_ref}` |
| Target fragment | existing `SurvivalAuthority.build_state_expiry_fragment()` |
| Formal writes | activation pending/release append, then separate owner fragment append |
| Receipts | two separate append-derived receipts; never a cross-stream atomic receipt |

At release, the merge consumer must derive the state from the admitted
obligation identity, verify the profile/actor, world, lock, policy, source
lifecycle, privacy and expected target revision, rebuild the same canonical
dehydration obligation, then call the existing Survival fragment through the
existing `ObligationSettlementCoordinator`.

The exact duplicate route additionally validates the event-derived settled
record's obligation, owner, stream, policy and due tick. A changed released
obligation sharing the idempotency key is zero-write rejected; the consumer may
not bypass that validation with an empty coordinator fragment set.

## Rejections and proof

Unknown state identity, unregistered state, forged pending payload, stale
target revision, terminal obligation, non-project scope, changed duplicate
payload and target-owner refusal must write zero target events. Tests and a
dedicated Harness must independently prove success, duplicate, changed
idempotency, revision, privacy, unregistered-state, terminal, replay and
separate receipt boundaries.

The permitted state set remains closed to the existing INF-2B cold row and
this dehydration row. Heat and all other lifecycle rows remain unsupported
until separately designed. No scheduler, store, coordinator writer, generic
pending queue, Economy activation binding, payment, promotion, SOC, GAME, P6
or P7 is admitted.

Evidence: `.harness/verification/infra-activation-dehydration-expiry-report.json`.
