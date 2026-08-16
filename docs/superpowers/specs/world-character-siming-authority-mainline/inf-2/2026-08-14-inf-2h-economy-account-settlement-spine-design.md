# INF-2H Economy Account Settlement Spine Design

Status: `implemented bounded and verified 2026-08-14`

## Scope

INF-2H repairs the existing account-ledger write path, which is already owned
by `EconomyAuthorityService` (`actor_gameplay.economy_domain`).  It converts
only account opening, same-currency debit/credit transfer, and budget
reservation writes from the legacy raw `_append()` helper to:

```text
EconomyAuthorityService -> GameplayCommandEnvelope -> SettlementPlan
-> GameplayEventStore.append_batch() -> authority-scoped outbox
-> EconomyProjector / EconomyPrivacyQueryService
```

The fixed owner stream is `gameplay:economy`.  The fixed event family is
`gameplay.economy.account_opened`, `account_debited`, `account_credited`, and
`budget_reserved`.  `EconomyProjector` remains the replay reader and account
balances remain projections, never caller-supplied truth.

## Contract

- Only `actor_gameplay.economy_domain` may create the command envelope.
- `transfer()` emits the paired debit/credit events in one `SettlementPlan`
  batch on the one existing economy stream.  It is not a general cross-owner
  settlement API.
- The authority reads the current projection, then rejects an optional stale
  expected economy revision before append.  Invalid accounts, currency
  mismatch, duplicate account/reservation, insufficient funds, and stale
  revision all write zero events and zero outbox entries.
- The idempotency key and complete command payload are digested by the
  envelope/plan adapter.  Duplicate identical commands replay the store result;
  a changed payload with the same key is rejected by the existing event store.
- Events retain `authority_only` visibility.  The scoped outbox contains only
  account identifiers and event types for `authority:economy`; it never exposes
  balances, account owners, transfer amounts, or reservation amounts.
- `SettlementReceipt` is derived only from the one resulting
  `GameplayEventStore.append_batch()` result.  It adds no event, store, or
  coordinator and is available only to the authority scope.

## Non-goals

This package does not merge `EconomyAuthorityService` with the separate
`EconomyAuthority` wage principal, introduce payment policy registration,
create payment obligations, settle a different domain, add a scheduler, or
admit arbitrary cross-domain atomic settlement.  Dynamic quotes and orders
remain outside this package until each receives its own formal contract.

## Required evidence

Focused tests and the independent `infra-economy-account-settlement-spine`
profile must separately assert successful formal transfer/outbox/receipt,
duplicate idempotency, stale revision zero-write, insufficient-funds
zero-write, privacy scope, full and checkpoint-tail replay, and preservation
of the one-store boundary.  The report must not claim generic policy
registration, payment, or cross-domain settlement.

Evidence: `.harness/verification/infra-economy-account-settlement-spine-report.json`;
focused account/economy suites and full `python -m pytest -q` (`3026 passed`)
passed on 2026-08-15.  `git diff --check`, the continuation gate, and
documentation check also passed.  This evidence does not widen the stated
single-owner account ledger scope.
