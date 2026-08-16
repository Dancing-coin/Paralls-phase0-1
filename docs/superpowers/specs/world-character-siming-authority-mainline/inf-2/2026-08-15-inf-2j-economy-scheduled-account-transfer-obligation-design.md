# INF-2J Economy Scheduled Account Transfer Obligation

Status: `implemented and verified as one fixed Economy owner row; not INF-2 closure`

## Purpose

INF-2J extends the existing `EconomyAuthorityService` account ledger with one
fixed, event-derived payment obligation. It fills the concrete payment/account
truth gap without creating a payment runtime, a second scheduler, a new
ledger, or caller-defined policy registration.

## Closed contract

| Field | Value |
| --- | --- |
| policy | `policy:economy_scheduled_account_transfer@1` |
| owner | `actor_gameplay.economy_domain` / `EconomyAuthorityService` |
| stream | `gameplay:economy` |
| opening event | `gameplay.economy.scheduled_transfer_obligation_opened` |
| settlement events | `account_debited`, `account_credited`, `scheduled_transfer_obligation_settled` |
| cancellation event | `scheduled_transfer_obligation_cancelled` |
| expiry event | `scheduled_transfer_obligation_expired` |
| payment projection | existing `EconomyProjector` account balances |
| lifecycle projection | existing `ObligationLifecycleProjection` |
| privacy | authority-only events/outbox and authority-only receipt |

`open_scheduled_account_transfer_obligation()` is an Economy authority method.
It accepts only two already-projected, distinct, same-currency accounts, a
positive amount and a non-negative due tick. It emits a `ScheduledObligation`
identity derived from the owner event; it does not accept a caller-supplied
stream, event family, owner, fragment, policy revision or settlement payload.

At due time, the existing `ObligationSettlementCoordinator` receives the
event-derived obligation and an Economy-built fragment. The fragment rereads
the committed opening event, checks the exact accounts/amount/due identity and
current account funds, then emits debit, credit and terminal settlement rows
in one `GameplayEventStore.append_batch()` result. A failed balance check
returns zero-write and leaves the already-open obligation available for the
existing lifecycle's bounded retry/expiry disposition; it does not invent a
separate payment truth store.

## Admission and non-goals

- Exact duplicate opens replay; changed duplicates, stale revisions, unknown
  source obligations, currency mismatch, privacy-scope misuse and forged
  fragments are zero-write.
- Cancellation and expiry use Economy-built fragments and the same fixed
  lifecycle registration. They never debit or credit an account.
- `SettlementReceipt` remains derived only from the one append result and is
  authority scoped.
- This does not implement caller-open policy registration, arbitrary payment
  policies, cross-domain business settlement, account reservation release,
  branch promotion, a scheduler or a generic coordinator writer.

## Required evidence

Focused tests must separately prove opening, due settlement, cancellation,
expiry, duplicate idempotency, revision conflict, insufficient funds,
authority privacy, full/checkpoint-tail replay and forged fragment zero-write.
The package requires its own Harness profile/report and predecessor account
spine evidence before broad verification.

Evidence: `infra-economy-scheduled-transfer-obligation` records thirteen
independent assertions in
`.harness/verification/infra-economy-scheduled-transfer-obligation-report.json`.
It verifies only this fixed same-stream, same-currency owner lifecycle.
