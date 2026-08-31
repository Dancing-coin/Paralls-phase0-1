# INF-2 Specification Tree

Status: `approved INF-2 narrow verticals verified through INF-2AN; generic and unadmitted INF-2 scope remains incomplete`

INF-2AI is implemented: the exact completed INF-4AG public-workshop activity
consumes the matching INF-2AH fixed reservation as one authority-only
`public_project_budget_consumed@1` marker. It is not debit, release, refund,
transfer, or generic budget settlement.

`INF-2AD` adds one implemented immutable municipal drought-assessment service
content row under the existing Contract/Economy exchange contract. It is not a
generic service-payment capability.

`INF-2AI` is implemented and verified as an exact Economy follow-on from the
completed INF-4AG activity and INF-2AH reservation. It records one fixed,
authority-only consumed marker and does not mutate accounts or open a generic
budget lifecycle.

INF-2AI is also the authority-only prerequisite for the separately scoped
INF-4AJ Organization execution row. INF-4AJ consumes the committed marker but
does not repeat or widen its payment/budget semantics.

INF-2AK is implemented and verified as the exact Economy close follow-on:
the committed INF-2AI consumed marker plus the matching INF-4AJ
`funded_and_executed` project execution yield one authority-only
`public_project_budget_closed@1` terminal marker. It is not account mutation,
release, refund, payment, transfer, or a generic budget lifecycle.

The approved [formal blocker disposition contract](../2026-08-26-august-inf-formal-blocker-disposition-contract.md)
keeps the Goal active. The historical Slot-A `TBD` disposition is superseded
only for the exact INF-2AG public-workshop service exchange below; Slots B/C
and generic payment/transfer/settlement remain blocked or unimplemented.
Existing INF-2 rows are not fallback authorities.

`INF-2AE` is an implemented exact facility commissioning-review exchange:
the v4 immutable package consumes an INF-1AI operational-verification source,
Contract records the fixed service, and Economy settles one authority-only
12-unit exchange. It does not generalize service payment or transfer.

1. [INF-2 time, obligation, and cross-domain settlement design](2026-08-12-inf-2-time-obligation-and-cross-domain-settlement-design.md)
2. [INF-2R multi-domain obligation policy expansion design](2026-08-12-inf-2r-multi-domain-obligation-policy-expansion-design.md)
3. [INF-2X obligation lifecycle and policy registration design](2026-08-12-inf-2x-obligation-lifecycle-and-policy-registration-design.md)
4. [INF-2A Survival generic obligation lifecycle design](2026-08-13-inf-2a-survival-generic-obligation-lifecycle-design.md)
5. [INF-2B activation-released Survival expiry design](2026-08-14-inf-2b-activation-released-survival-expiry-design.md) - verified exact two-receipt owner row
6. [INF-2C Economy wage obligation design](2026-08-14-inf-2c-economy-wage-obligation-design.md) - verified one existing Economy owner row
7. [INF-2D Economy wage terminal lifecycle design](2026-08-14-inf-2d-economy-wage-terminal-lifecycle-design.md) - verified authority-owned closed registration and retry/cancel/expired/settled/compensated states for that one row
8. [INF-2E activation-released dehydration expiry design](2026-08-14-inf-2e-activation-released-dehydration-expiry-design.md) - verified exact second Survival activation row; no generic binding
9. [INF-2F activation-released overheated expiry design](2026-08-14-inf-2f-activation-released-overheated-expiry-design.md) - verified exact third Survival activation row; no generic binding
10. [INF-2G activation-obligation binding contract design](2026-08-14-inf-2g-activation-obligation-binding-contract-design.md) - verified finite reader for four existing rows; no open registration
11. [INF-2H economy account settlement spine design](2026-08-14-inf-2h-economy-account-settlement-spine-design.md) - implemented bounded formalization of the existing account-ledger append path; not generic payment or cross-domain settlement
12. [INF-2I Organization/Economy commerce commitment design](2026-08-14-inf-2i-organization-economy-commerce-commitment-design.md) - implemented bounded existing-owner atomic commitment; not a generic cross-domain writer
13. [INF-2J Economy scheduled account-transfer obligation design](2026-08-15-inf-2j-economy-scheduled-account-transfer-obligation-design.md) - verified fixed Economy payment obligation with open/settled/cancelled/expired lifecycle; not open policy registration or arbitrary settlement
14. [INF-2K Government policy registration design](2026-08-15-inf-2k-government-policy-registration-design.md) - verified one fixed Government-owned commercial inspection policy register/revoke row; not arbitrary policy registration or settlement
15. [INF-2L debt settlement formal spine design](2026-08-15-inf-2l-debt-settlement-formal-spine-design.md) - verified bounded migration of the existing fixed simple-debt authority, including owner-local full/checkpoint-tail replay reader; not arbitrary settlement
16. [INF-2M closed lifecycle registration admission](2026-08-15-inf-2m-closed-lifecycle-registration-admission-design.md) - verified input-admission fence: rejects caller-supplied registration and smuggled events outside existing owner-local families, but does not remove the coordinator append surface
17. [INF-2N activation-released fatigue expiry](2026-08-15-inf-2n-activation-fatigue-expiry-design.md) - verified fourth finite Survival activation row; not generic binding
18. [INF-2O Economy dynamic quote formal spine](2026-08-15-inf-2o-economy-dynamic-quote-formal-spine-design.md) - verified existing Economy quote append spine, revision pin and project privacy boundary; not a consumer admission or generic settlement
19. [INF-2P payroll and organization operating-window closure](2026-08-15-inf-2p-payroll-and-organization-operating-window-closure-design.md) - verified Organization-owned window stream and Economy-owned wage/account writes; not a scheduler or generic payroll settlement
20. [INF-2Q owner-only obligation commit spine](2026-08-15-inf-2q-owner-only-obligation-commit-spine-design.md) - implemented and verified bounded ownership repair. It retires the coordinator append surface and keeps commit ownership in existing authorities; it does not close August INF-2.
21. [INF-2R payroll owner-contract catalog](2026-08-16-inf-2r-payroll-owner-contract-catalog-design.md) - approved owner-bound catalog admission for the existing Organization window and Economy wage-payment rows; not generic settlement.
22. [INF-2S append-derived settlement receipt factory](2026-08-16-inf-2s-append-derived-settlement-receipt-factory-design.md) - verified pure receipt derivation for the admitted readers; not a receipt store or settlement writer.
23. [INF-2T event-derived bounded due lifecycle view](2026-08-16-inf-2t-event-derived-bounded-due-lifecycle-view-design.md) - verified shared read-only `open/retry -> due -> terminal` time view with bounded catch-up and checkpoint-tail reconstruction for the closed registrations; not a scheduler, policy registry, or writer.
24. [INF-2U Economy policy-instance registration](2026-08-16-inf-2u-economy-policy-instance-registration-design.md) - verified existing-Economy-owner expansion for one scheduled-transfer policy kind with 27 focused acceptance tests plus a dedicated harness profile; no broad policy registry is claimed.
25. [INF-2V bounded payroll and operating-window closure re-closure](2026-08-15-inf-2v-bounded-payroll-operating-window-closure-reclosure-design.md) - independently verified re-closure of the existing owner split with committed-evidence paid/overdue paths and append-derived receipt proof; no scheduler or generic payroll settlement.
26. [INF-2W event-derived obligation materialization](2026-08-16-inf-2w-event-derived-obligation-materialization-design.md) - verified read-only conversion of registered lifecycle records into `ScheduledObligation` inputs for existing owners; no policy registration or settlement writer.
27. [INF-2Y exact lifecycle owner-contract catalog](2026-08-16-inf-2y-exact-lifecycle-owner-contract-catalog-design.md) - verified replacement of the synthetic lifecycle catalog row with five exact existing-owner rows and their pre-append admission gates; not generic lifecycle registration or settlement.
28. [INF-2Z Economy tax obligation](2026-08-16-inf-2z-economy-tax-obligation-design.md) - verified one existing Economy owner-local tax obligation row derived from committed `tax_due_recorded`; terminal settlement/cancel/expiry never mutates accounts and does not admit payment or cross-domain collection.
29. [INF-2C2 reusable lifecycle contract](2026-08-16-inf-2c2-reusable-lifecycle-contract-design.md) - implemented shared closed terminal-operation lookup and explicit canonical registry factory across existing Survival/Economy lifecycle readers; no open policy registration or generic settlement.
30. [INF-2C3 append-derived settlement recipe](2026-08-16-inf-2c3-append-derived-settlement-recipe-design.md) - implemented pure owner-fragment batch/receipt recipe and routed obligation planning through it; no writer or arbitrary settlement.
31. [INF-2AA Commerce delivery payment](2026-08-16-inf-2aa-commerce-delivery-payment-design.md) - independently verified one exact Economy-owned payment and compensation outcome from committed Inventory delivery, Economy obligation, and commitment-bound budget reservation evidence; not arbitrary payment, generic compensation, or cross-domain settlement.
32. [INF-2AB tax payment owner-contract audit](2026-08-17-inf-2ab-tax-payment-owner-contract-audit.md) - existing-owner discovery is terminal evidence; the approved bounded Treasury/Economy tax-payment vertical is implemented and verified, while INF-2Z's broader account-neutral path remains unchanged.
33. [INF-2AB Treasury collector owner-admission design](2026-08-17-inf-2ab-treasury-collector-owner-admission-design.md) - implemented and independently verified: Treasury owns collector identity only; Economy retains all ledger/payment truth with committed jurisdiction/currency and canonical payer-binding pins.
34. [INF-2AC arbitrary payment owner-contract audit](2026-08-17-inf-2ac-arbitrary-payment-owner-contract-audit.md) - terminal evidence for generic arbitrary payment; the separately approved package-declared negotiated-exchange row is implemented narrowly.
35. [INF-2AC package-declared negotiated-exchange owner-admission design](2026-08-17-inf-2ac-package-declared-negotiated-exchange-owner-admission-design.md) - approved and implemented narrow immutable-package exchange: existing Inventory/Ownership/Contract facts plus Economy atomic ledger vector; no generic payment, transfer, price, or compensation authority.
36. [INF-2AG public-workshop service exchange](2026-08-27-inf-2ag-public-workshop-service-exchange-owner-admission-design.md) - implemented exact INF-1AJ public-use source -> Contract service -> fixed v5 Economy exchange; generic service/payment remains blocked.
37. [INF-2AH public-project budget reservation](2026-08-27-inf-2ah-public-project-budget-reservation-owner-admission-design.md) - implemented exact INF-2AF commitment -> one owner-derived local-account reservation; generic budget/payment remains blocked.
38. [INF-2AI public-project budget consumption](2026-08-28-inf-2ai-public-project-budget-consumption-owner-admission-design.md) - implemented exact INF-4AG activity + INF-2AH reservation -> one authority-only consumed marker; no account mutation or generic budget settlement.
39. [INF-2AK public-project budget close](2026-08-28-inf-2ak-public-project-budget-close-owner-admission-design.md) - implemented exact INF-2AI consumed marker + INF-4AJ funded execution -> one authority-only terminal close marker; no release, refund, payment, transfer, or generic lifecycle.
40. [INF-2AM reinforced-mill flour output purchase](2026-08-28-inf-2am-reinforced-mill-flour-output-purchase-owner-admission-design.md) - implemented exact INF-1AM certified flour custody -> fixed v7 Economy purchase; generic output/payment/transfer remains blocked.
41. [INF-2AN grain-intake acceptance](2026-08-29-inf-2an-grain-intake-acceptance-owner-admission-design.md) - implemented exact Organization grain intake -> Economy acceptance marker; no debit/credit/payment/transfer semantics.

Evidence: [focused Harness report](../../../../../.harness/verification/infra-time-obligation-report.json) proves the historical explicit caller-driven clock/coordinator surface and named fragment fixtures only. It does not prove August INF-2 closure or generic activation pending merge. The separately verified released pending rows are `schedule_gated_supply` (`infra-activation-pending-schedule-merge`) and `survival_state_expiry` for `state:cold@1` (`infra-activation-survival-expiry`), `state:dehydrated@1` (`infra-activation-dehydration-expiry`) and `state:overheated@1` (`infra-activation-overheated-expiry`); none creates a generic binding. INF-2R is a narrow named policy; INF-2X separately owns lifecycle/retry/cancel/compensation design.

## 2026-08-16 Owner Audit

The next-owner audit checked whether an existing authority can lawfully open a
new INF-2 implementation package. `ReferenceDataAuthority` has a complete
closed owner contract (`authority:reference_data`,
`gameplay:reference_data:{dataset_ref}`, registered/corrected/revoked event
family, authority-only projection, append-derived receipt and replay), but it
belongs to the already verified INF-4Z-A reference-data admission vertical. It
is therefore not an INF-2 obligation or cross-domain settlement owner and is
not promoted into the INF-2 catalog.

No remaining Government, Commerce, or Economy candidate currently supplies the
missing arbitrary policy outcome, compensation semantics, target stream/revision
vector, and owner receipt required for INF-2 closure. Caller-open policy
registration and arbitrary cross-domain business settlement remain explicit
unsupported-input zero-write boundaries; no new writer or owner is authorized by
this audit.

The [2026-08-20 candidate register](2026-08-20-inf-2-owner-admission-candidate-register.md)
and [plan](../../../plans/world-character-siming-authority-mainline/inf-2/2026-08-20-inf-2-owner-admission-candidate-plan.md)
record three bounded slots. Existing narrow rows are reference evidence only;
no new package-defined economic row is approval-ready until its source owner,
typed outcome, policy, event vector, receipt, replay, and compensation
semantics are explicitly decided. The historical Slot-A `TBD` record is
superseded for INF-2AG only; slots B/C and generic payment/transfer remain
owner-contract blocked.

The [INF-2 Slot A business decision packet](2026-08-21-inf-2-slot-a-business-decision-packet.md)
remains the historical approval surface for any future distinct exchange. It
requires one committed source, one existing target owner, and one exact target
outcome; it creates no default economic semantics or runtime authority.

## INF-2AF Public-Project Budget Commitment

`INF-2AF` is an implemented narrow Economy row. The exact Construction
`project-step:public-project:workshop-bench@1` completion produces one
authority-only `public_project_budget_commitment_recorded` fact with fixed
`12 currency:local` policy metadata. It performs no account debit/credit,
transfer, material, or inventory write. Focused tests and the independent
`inf2af-public-project-budget-commitment` Harness cover source/head/revision,
privacy, idempotency, receipt, no-account-mutation, and full/checkpoint-tail
projection evidence. Generic payment, transfer, budget reservation, and
settlement remain blocked.

## INF-2AG Public Workshop Service Exchange

`INF-2AG` is an implemented narrow cross-owner row. The exact project-visible
Construction `facility_public_use_enabled@1` fact for an `oven` creates and
fulfills one fixed `public-workshop-session` Contract, then the immutable v5
package settles one authority-only 12-unit `currency:local` exchange through
the existing Economy owner. Contract and Economy retain separate receipts,
privacy, idempotency and full/checkpoint-tail replay. No generic service,
payment, transfer, account selection, market pricing, material, inventory,
permit, technology, weather, social or compensation semantics are admitted.

## INF-2AH Public-Project Budget Reservation

`INF-2AH` is an implemented narrow Economy row. It consumes exactly one
authority-only INF-2AF budget commitment and the matching project-visible
Construction acquisition, derives the unique `currency:local` account from the
committed acquisition owner, and records one fixed 12-unit
`budget_reserved@1` event. Missing, multiple, stale, private, mismatched or
insufficient accounts are zero-write. The row keeps authority-only privacy,
owner-derived idempotency, append-derived receipt and full/checkpoint-tail
replay. Generic budget reservation, account selection, payment, transfer,
release and reimbursement remain blocked.

## INF-2AK Public-Project Budget Close

`INF-2AK` is an implemented narrow Economy row. It consumes exactly one
authority-only INF-2AI `public_project_budget_consumed@1` marker and the
matching project-scoped INF-4AJ `funded_and_executed` execution fact, then
records one fixed authority-only `public_project_budget_closed@1` event.
Missing, stale, private, duplicate, or mismatched sources are zero-write.
The row keeps owner-derived idempotency, append-derived receipt, and
full/checkpoint-tail replay. It does not debit or credit any account, release
or refund a reservation, pay or transfer funds, or create a generic budget
lifecycle.

## 2026-08-28 Current Lane Checkpoint

INF-2's named delivery, tax, negotiated-exchange, municipal assessment,
commissioning-review, public-workshop, budget commitment/reservation,
consumption, close, and reinforced-mill flour purchase rows remain implemented
and verified. Generic payment, transfer, settlement, release, refund and
account-selection behavior remain zero-write. Current verification is
`1246 passed` for the keyword-selected INF/INFRA collection and `4004 passed`
for the repository-root suite. Goal remains active; August INF A-D remains not
complete.

## INF-2AL Public Milling Session

`INF-2AL` is an implemented narrow service/economy extension. The exact
project-visible INF-1AL `mill_reinforced` public-use fact creates and fulfills
one fixed milling-session Contract, then the immutable v6 package settles one
8-unit `currency:local` exchange through the existing Economy owner. Contract
and Economy keep separate authority receipts and full/checkpoint-tail replay;
generic service, payment, transfer, market pricing and settlement remain
blocked.

Current verification after INF-2AL is `1240 passed` for the filename-scoped
INF/INFRA collection and `4012 passed` for the repository-root suite. Slot B
and Slot C are closed only for their named service and certified-flour
partitions; generic payment/transfer/settlement remain blocked.

Current ordered disposition: Slot B is closed only for INF-2AL's named public-
milling service. Slot C is now closed only for the exact INF-2AM certified
reinforced-mill flour-output purchase below; generic payment, transfer and
settlement remain blocked.

## 2026-08-28 Slot-C Autonomous Gap Review

The prior Slot-C blocker is resolved narrowly by the approved autonomous row
contract and immutable v7 package below. Generic output, payment, transfer and
settlement paths remain unchanged and are not implied.

## INF-2AM Reinforced-Mill Flour Output Purchase

`INF-2AM` is an implemented narrow vertical. One project-visible INF-1AM
`mill_flour_output_certified@1` fact is admitted by the existing
`InventoryAuthorityService` into one fixed provider-held
`mill_flour_output_received@1` custody fact. The existing
`EconomyAuthorityService` then settles one fixed package v7 exchange for
`10 item:industrial-facilities:flour@1` at `8 currency:local`, deriving the
receiver from the acquisition owner and accounts from the exact-one-account
rule.

Inventory and Economy retain separate owner-local receipts. Inventory custody
is project-scoped; Economy settlement is authority-only. Exact source,
package, binding, provider, receiver, account, price, revision, idempotency
and capacity conflicts reject before append. The purchase is terminal and has
no compensation, reversal, refund, retry-as-new, fanout or combined receipt
semantics. Focused evidence is the
`inf2am-reinforced-mill-flour-output-purchase` Harness profile and its
`test_inf2am_reinforced_mill_flour_output_purchase.py` suite.

The 2026-08-28 verification repair adds two owner-local fences without
changing the row's business meaning: a custody receipt must still be the
provider inventory stream head when Economy plans the transfer, and the
authority replay reader validates the fixed v7 settlement payload and its
certified Inventory provenance before projection. Stale custody and forged
canonical settlement payloads are zero-write or fail-closed replay cases.

No new INF-2 Economy tuple is formed by INF-4AP grain intake. That
project-visible Organization fact has no committed buyer, account, currency,
price, or terminal settlement contract; generic payment, transfer, market
pricing, and settlement remain blocked.
## INF-2AM Reinforced-Mill Flour Output Purchase

`INF-2AM` is implemented and verified as one fixed two-owner vertical. The
INF-1AM Construction certificate creates one project-visible Inventory-owned
flour lot for the fixed provider/container; the existing Economy owner then
settles the immutable v7 package outcome at 8 `currency:local` units to the
committed receiver. Inventory and Economy retain separate receipts and
replay/provenance fences. Generic output, payment, transfer, market pricing,
and settlement remain blocked.

## INF-2AN Grain Intake Acceptance

`INF-2AN` is an implemented narrow Economy marker. The exact project-visible
Organization `grain_intake_recorded@1` fact and its Inventory provenance yield
one authority-only `grain_intake_accepted@1` marker on `gameplay:economy`.
It records acceptance only: no debit, credit, payment, transfer, price,
account selection, material, production, compensation, or generic settlement
semantics are introduced. The owner-derived idempotency key, append-derived
authority receipt, source revision/privacy fences, and full/checkpoint-tail
replay are covered by the independent `inf2an-grain-intake-acceptance`
Harness.

Source validation additionally requires the Organization and Inventory events
to be on their fixed owner streams; a wrong-stream forged source is rejected
before append.
