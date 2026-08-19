# INF-2AB Treasury Collector Owner-Admission Plan

Status: `approved plan completed as one verified narrow vertical`

## Preconditions

1. The federated owner-capability mechanism is approved.
2. The three-audit existing-owner result is retained as blocker evidence.
3. The companion Treasury collector design is approved as this exact row; no
   other INF-2 payment, policy, or Treasury behavior is included.
4. Before any green implementation, INF-2Z's committed tax-obligation opening must expose
   jurisdiction/currency source event and revision pins, and the existing
   Economy owner must expose the explicit canonical payer-binding event and
   account-opened source/revision pins. No default-account resolution is
   permitted.

## Approval-Gated Implementation Sequence

1. Add one `GovernmentTreasuryCollectorAuthority` that publishes only the
   canonical collector-account identity admission fact. It must not debit,
   credit, assess, settle, refund, schedule, or route payments.
2. Extend the fixed Economy tax-obligation source contract so the committed
   opening carries `jurisdiction_ref`/`currency_ref` with the exact tax-due
   source event and stream revision, plus `payer_account_ref` and
   `payer_account_owner_ref` from an explicit Economy-owned
   `tax_obligation_payer_bound@1` fact referencing `account_opened`; pin every
   source event and reject missing or stale bindings. This is not a caller
   account selector or a default-account fallback.
3. Add one typed `TaxPaymentIntentV1` capability surface with fixed fields;
   reject caller-selected owner, account, stream, event, revision, scope,
   fragment, receipt, retry, and compensation choices before append.
4. Extend only the existing `EconomyAuthorityService` with the fixed payer
   debit, admitted collector credit, and tax-obligation terminal fragment.
   Use the existing `GameplayCommandEnvelope -> SettlementPlan ->
   GameplayEventStore.append_batch()` spine.
   The one payment batch must contain payer debit, collector credit,
   `tax_payment_settled@1`, and `tax_obligation_settled@1`; marker-only or
   split-marker appends are invalid.
5. Derive one authority-only append receipt and add scoped full and
   checkpoint-tail replay readers. Compensation, if approved, is one separate
   Economy inverse-ledger operation tied to a committed reversal source. Its
   batch must contain inverse ledger events, `tax_payment_compensated@1`, and
   `tax_obligation_reopened@1`; the original payment ends `compensated` while
   the obligation becomes `open` with a new lifecycle revision. No implicit
   reopen or terminal `compensated` obligation is allowed.
6. Add focused RED-to-green tests and one independent Harness profile covering
   success, caller/capability denial, zero-write rejection, privacy, stale
   tax-due jurisdiction/currency pin, payer-binding/account-opened pin,
   source/target revision, exact and changed duplicate, receipt, full replay,
   checkpoint-tail replay, atomic marker relation, and compensation/reopen
   boundaries.
7. Update the immutable catalog only after the owner and capability are
   implemented and verified. No runtime registration API is permitted.

## Forbidden Scope

- generic Treasury, tax, payment, transfer, policy, or settlement authority;
- caller-supplied collector accounts or owner fragments;
- any new writer, router, registry, coordinator, scheduler, store, bus, or
  second runtime; and
- implementation before explicit approval of this exact revised row design.

## Completion Evidence

The approved sequence completed in order: tax-due/obligation source pins,
Economy-owned payer binding, Treasury collector identity, then the fixed
Economy payment and compensation vectors. `49 passed` focused Economy/catalog
regression tests and the independent `infra-economy-government-tax-payment`
Harness profile provide the current evidence. The next action is to retain the
row boundary and continue only with separately admitted remaining rows.
