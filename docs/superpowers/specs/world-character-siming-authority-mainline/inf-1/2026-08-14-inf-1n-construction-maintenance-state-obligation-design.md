# INF-1N Construction Maintenance State Obligation Design

Status: `implemented and verified; fixed Construction lifecycle row only`

## Purpose

INF-1G proved one Construction-owned `effect:maintenance_required ->
state:maintenance_due` apply row. It did not give that state an event-derived
expiry lifecycle. INF-1N closes that owner-local gap without treating the
finite semantic matrix as a generic router.

## Existing-Owner Contract

| Concern | Contract |
| --- | --- |
| Target owner | existing `ConstructionProductionAuthority` / `actor_gameplay.construction_production_domain` |
| Canonical stream | existing `gameplay:construction_production:{facility_ref}` only |
| State/effect | fixed `effect:maintenance_required -> state:maintenance_due` only |
| Lifecycle policy | fixed `policy:construction_maintenance_state_expiry@1` |
| Open events | the existing committed `gameplay.construction_production.maintenance_state_applied` source event, followed by new owner-local `gameplay.construction_production.maintenance_state_obligation_opened` |
| Due events | new owner-local `gameplay.construction_production.maintenance_state_expired` plus `gameplay.construction_production.maintenance_state_obligation_settled` in one append batch |
| Privacy | project scope only |
| Projection | existing `ConstructionProductionProjector`, extended only to reconstruct the active maintenance state and its obligation identity from this stream |
| Settlement | existing caller-driven `ObligationSettlementCoordinator` receives a Construction owner fragment and produces one append-derived `SettlementReceipt`; the registered policy requires both `maintenance_state_expired` and `maintenance_state_obligation_settled` in the same atomic batch; it does not schedule or author the outcome |

The Construction owner opens the obligation only from a committed matching
state-apply source event, pinning its event ID/revision, the obligation ID,
policy ref/revision, due tick, facility stream revision and semantic snapshot
digest through that immutable source event. The due fragment accepts only that
committed open event at the expected stream revision and clears the matching
active maintenance state. A new open for the same state source or an open while
an equivalent obligation remains active is a structured zero-write rejection;
it does not silently replace the obligation.

## Boundary

Formal writes remain:

`semantic proposal -> existing Construction state apply -> committed source
event -> Construction owner obligation-open/expiry fragment ->
GameplayCommandEnvelope / SettlementPlan -> GameplayEventStore.append_batch()
-> scoped outbox -> Construction projection/replay`.

The semantic layer may propose the fixed pair but cannot create an obligation
or write the facility stream. The clock is caller-driven due selection only.
No scheduler, second store, generic policy registration, cross-domain atomic
receipt, retry, cancel, compensation, dispel or transform is admitted by this
package.

## Required Evidence

Focused tests must first fail for the absent lifecycle, then prove:

1. successful state/open append and due/expired-settled append;
2. duplicate replay and changed-idempotency zero write;
3. stale revision, unknown facility, wrong state/effect/policy/privacy and
   direct non-owner fragments are zero write;
4. no duplicate active obligation on re-apply;
5. scoped outbox and full/checkpoint-tail Construction projection equivalence;
6. lifecycle projection and `SettlementReceipt` reflect exactly one
   `append_batch()` result; and
7. unsupported retry/cancel/compensation remain zero write.

The package has its own `infra-construction-maintenance-state-obligation`
Harness profile/report and updates the August analysis, root dependency
design/plan, and INF-1 README. Its 19 independent checks prove the named
append, paired-expiry invariant, direct non-owner rejection, zero-write,
committed-open admission, lifecycle, scoped-outbox, receipt-privacy and
full/checkpoint-tail replay boundaries; they do not upgrade INF-1 to generic
lifecycle closure.
