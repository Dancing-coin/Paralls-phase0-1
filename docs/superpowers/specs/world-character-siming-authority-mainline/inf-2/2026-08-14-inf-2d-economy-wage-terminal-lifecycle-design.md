# INF-2D Economy Wage Terminal Lifecycle Design

Status: `implemented and verified for one Economy wage row; generic lifecycle remains incomplete`

Date: `2026-08-14`

## Scope

INF-2D completes the event-derived lifecycle only for the existing
`policy:economy_wage_accrual@1` row. It uses the existing `EconomyAuthority`,
`gameplay:economy:wage:{worker_ref}` stream, `SimulationClock`,
`ObligationSettlementCoordinator`, one `GameplayEventStore`, and one append
batch per accepted operation.

| Transition | Existing owner event | Admission |
| --- | --- | --- |
| open | `gameplay.economy.wage_obligation_opened` | existing INF-2C |
| retry | `gameplay.economy.wage_obligation_retry_scheduled` | `open|due|retry`, bounded policy attempt |
| cancelled | `gameplay.economy.wage_obligation_cancelled` | committed open source, `open|due`, reason |
| expired | `gameplay.economy.wage_obligation_expired` | committed unsettled source, `open|due|retry`, reason |
| settled | `gameplay.economy.wage_accrued`, `gameplay.economy.wage_obligation_settled` | existing INF-2C |
| compensated | `gameplay.economy.wage_accrual_compensated`, `gameplay.economy.wage_obligation_compensated` | settled terminal source and explicit compensation policy |

Each event is Economy-owned. Retry adjusts only the lifecycle due cursor.
Cancellation and expiry do not revoke evidence or pay/accrue a wage.
Compensation reverses only the semantic `wage_accrued` fact in the wage stream;
it cannot debit accounts, recover funds, or imply payment.

## Contract

The coordinator remains an assembler, never an Economy writer. It accepts only
an `EconomyAuthority` fragment matching exact current wage-stream revision and
the registered policy/owner/visibility. `EconomyAuthority` owns the closed
registration method for this one row, so callers cannot reconstruct or widen
the policy contract. The registration explicitly contains the retry and
compensation event names. `SettlementReceipt` is built only from
the one resulting `append_batch()` result; it is not a second receipt store or
cross-domain atomic receipt.

`retry_policy` is closed to integer `attempt`/`max_attempts`, with
`1 <= attempt <= max_attempts`, and must advance no earlier than the current
due tick. `compensation_policy` must be non-empty. Unknown source, stale
revision, terminal cancellation/expiry, missing reason, wrong fragment/policy,
retry overrun and compensation before settlement are zero-write rejects. An
expiry receipt is derived solely from the same `GameplayEventStore.append_batch()`
result that writes the owner event.

All terminal-operation idempotency digests include the complete
`ScheduledObligation` as well as the owner fragment batch. Exact repeats replay;
changed retry, expiry or compensation inputs under an existing key are
zero-write rejects, even when the owner event does not serialize every
obligation field.

## Non-goals

No payroll payment, account transfer, generic work admission, activation
binding, cross-stream atomic settlement, second clock/scheduler/store, or
generic owner matrix is admitted.

## Verification record

The dedicated focused suite/profile passed on `2026-08-14`; evidence is at
`.harness/verification/infra-economy-wage-terminal-lifecycle-report.json`.
Its registration selector is independent from the transition selectors. This
does not create dynamic policy registration or admit another Economy row.
