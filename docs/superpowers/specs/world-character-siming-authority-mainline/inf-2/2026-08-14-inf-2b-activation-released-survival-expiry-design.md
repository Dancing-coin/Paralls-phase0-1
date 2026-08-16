# INF-2B Activation-Released Survival Expiry Design

Status: `implemented and verified for one released Survival state:cold@1 expiry row; August INF-2 closure remains incomplete`

## Scope

This package adds one owner-bound activation release consumer for the existing
Survival `state:cold@1` expiry obligation. It does not create a generic pending
queue, a second scheduler, a population owner, or a two-stream coordinator
writer.

| Concern | Contract |
| --- | --- |
| Activation owner | existing `ProfileActivationAuthority` |
| Activation stream | `population:{world_ref}` |
| Pending kind | `survival_state_expiry` only |
| Survival owner | existing `SurvivalAuthority` |
| Survival stream | `gameplay:survival:{actor_ref}` |
| Source lifecycle | registered `policy:survival_state_expiry@1` open/due record |
| Consequence | existing `SurvivalAuthority.build_state_expiry_fragment()` through `ObligationSettlementCoordinator` |
| Receipts | activation release receipt and Survival `SettlementReceipt` remain separate, each derived from exactly one append batch |

The pending record pins only `world_ref`, `profile_ref`, `lock_ref`, obligation
identity, policy revision and expected survival revision. At release, the
consumer rebuilds the registered Survival obligation from the existing event
projection, verifies the pending row, released lock, profile/actor identity,
scope and revisions, and then invokes the existing Survival owner fragment.
The activation event and Survival settlement are deliberately separate formal
writes; no result may present their event ids as one atomic receipt.

## Evidence

`infra-activation-survival-expiry` independently asserts owner-fragment
success, duplicate idempotency, revision conflict zero-write, privacy zero-write,
terminal-obligation zero-write and checkpoint-tail replay. Its report records
the two independent append-derived receipt boundaries.

## Rejections and non-goals

Unknown pending kinds, unregistered/terminal/stale obligations, mismatched
profile/actor/world/lock, private scope, forged payload, changed idempotency
and any revision conflict are zero-write for the Survival target. The package
does not add expiry policy rows, generic activation-obligation binding,
cross-domain atomicity, economy lifecycle, branch promotion, SOC, GAME, P6 or
P7.
