# INF-2 Owner-Admission Candidate Register

Status: `INF-2AN latest grain-intake acceptance vertical implemented and verified; remaining candidate slots retain their formal dispositions`

## Shared Contract Requirements

An INF-2 row must name one package-defined economic outcome and one existing
Economy/Inventory/Ownership/Service owner. The package may declare item,
typed service, eligibility, currency and bounded price policy; it may not
choose authority coordinates, privacy, receipt, compensation, settlement
fragment, or a generic payment/transfer route. The owner derives the
idempotency key, appends the exact fixed event vector, and owns full/tail
replay. Every listed unknown/multiple/unadmitted/digest/privacy/stale/binding/
revision/duplicate condition is pre-append zero-write.

## Candidate INF-2-SLOT-A (Historical, Superseded for INF-2AG)

The previously approved `package_declared_negotiated_exchange@1` is an
implemented narrow reference row, not a new business fact. A new candidate
would require a distinct active immutable package revision, named item/service,
source owner/evidence, allowed currency, eligibility, price-policy revision,
Economy target stream/event/revision, actor/party binding, terminal and
compensation semantics, and descriptor/catalog pins. Recommendation: no new
row until those literals exist; generic payment remains zero-write. The
[Slot A business decision packet](2026-08-21-inf-2-slot-a-business-decision-packet.md)
is the required approval surface and intentionally supplies no defaults.

The 2026-08-26 autonomous check confirmed that existing
`completed_service@1` support is only a reusable source mode, not a candidate
fact. No unconsumed package service declaration, exact terms/evidence mapping,
price policy, or party/account policy appeared in the approved August material;
existing tutoring, delivery, wage, and fixed-offer fixtures were all duplicate
reference partitions. Slot A was therefore `admission-evidence pending` and
candidate-only until the exact INF-2AG public-workshop partition was selected
and verified. That partition is closed below; this record remains applicable
only to a future distinct exchange and remains zero-write until its own
literals exist.

## Candidate INF-2-SLOT-B (typed service result; blocked)

No committed service completion evidence, exact Economy event family, or
canonical owner receipt is present in the remaining-scope audit. Missing:
service identity/package revision, source owner/event/revision/privacy,
consumer owner/stream/event/write revision, idempotency, replay, terminal,
reversal/compensation, and all admission pins. Recommendation: approve one
named service outcome and source evidence before drafting a contract.

## Candidate INF-2-SLOT-C (inventory/economic result; blocked)

No additional committed Inventory/Ownership source and exact Economy outcome
survive the terminal existing-owner discovery. The tax-payment and delivery/
negotiated-exchange rows are existing references and cannot be relabeled.
Missing the same complete field set as slot B; recommendation is to preserve
zero-write rather than invent a transfer or settlement authority.

## Candidate INF-2AD (implemented narrow vertical)

The exact frozen `package:municipal-drought-services:v1` content declares one
completed municipal drought-assessment service at fixed `12 currency:local`
minor units. Existing Contract terms own the exact completion evidence, while
existing Economy owns the authority-only debit/credit/settled batch. Its
immutable v2 digests, active package pins, source/party/price/idempotency,
append receipt, full/tail replay, and zero-write evidence are in the
[contract](2026-08-26-inf-2ad-municipal-drought-assessment-service-exchange-design.md)
and `inf2ad-municipal-drought-assessment-exchange` Harness. It does not make
service payment generic or let Government advisory truth trigger payment.

## Candidate INF-2AL (implemented narrow vertical)

The exact INF-1AL project-visible `mill_reinforced` public-use event produces
one fixed Contract service (`service:industrial-facility-public-milling-session@1`)
and one fulfilled completion pair. The existing Economy owner then settles the
distinct immutable v6 package outcome at fixed `8 currency:local` between the
fixed provider `organization:district-milling-cooperative` and the committed
facility acquisition owner. Contract and Economy retain separate owner-local
receipts and full/checkpoint-tail replay. This row is not generic service,
payment, transfer, market pricing, inventory or settlement authority.

Current verification after INF-2AL is `1240 passed` for the filename-scoped
INF/INFRA collection and `4012 passed` for the repository-root suite. Slot B is
closed only for this exact public-milling service; Slot C remains
owner-contract blocked.

## Candidate INF-2AM (implemented narrow vertical)

The exact project-visible INF-1AM flour-output certification is admitted by
the existing Inventory owner into one fixed provider-held
`item:industrial-facilities:flour@1` custody lot, then the existing Economy
owner settles the immutable v7 package outcome for `10` items at `8
currency:local` to the acquisition-derived receiver. Inventory and Economy
retain separate receipts, owner-derived coordinates, source/revision fences,
privacy, idempotency, and full/checkpoint-tail replay. The 2026-08-28 repair
also rejects a stale provider custody stream and fails closed on forged v7
settlement replay. This remains a terminal no-compensation row; generic
output, payment, transfer, market pricing, and settlement remain blocked.

### 2026-08-28 Autonomous Gap Precision

The autonomous upstream-fact review tested the only product-significant
direction that could plausibly unlock Slot C: a fixed completed
`mill_reinforced` production run producing one Inventory-owned flour custody
receipt, followed by one fixed Economy purchase outcome. It did not form a
row. The current `run_finished.output_item` is only a Construction projection
field; it is not committed Inventory custody. The existing Inventory receipt
method accepts caller-supplied source, actor, item, definition, container, and
quantity, so it cannot serve as row-specific provenance.

The minimum missing business facts are explicit: exact committed mill recipe
and immutable flour definition; owner-derived source holder and destination
container; produced quantity; fixed provider/receiver party binding; currency
and fixed or bounded price policy; Economy root event/outcome; and
terminal/reversal/compensation semantics. Test recipes, archive-token custody,
INF-2AA delivery, and INF-2AC package exchange are duplicate or
non-authoritative sources. Slot C remains `owner-contract blocked` and generic
payment/transfer/settlement remains zero-write.
