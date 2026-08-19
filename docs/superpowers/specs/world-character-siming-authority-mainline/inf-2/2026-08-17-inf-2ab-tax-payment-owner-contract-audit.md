# INF-2AB Tax Payment Owner-Contract Audit

Status: `existing-owner discovery exhausted; approved owner-admission implemented narrow vertical`

## Candidate

The existing `EconomyAuthorityService` can append account debits and credits
on `gameplay:economy`; INF-2Z supplies a committed authority-only
`tax_due_recorded -> tax_obligation_opened` source. This identifies a future
tax-payment row, but does not admit one.

## Missing Contract

No canonical treasury account or treasury account-owner contract exists. The
current lifecycle intentionally settles only an obligation marker and does not
debit or credit an account. Choosing an arbitrary account ID or inventing a
`government:treasury` owner would create financial truth outside an existing
authority contract.

| Required field | Current evidence | Result |
| --- | --- | --- |
| payment owner | `EconomyAuthorityService` exists | available |
| source | committed `gameplay.economy.tax_obligation_opened` | available |
| payer account | Economy projection can validate it | available only after its existing owner supplies it |
| collector account and owner | no canonical treasury/account-holder admission | missing |
| stream/event family | Economy account events exist, no tax-payment marker contract | missing |
| privacy/revision/idempotency/receipt/replay | depends on collector contract | blocked |

The revised design records three additional non-optional gates that remain
unimplemented: (a) the obligation must carry committed jurisdiction/currency
from `tax_due_recorded` with its Economy stream revision; (b) Economy must
publish an explicit `tax_obligation_payer_bound@1` source referencing the
canonical `account_opened` event, owner, and both revisions, with no default
account selection; and (c) `tax_payment_settled@1` and
`tax_obligation_settled@1` must be in the same atomic append, while
compensation must atomically emit inverse ledger events,
`tax_payment_compensated@1`, and `tax_obligation_reopened@1`.

## Federated Admission Transition

The approved federated owner-capability mechanism changes this row's next
artifact, not its implementation state. Three resumed audits are durable
evidence that no legitimate existing collector owner exists. The proposed
row-specific [Treasury collector design](2026-08-17-inf-2ab-treasury-collector-owner-admission-design.md)
may now seek separate approval. It does not create an owner, capability,
event, plan, test, or Harness profile.

## Decision

The approved contract is now implemented through one bounded Treasury identity
owner and the existing Economy payment owner. The focused suite, independent
Harness profile, privacy/revision/idempotency/receipt evidence, and
full/checkpoint-tail replay prove this exact row. This audit still does not
claim generic payment, caller-open registration, arbitrary Treasury behavior,
or arbitrary cross-domain settlement.

## Row Approval Condition

A separately approved revised owner-admission contract must publish one exact
treasury account contract containing:

1. canonical collector account reference and account-holder owner;
2. permitted `gameplay:economy` tax-payment event family and authority-only
   projection/outbox scope;
3. payer-account ownership and revision pin rules;
4. payment/compensation outcome, idempotency key shape, receipt/replay reader,
   source pins for jurisdiction/currency and the canonical payer account, and
   the atomic settled/compensated/reopened state transitions.

Only then may an Economy owner fragment produce one
`GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`
batch.
