# INF-2AA Commerce Delivery Payment Contract

Status: `implemented and independently verified; exact Economy-owned payment and compensation row only`

## Purpose

INF-2AA closes one missing commercial payment outcome without opening caller
policy registration or a general cross-domain settlement writer. It reuses the
existing `EconomyAuthorityService`, `GameplayEventStore`, account ledger,
Inventory delivery evidence, and append-derived receipt.

The command is an intent and never carries an amount, debit account, event
type, target stream, or fragment. Economy derives the buyer debit account and
amount from the already committed buyer budget reservation, derives the seller
from the committed Inventory delivery event, and is the sole authority that
builds the account fragment and appends it.

```text
payment intent/evidence
-> EconomyAuthorityService validates committed Inventory + Economy sources
-> Economy-owned GameplayCommandEnvelope / SettlementPlan + fragment
-> one GameplayEventStore.append_batch()
-> authority-only outbox, replay and scoped payment projection
```

## Exact owner contract

| Fact | Existing owner | Stream | Event family | Scope / reader |
| --- | --- | --- | --- | --- |
| delivery proof | `InventoryAuthorityService` | `gameplay:inventory:{seller_organization_ref}` | `gameplay.inventory.delivery_committed`, then only rejection/cancellation evidence for compensation | project source pin / existing event reader |
| delivery obligation proof | `EconomyAuthorityService` | `gameplay:economy` | `gameplay.economy.delivery_obligation_updated` | project source pin / `EconomyProjector` |
| buyer funding proof | `EconomyAuthorityService` | `gameplay:economy` | existing `gameplay.economy.budget_reserved` | project source pin / `EconomyProjector` |
| payment/compensation truth | `EconomyAuthorityService` | `gameplay:economy` | `account_debited`, `account_credited`, `commerce_delivery_payment_settled`, `commerce_delivery_payment_compensated` | authority-only / `EconomyCommercePaymentProjection` |

The target owner is `actor_gameplay.economy_domain`; the target stream is the
existing single `gameplay:economy` stream. The new terminal markers are Economy
facts only. They do not create a Commerce truth store or a second receipt.

## Admission

Payment accepts one exact `delivery_committed` event only when all conditions
hold before fragment construction:

1. its event id, source stream, source revision, project visibility, and stream
   head match the supplied source pin;
2. an existing project-visible `delivery_obligation_updated` event has the same
   `delivery_ref` and `commitment_ref` with `status=delivered`;
3. the existing project-visible `commerce_obligation_recorded` event supplies
   the same commitment and buyer organization;
4. the supplied budget reservation is named by the committed
   `commerce_obligation_recorded` payload for that same commitment, is in the
   existing Economy projection, belongs to that buyer, and its positive reserved
   amount is the exact transfer amount;
5. the supplied seller account exists, belongs to the seller derived from the
   Inventory event, uses the same currency, and the buyer retains sufficient
   balance;
6. the expected Economy revision is current and no prior payment terminal exists
   for the same delivery event; and
7. a non-empty idempotency key is unique or exactly replays the same immutable
   request digest.

Compensation is not caller-selected reversal. It accepts an existing committed
payment terminal plus one later project-visible Inventory `delivery_rejected` or
`delivery_cancelled` event for the same commitment and seller. It reverses only
the exact accounts and amount recorded by the payment terminal, requires the
seller to retain the funds, and rejects an already compensated payment.

Wrong owner/account/currency/source/status/privacy/revision/duplicate inputs
are zero-write. Failed compensation due to insufficient seller funds is also
zero-write. No retry loop, scheduler, policy registration, reservation release,
or arbitrary payment amount is admitted.

## Receipt, privacy, and replay

Each accepted operation creates exactly one `SettlementReceipt` from the one
`GameplayEventStore.append_batch()` result. The receipt and account events are
authority-only. The scoped projection returns payment refs/status without account
balances outside the authority scope. Full replay and checkpoint-tail replay of
the payment projection must agree.

## Completion evidence

Focused tests and one independent Harness profile must separately prove:

- payment success and exact append-derived receipt;
- forged source, owner/account/currency, privacy, stale revision, and duplicate
  zero-write rejection;
- exact duplicate replay and changed duplicate rejection;
- compensation success and its committed evidence/insufficient-funds fences;
- authority-only projection; and
- full plus checkpoint-tail replay equivalence.

This package remains one exact Economy-owned commerce-payment row. It does not
complete caller-open policies, generic compensation, arbitrary payments, or
cross-domain settlement.
