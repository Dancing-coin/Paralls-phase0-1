# INF-2C Economy Wage Obligation Design

Status: `implemented and verified for one Economy wage-accrual obligation row; August INF-2 closure remains incomplete`

## Scope

This adds exactly one existing Economy owner lifecycle row. The owner is
`EconomyAuthority` with principal `actor_gameplay.econ1_economy_domain`; the
only stream is `gameplay:economy:wage:{worker_ref}`. The lifecycle is derived
from canonical owner events, not a second obligation store:

| Transition | Event |
| --- | --- |
| open | `gameplay.economy.wage_obligation_opened` |
| settled | `gameplay.economy.wage_accrued` and `gameplay.economy.wage_obligation_settled` |

Opening is an Economy `GameplayCommandEnvelope -> SettlementPlan ->
GameplayEventStore.append_batch()` write. Due selection stays caller-driven in
the one `SimulationClock`. Settlement uses
`ObligationSettlementCoordinator` and an Economy-owned fragment; its receipt
is derived only from that one append batch.

## Verified admission

The row is `policy:economy_wage_accrual@1`. It requires a worker
`character:` ref, non-empty existing work-evidence refs, positive minor-unit
wage amount, policy revision, project visibility, exact wage-stream revision,
and an obligation identity `obligation:economy:wage:{worker_ref}:{accrual_ref}`.
The authority does not pay wages, debit accounts, create a payroll system, or
admit generic work evidence. Those remain outside this row.

## Rejection, privacy, replay

Duplicate equal commands replay through the store; altered duplicate payload,
wrong owner, stale revision, actor/private scope, malformed refs, terminal
settlement and unregistered policy are zero-write rejections. Project outbox
data contains the accrual/worker reference only, while evidence remains in the
canonical event. Full and checkpoint-tail replay must reconstruct the same
registered lifecycle projection.

An active wage obligation identity cannot be reopened with another idempotency
key. The exact original key remains delegated to the existing event-store
idempotency result, so equal input replays and changed input rejects without a
second event.

## Non-goals

No second clock, scheduler, store, receipt store, activation binding,
multi-stream atomic settlement, cancellation/retry/compensation event for the
Economy row, generic obligation matrix, SOC-1, GAME-1, P6, or P7. The existing
Survival row remains the only admitted retry/compensation example.
