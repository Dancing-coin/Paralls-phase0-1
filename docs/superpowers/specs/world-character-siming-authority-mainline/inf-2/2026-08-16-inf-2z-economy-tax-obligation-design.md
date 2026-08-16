# INF-2Z Economy Tax Obligation

Status: `implemented and independently verified as one fixed Economy owner row; broader INF-2 remains incomplete`

## Purpose

The existing `EconomyAuthorityService` already owns canonical
`gameplay.economy.tax_due_recorded` facts and their `EconomyProjector` view.
INF-2Z turns that existing fact into one owner-local, event-derived tax
obligation lifecycle on the same `gameplay:economy` stream.

## Contract

| Field | Fixed value |
| --- | --- |
| owner | existing `EconomyAuthorityService` / `actor_gameplay.economy_domain` |
| stream | existing `gameplay:economy` |
| open | `gameplay.economy.tax_obligation_opened` from a committed tax-due fact |
| terminal | `tax_obligation_settled`, `tax_obligation_cancelled`, `tax_obligation_expired` |
| policy | `policy:economy_tax_due@1` |
| projection | existing `EconomyProjector`, extended only to the documented tax lifecycle |
| receipt | derived solely from the owner `GameplayEventStore.append_batch()` result |
| privacy | authority-only accounting payload; no tax amount/evidence in project outbox |

The owner accepts a typed command that pins the existing tax-due event, its
stream revision, and due tick. It validates the source before a single formal
`GameplayCommandEnvelope -> SettlementPlan -> append_batch` write. Due
settlement is owner-local: it records only terminal obligation state, not a
payment/account debit. A separate owner contract is required before any tax
payment or cross-domain collection is allowed.

## Non-goals

This does not create caller-open policy registration, a generic tax system,
payment truth, a scheduler, a cross-domain coordinator writer, or arbitrary
settlement. It is one existing Economy owner row.
