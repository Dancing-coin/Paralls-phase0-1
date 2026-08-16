# INF-2AB Tax Payment Owner-Contract Audit

Status: `blocked; no implementation or Harness completion claim`

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

## Decision

Do not open RED implementation tests or add an Economy method. The correct
zero-write behavior remains the existing INF-2Z terminal-only tax obligation.
This audit does not claim tax payment, generic payment, caller-open
registration, or arbitrary cross-domain settlement.

## Unblock Condition

An existing owner must publish one exact treasury account contract containing:

1. canonical collector account reference and account-holder owner;
2. permitted `gameplay:economy` tax-payment event family and authority-only
   projection/outbox scope;
3. payer-account ownership and revision pin rules;
4. payment/compensation outcome, idempotency key shape, and receipt/replay
   reader.

Only then may an Economy owner fragment produce one
`GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`
batch.
