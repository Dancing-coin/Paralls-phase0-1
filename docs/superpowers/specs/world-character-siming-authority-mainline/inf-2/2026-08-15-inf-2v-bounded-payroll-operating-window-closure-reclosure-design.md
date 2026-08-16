# INF-2V Bounded Payroll And Operating-Window Closure Re-closure

Status: `implemented bounded and independently verified 2026-08-16; broader INF-2 remains incomplete`

## Purpose

INF-2V re-closes the existing INF-2P payroll/operating-window seam against the
current owner contract. It proves one bounded vertical only:

`Organization schedule + verified completed evidence -> Economy wage obligation -> explicit window close/due -> paid or overdue`

The package preserves the existing owners:

- `OrganizationAuthority` remains the sole direct writer for
  `gameplay:organization:window:{window_ref}` open/close/due facts and the
  verified completed-evidence source boundary.
- `EconomyAuthority` remains the sole owner for wage obligation, accrual,
  payment, overdue, and account settlement writes.
- `EconomyAuthority.open_window()`, `.close_window()`, and `.evaluate_due()`
  remain compatibility delegates only.

## Acceptance

Independent focused tests cover:

- verified completed evidence through wage obligation to successful payment;
- insufficient-funds zero-write followed by an explicit overdue fact;
- exact duplicate replay and changed-duplicate rejection;
- stale revision zero-write and privacy-scope rejection;
- full replay versus checkpoint-plus-tail replay;
- append-derived authority receipt with no receipt store or second writer.

All canonical writes remain:

`GameplayCommandEnvelope -> SettlementPlan/owner fragment -> GameplayEventStore.append_batch() -> outbox/replay/scoped projection`

## Non-goals

This is intentionally bounded. It does not add a scheduler, simulation clock,
payroll service, generic policy registry, new obligation store, coordinator
writer, arbitrary cross-domain settlement, or generalized payroll semantics.
