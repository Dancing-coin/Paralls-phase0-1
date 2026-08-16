# INF-2A Survival Generic Obligation Lifecycle Design

Status: `two owner rows plus Survival retry/compensation are verified; only obligation-bound activation integration remains open`

## Scope

This package generalizes the existing event-derived obligation lifecycle across
exactly two existing owners: construction completion and Survival state expiry.
It does not create an obligation truth store. Lifecycle state is reconstructed
only from committed owner events on the existing domain streams.

| Policy | Owner | Stream | Open | Terminal events | Scope |
| --- | --- | --- | --- | --- | --- |
| `policy:construction_due_completion@1` | `ConstructionProductionAuthority` | `gameplay:construction_production:{facility_ref}` | `run_started` | `obligation_settled`, `obligation_cancelled` | project |
| `policy:survival_state_expiry@1` | `SurvivalAuthority` | `gameplay:survival:{actor_ref}` | `obligation_opened` | `obligation_settled`, `obligation_cancelled` | project |

The target state vocabulary is `open`, `due`, `settled`, `cancelled`,
`expired`, `retry`, and `compensated`. Compatibility aliases may remain in the
shared data model only while no caller can use them to bypass registration.

## Boundaries

`SimulationClock` remains caller-driven bounded due selection. The existing
`ObligationSettlementCoordinator` validates registrations and submits one
atomic `GameplayEventStore.append_batch()` result. It may aggregate that result
into one `SettlementReceipt`; it cannot author a Survival or construction
outcome. Retry, cancellation and compensation each require a registered owner
event type and a committed source correlation. No background scheduler, clock,
store, receipt database, population owner or coordinator writer is allowed.

Survival activation merge, if admitted, must reuse the existing
`ProfileActivationAuthority` lock/pending/release event path at a pinned
revision. It cannot be implemented as a clock-side queue.

## Current Evidence And Remaining Work

The read-only projection rebuilds construction and Survival open/settled/
cancelled facts from the existing owner streams. `SurvivalAuthority` also owns
the explicit `gameplay.survival.obligation_retry_scheduled` row, registered
only for `policy:survival_state_expiry@1`; its next due tick and bounded attempt
fields are reconstructed without a second writer. Construction retry remains
unregistered and zero-write rejected.

`SurvivalAuthority` additionally owns the explicit inverse row
`state_compensated + obligation_compensated`. It is admissible only after the
same obligation has an event-derived `settled` record, with an explicit restore
snapshot, project scope, append-derived receipt, duplicate replay and
checkpoint-tail proof. Construction retry/compensation remains unregistered.

Activation locks remain owned by `ProfileActivationAuthority` and are not
connected to Survival obligations. INF-4C now proves one event-derived released
`schedule_gated_supply` row into the existing Organization fragment, but it is
not a `ScheduledObligation` binding. Joining a Survival obligation requires a
separate named owner-side pending payload and receipt contract. This remains
open work and the package does not claim a universal lifecycle closure.

### Formal activation-pending blocker

Blocked: there is no owner-authorized activation pending-merge mapping for
`ScheduledObligation` settlement. `ProfileActivationAuthority` now commits
canonical `population.activation.pending_recorded` and release events for the
sole `schedule_gated_supply` payload, with an event-derived scoped projection;
INF-4C delegates only that released row to the existing Organization fragment.
There is still no pending payload, `OwnerAuthorizedFragment` surface, or
unified `SettlementReceipt` contract binding a Survival obligation on
`gameplay:survival:{actor_ref}` to activation lock/release. Future work must
name that exact owner event family, privacy, revision vector and atomicity; it
must not place queue or lock state in the clock or coordinator.

## Completion Conditions

Focused RED tests must precede implementation. The dedicated profile must
independently prove two-domain open/due/settled/cancelled reconstruction,
bounded catch-up, duplicate/revision/privacy/replay/zero-write, and every
enabled retry/cancel/compensation transition. An owner without a registered
failure/compensation event stays zero-write rejected. This package does not
claim universal domain policies, ecology retry, branch work, SOC/GAME/P6/P7.
