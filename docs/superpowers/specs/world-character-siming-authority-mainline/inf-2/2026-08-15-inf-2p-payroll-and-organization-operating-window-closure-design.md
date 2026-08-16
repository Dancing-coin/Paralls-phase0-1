# INF-2P Payroll And Organization Operating-Window Closure Design

Status: `implemented bounded and verified 2026-08-15`

## Scope

INF-2P closes one mixed Phase-2 seam by naming one owner per write family and
forcing both families onto the existing single-store append spine:

| Family | Sole owner | Stream | Events | Read projection / receipt |
| --- | --- | --- | --- | --- |
| operating window | `OrganizationAuthority` / `actor_gameplay.organization_domain` | `gameplay:organization:window:{window_ref}` | `gameplay.organization.operating_window_opened`, `operating_window_closed`, `operating_window_due_recorded` | `OrganizationOperatingWindowView`, append result, scoped outbox |
| payroll | `EconomyAuthority` / `actor_gameplay.econ1_economy_domain` | `gameplay:economy:wage:{worker_ref}` and existing `gameplay:economy` account stream | existing `wage_obligation_opened`, `wage_accrued`, `wage_paid`, `wage_overdue`, `account_debited`, `account_credited` | existing wage/account projections and append results |

Every write remains `GameplayCommandEnvelope -> SettlementPlan ->
GameplayEventStore.append_batch()` or an existing owner fragment leading to the
same append result. No second store, scheduler, clock, coordinator, receipt
store or truth owner is admitted.

## Owner contract

- `OrganizationAuthority.record_schedule()` remains the schedule writer and the
  source of the worker-visible `operating_window_ref`.
- `OrganizationAuthority.completed_evidence()` remains the bounded gate for
  verified completed evidence.
- `OrganizationAuthority.open_operating_window()`,
  `.close_operating_window()` and `.record_operating_window_due()` are the only
  writers for `gameplay:organization:window:{window_ref}`.
- `EconomyAuthority.open_window()`, `.close_window()` and `.evaluate_due()`
  survive only as compatibility wrappers that delegate to the Organization
  owner. They must not preserve an Economy principal append on any
  `gameplay:organization:window:*` stream.
- `EconomyAuthority` keeps wage obligation, accrual, payment, overdue and
  account-transfer writes only. It does not regain organization-window truth.

## Admission and rejection

The bounded happy path is:

`record_schedule/schedule_view -> verified completed evidence -> Economy open wage -> explicit Organization close -> Economy paid or overdue`

Independent evidence must prove:

- successful schedule-view plus organization-window owner write
- successful wage-obligation open, wage accrual and paid path
- `accrue_wage` and `mark_overdue` use the formal command-envelope /
  `SettlementPlan` single-stream append path and actor-scoped wage outbox
- `pay_wage` emits one actor-scoped wage outbox entry with the paid terminal
  status plus authority-scoped account outbox entries, and materializes that
  wage terminal from its Economy command envelope through `SettlementPlan`
  before the owner assembles the single atomic account-and-wage batch
- explicit insufficient-funds zero-write before a later overdue fact
- invalid or unverified completed evidence writes zero payroll events
- exact duplicate replay plus changed-key zero-write rejection on the
  Organization window stream, and exact duplicate idempotency replay on the
  existing Economy wage-obligation stream
- open/close/due changed-key reuse with stale expected revisions is rejected by
  the existing append-store `revision_conflict`, not by owner-local early
  terminal checks
- explicit stale revision zero-write on both owner families
- public window-write privacy rejection while actor-scoped schedule reads remain
  bounded
- full replay and checkpoint-tail replay reconstruct the same schedule and
  window projections

## Privacy, revision, replay

- Operating-window writes admit only `project` and `authority_only` visibility.
  `public` write admission is zero-write.
- Schedule rows stay actor-scoped unless the existing schedule policy already
  widens them.
- Wage obligation opening remains project-scoped; wage accrual stays actor
  scoped; account transfers remain on the existing Economy account ledger.
- Stream head revisions are the only canonical write precondition. There is no
  side revision cache.
- Receipts are the existing `AppendBatchResult` values returned by
  `GameplayEventStore.append_batch()`.
- Replay remains the existing event-store plus projection path; INF-2P adds no
  bespoke replay engine.

## Non-goals

No payroll service, no organization/economy mega-coordinator, no arbitrary
policy registration, no generic cross-domain settlement, no business-period
scheduler, no implicit tick wake-up, no new truth owner, and no widening beyond
the exact window and payroll families above.
