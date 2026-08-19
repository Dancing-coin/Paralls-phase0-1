# INF-2 Specification Tree

Status: `approved INF-2 narrow verticals verified; INF-2V bounded payroll/operating-window re-closure verified; broader INF-2 remains incomplete`

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
34. [INF-2AC arbitrary payment owner-contract audit](2026-08-17-inf-2ac-arbitrary-payment-owner-contract-audit.md) - terminal existing-owner evidence; the approved candidate remains not implemented.
35. [INF-2AC package-declared negotiated-exchange owner-admission design](2026-08-17-inf-2ac-package-declared-negotiated-exchange-owner-admission-design.md) - approved and implemented narrow immutable-package exchange: existing Inventory/Ownership/Contract facts plus Economy atomic ledger vector; no generic payment, transfer, price, or compensation authority.

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
