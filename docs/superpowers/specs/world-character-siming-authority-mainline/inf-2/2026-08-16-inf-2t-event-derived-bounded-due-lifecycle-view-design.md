# INF-2T Event-Derived Bounded Due Lifecycle View

Status: `implemented and verified; no world write path is added`

Date: `2026-08-16`

## Purpose

The existing closed obligation registrations have event-derived `open`, `retry`
and terminal records, but their shared read model does not yet expose the
canonical `due` lifecycle state at a supplied shared-clock tick. INF-2T adds a
pure, replayable time view over those existing records. It is infrastructure,
not a new scheduler: it neither advances a clock nor commits a result.

## Contract

`ObligationLifecycleView.at_tick(tick, catch_up_limit)` shall:

1. rebuild only from the already admitted event-derived lifecycle records;
2. retain terminal `settled`, `cancelled`, `expired` and `compensated` records;
3. expose eligible `open` or `retry` records as `due`, in stable
   `(due_tick, obligation_id)` order, up to the explicit non-negative
   `catch_up_limit`;
4. leave eligible records beyond that budget in their prior pending status;
5. preserve owner, stream, privacy scope and source revision exactly; and
6. perform no append, outbox write, receipt write or policy registration.

`ObligationLifecycleProjection` shall also support full and checkpoint-tail
reconstruction. A checkpoint contains only the event-derived pending/terminal
records, never a materialized `due` decision. Both full and tail paths apply
the same final `tick` and `catch_up_limit`, so their result must be identical.
`checkpoint_plus_tail_at()` rejects a checkpoint that contains materialized
`due` (or any other non-pending open) record before reading tail events.

Only registrations admitted by `ObligationLifecycleContractRegistry` can enter
the view. An unknown policy, forged event family, invalid tick or invalid
budget is rejected before any world write; because this surface is pure, the
event-store snapshot remains unchanged.

## Ownership And Boundaries

The view is a reader shared by the existing Construction, Survival, Ecology and
Economy lifecycle rows. It never selects an owner or materializes a fragment.
An existing domain authority still decides whether a due record becomes a
domain settlement and must use its own `GameplayCommandEnvelope` or
`SettlementPlan` followed by the one `GameplayEventStore.append_batch()`.

This package does not admit caller-open policy registration, an asynchronous
scheduler, a second clock, generic cross-domain settlement, retry or
compensation for unregistered rows, or a receipt aggregate.

## Completion Evidence

Focused RED/GREEN tests must independently cover cross-owner due derivation,
catch-up limiting, terminal preservation, invalid-input zero-write, full and
checkpoint-tail replay equivalence, and privacy preservation. A dedicated
Harness profile/report and August/formal-plan synchronization are required
before this package can be described as verified. Evidence:
`.harness/verification/infra-event-derived-bounded-due-lifecycle-view-report.json`.
