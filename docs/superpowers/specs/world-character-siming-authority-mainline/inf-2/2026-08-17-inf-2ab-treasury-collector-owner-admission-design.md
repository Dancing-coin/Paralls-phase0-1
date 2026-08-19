# INF-2AB Treasury Collector Owner-Admission Design

Status: `approved and implemented narrow vertical; focused tests and independent Harness verified`

## Scope

This proposal evaluates one federated owner:
`GovernmentTreasuryCollectorAuthority`. It owns only the canonical
collector-account identity for one government jurisdiction. It does not own
payer balances, Economy ledger truth, tax assessment, tax obligation
lifecycle, payment execution, a generic treasury, or an arbitrary payment
policy.

Three resumed existing-owner audits found no existing authority that publishes
the required collector identity. That result authorizes this row-specific
design under the federated admission decision; it is not an implementation
approval.

## Owned And Non-Owned Facts

| Fact | Proposed owner | Boundary |
| --- | --- | --- |
| canonical `(jurisdiction_ref, currency_ref)` collector account identity | proposed Treasury owner | one account reference and immutable admission revision |
| payer account balance and debit | `EconomyAuthorityService` | remains existing Economy ledger truth |
| collector credit and tax-payment settlement marker | `EconomyAuthorityService` | Economy validates the admitted identity and appends its own fixed ledger vector |
| tax assessment and obligation lifecycle | existing Government/Economy paths | this owner never assesses, opens, settles, cancels, or expires an obligation |
| arbitrary payment, treasury transfer, budget, or policy registration | not admitted | reject before append |

## Proposed Capability

`capability:government-tax-payment@1` accepts one typed
`TaxPaymentIntentV1`. The caller supplies only the obligation reference and
idempotency token; it cannot choose an owner, collector account, stream, event
family, revision, privacy scope, receipt rule, or compensation rule.

Admission requires committed evidence for:

1. existing authority-only `gameplay.economy.tax_obligation_opened`;
2. `gameplay:government_treasury:{jurisdiction_ref}` /
   `gameplay.government_treasury.collector_account_admitted@1`, matching the
   obligation jurisdiction and currency; and
3. existing Economy payer-account eligibility and ledger revision.

The obligation opening is admissible only when its committed payload carries
all of the following source bindings. These are owner-produced facts, never
caller fields or defaults:

| Obligation fact | Canonical source | Required pin |
| --- | --- | --- |
| `jurisdiction_ref`, `currency_ref` | the committed Economy `tax_due_recorded` source, copied into `tax_obligation_opened` only after validating the source's jurisdiction/currency against the fixed tax policy | `source_tax_due_event_id` plus `source_tax_due_stream_revision` on `gameplay:economy` |
| `payer_account_ref`, `payer_account_owner_ref` | a committed Economy-owned `gameplay.economy.tax_obligation_payer_bound@1` event for this exact obligation, whose payload references the canonical `gameplay.economy.account_opened` event; the binding is selected by Economy's explicit payer-account rule, not by first/default account lookup | `payer_binding_event_id`, `payer_binding_stream_revision`, and the referenced `payer_account_opened_event_id`/`payer_account_opened_stream_revision` |

The payer binding must prove `payer_account_owner_ref` is the assessed
organization, the account currency equals the committed obligation
`currency_ref`, and the account was open at the pinned revision. A payment
intent supplies neither an account id nor a selection rule. If either binding
is absent, stale, mismatched, or caller-forged, the operation rejects before
append. This design therefore requires INF-2Z's opening source to retain the
jurisdiction/currency pins and requires the existing Economy owner to publish
the narrow payer-binding event before a tax payment can be admitted; it does
not authorize a default-account fallback.

The proposed Treasury command surface is separately restricted to
collector-account admission. A tax-payment intent cannot invoke it and it can
never append a payment fragment.

## Streams And Event Families

| Owner | Fixed stream and event | Write rule |
| --- | --- | --- |
| proposed Treasury owner | `gameplay:government_treasury:{jurisdiction_ref}` / `collector_account_admitted@1` | establishes collector identity only; no tax-payment write |
| existing Economy owner | `gameplay:economy` / `account_debited`, `account_credited`, `tax_payment_settled@1`, `tax_obligation_settled@1` | one atomic Economy batch debits the pinned payer, credits the pinned collector, records the payment, and settles the obligation; the two markers may not be appended separately |
| existing Economy owner | `gameplay:economy` / inverse account events, `tax_payment_compensated@1`, `tax_obligation_reopened@1` | one atomic compensation batch after the exact committed reversal source; it compensates the original payment and explicitly reopens the obligation |

The future append uses only the existing spine:
`TaxPaymentIntentV1 -> admitted capability -> Economy owner fragment ->
GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`.
No new store, bus, clock, scheduler, generic writer, generic router, or
generic settlement authority is proposed.

## Revision, Privacy, And Idempotency

- exact current `gameplay:economy` head is the Economy write pin;
- treasury admission event/admission revision and tax-obligation opening
  revision are read-set pins; tax payment does not write the treasury stream;
- all collector identity, account amount, receipt, outbox, and projection data
  are `authority_only`; public or project scopes reject before append; and
- idempotency is `tax-payment:{obligation_id}:{payer_account_ref}:v1`: exact
  duplicates replay the one Economy receipt and changed duplicates are
  zero-write.

## Receipt, Replay, And Terminal Semantics

`TaxPaymentReceiptV1` derives solely from one `append_batch()` result. It
contains the Economy event IDs/revision, treasury admission event ID/revision,
obligation ID, both source-binding event IDs/revisions, and an authority-only
projection digest. It is not an aggregate or independent treasury receipt.

`EconomyAuthorityService.tax_payment_projection` and the proposed Treasury
collector identity view must each prove full and checkpoint-tail replay from
the same committed events. Historical Economy events cannot be reinterpreted
as Treasury facts at a checkpoint boundary.

Payment is terminal only after one atomic Economy batch commits all four
payment/obligation events: the payer debit, collector credit,
`tax_payment_settled@1`, and `tax_obligation_settled@1`. A batch containing only
the payment marker or only the obligation marker is invalid. Retry of that
payment is not admitted.

Compensation is a separate fixed Economy operation after an exact committed
reversal source for that payment. Its one batch appends inverse ledger events,
`tax_payment_compensated@1`, and `tax_obligation_reopened@1` together. The
original payment reaches the terminal `compensated` state; the obligation does
not become a terminal `compensated` obligation. It transitions from `settled`
to `open` with a new lifecycle revision and a compensation source reference,
so a later payment can occur only through a newly issued Economy payment-cycle
idempotency key and the same canonical source-binding rules. Compensation may
not silently leave the obligation `settled`, may not create a generic refund,
and may not reopen from any source other than the exact committed reversal.

## Required Zero-Write Rejections

- unknown, public, project-scoped, or version-mismatched capability intent;
- missing/stale obligation opening, collector admission, or Economy head;
- missing/stale jurisdiction/currency source pin or payer-binding/account-opened source pin;
- ineligible payer or jurisdiction/currency mismatch;
- caller-supplied collector account, stream, event type, privacy, fragment, or
  compensation rule;
- caller-supplied payer account, default-account request, or payer selection rule;
- a payment batch that omits either marker or appends `tax_payment_settled@1`
  separately from `tax_obligation_settled@1`;
- changed duplicate payer, amount, obligation, or source revision; and
- compensation without its exact committed terminal/reversal source, or a
  compensation that does not append the explicit reopen marker atomically.

## Implementation Evidence

The row-specific contract was explicitly approved before implementation.
`GovernmentTreasuryCollectorAuthority` publishes only the admitted collector
identity, while `EconomyAuthorityService` owns the payer binding, payment,
compensation, receipt, outbox, and replay vectors. Focused tests and the
independent `infra-economy-government-tax-payment` Harness profile prove the
required success, zero-write, privacy, revision, idempotency, receipt, full
replay, and checkpoint-tail replay cases. This evidence does not admit a
generic Treasury, arbitrary payment, transfer, or settlement authority.
