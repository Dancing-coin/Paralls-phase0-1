# INF-2 Remaining Rows Blocker And Design Packet

Status: `current remainder: INF-2AN closes one acceptance-marker partition; Slot C and generic classes remain blocked`

## Scope And Exclusions

This packet reviews only the current INF-2 rows that remain after excluding
the independently implemented and verified narrow verticals:

- INF-2AA: one Inventory-delivery-bound Economy payment and compensation row;
- INF-2AB: one bounded Treasury collector identity plus Economy tax-payment row;
- INF-2AC: one immutable-package negotiated-exchange row.

Those three rows are reference boundaries, not fallback authorities. INF-2AN is
an acceptance-only marker and not a fallback payment authority. Their
owners, event families, streams, privacy, receipts, replay readers,
idempotency keys, package pins, and compensation rules cannot be generalized.
No generic payment, transfer, treasury, router, registry, coordinator,
writer, or unified settlement authority is proposed here.

The review uses the existing INF-2 register, formal audits, completion audit,
remaining-scope matrix, continuation checkpoint, and current Economy,
Government/Treasury, Commerce, Inventory, Ownership, Contract, and Debt owner
contracts. It does not repeat existing-owner discovery.

## Row Disposition Summary

| Remaining row/class | Current status | Existing owner contract? | Committed source evidence? | Row-specific Owner-Admission Contract? |
| --- | --- | --- | --- | --- |
| INF-2-SLOT-A: public-workshop exchange | `closed for INF-2AG; do not reopen` | Existing Contract/Economy owners have the exact INF-2AG row | Committed INF-1AJ public-use source and immutable v5 package | Implemented and verified; remaining new exchanges require separate contracts |
| INF-2-SLOT-B: typed service result | `closed for INF-2AL; do not generalize` | Existing Contract/Economy owners now have the exact public-milling row | INF-1AL public-use -> public-milling Contract completion -> frozen v6 8-unit exchange | Implemented and verified; another service requires its own source/outcome contract |
| INF-2-SLOT-C: Inventory/Ownership economic result | `owner-contract blocked` | Inventory and Ownership owners exist; Economy has fixed payment/exchange owners only | No additional committed Inventory/Ownership source and exact Economy outcome survive the terminal audit | Yes |
| Generic arbitrary payment/transfer | `owner-contract blocked` -> `admission-evidence pending` | Fixed Economy/Treasury/Commerce/Debt rows exist; no canonical arbitrary-payment owner contract | No canonical arbitrary source-to-payment evidence | Yes, but only for one named outcome, never for the generic class |
| Caller-open policy registration / generic cross-domain settlement | `unimplemented` and `owner-contract blocked` | Several closed policy/lifecycle rows exist; no open registration or generic cross-domain settlement owner | No committed source and target vector for arbitrary policy kinds | Yes for each exact named row; generic registration remains zero-write |

## Row INF-2-SLOT-A: New Package-Defined Exchange Direction (Historical, Superseded for INF-2AG)

### Current State

The former `candidate only` entry is historical. INF-2AG now closes one exact
public-workshop package-defined exchange using the existing Contract and
Economy owners. The old table below remains useful only as a record of the
pre-INF-2AG missing fields; it does not authorize another package exchange or
generic service/payment path. Any new Slot-A-shaped row must have a distinct
source, package, parties, policy, and exact outcome.

| Required contract field | Current evidence / missing boundary |
| --- | --- |
| Existing owner contract | `EconomyAuthorityService` owns the exact INF-2AC ledger vector on `gameplay:economy`; Inventory, Ownership, or Contract owners provide only the exact source evidence accepted by that row. No open contract accepts a new exchange direction. |
| Committed source evidence | Missing for a distinct row. A package declaration, proposal, agreement, dossier, or caller assertion is not committed economic truth. A future row must name one existing source owner and one exact committed evidence kind. |
| Owner-owned fact | Missing exact economic outcome: the owner must define the debit/credit or other bounded ledger result and what it means. Package content may define item/service, currency, eligibility, and bounded price policy only; it cannot select accounts, owner, stream, privacy, receipt, or compensation. |
| Event family and stream | Missing. No second package-exchange event family or target stream may be inferred from INF-2AC. Any future Economy target must be explicitly selected and owner-owned. |
| Revision fence | Missing source event ids/revisions, source stream heads, active package/declaration/policy/descriptor/active-set revisions, target Economy head, and any account-opened/account-owner pins. |
| Privacy | Missing row-specific scope. INF-2AC's authority-only projection and rejection of public/project requests cannot be assumed to another row without approval. |
| Receipt and replay | Missing row-specific append-derived receipt fields and owner projection. Full/checkpoint-tail replay must be defined for the exact new outcome; INF-2AC's reader cannot be reused as a generic exchange reader. |
| Idempotency | Missing exact authority-derived key and request/source digest. Caller-selected keys, amounts, accounts, and event coordinates remain zero-write. |
| Terminal/reversal/compensation | Missing business decision. No compensation, refund, retry, reversal, or terminal state may be inferred from INF-2AC's no-compensation boundary. |
| Needs Owner-Admission Contract? | Yes. It must precede package authoring, descriptor/catalog admission, RED tests, or runtime changes. |
| Minimum business approval | One distinct package identity/version; one named item or typed service; source owner and evidence kind; allowed currency; eligibility/consent; fixed or bounded price policy; target Economy outcome/event family; party/account binding; terminal/reversal/compensation semantics; and explicit package/descriptor/catalog pins. |

## Row INF-2-SLOT-B: Typed Service Result

### Current State

Historical blocker, superseded only for INF-2AL. The exact `mill_reinforced`
public-use source, Contract terms/evidence, fixed provider/receiver binding,
immutable v6 package, fixed price and owner-local receipts now form one
implemented row. This does not provide defaults to any other service.

Every other typed service result remains `owner-contract blocked`. The
repository has Contract/Service-owned facts and the INF-2AC completed-service
source mode, but no separate committed service completion evidence and no
exact new Economy result. A service proposal or agreement is not completion
truth.

| Required contract field | Current evidence / missing boundary |
| --- | --- |
| Existing owner contract | Existing Contract/Service owner can own service completion facts; Economy owns only its admitted fixed payment/exchange rows. No owner contract binds a new service result to an Economy event. |
| Committed source evidence | Missing selected `service_completion_recorded`/fulfilment pair, service identity, provider/receiver binding, source privacy, and source stream revision. The INF-2AC completed-service evidence is already consumed by that row and cannot be relabeled. |
| Owner-owned fact | Missing exact service-result meaning and whether any Economy ledger event is warranted. No generic service-to-payment implication exists. |
| Event family and stream | Missing target Economy event family, target stream, write revision, and atomic event vector. Existing Contract events remain source facts, not a new settlement target. |
| Revision fence | Missing source completion event ids/revisions, contract stream head, package/service policy revision, target Economy head, and account ownership/currency pins if a ledger result is selected. |
| Privacy | Missing. Source and target scope must be explicitly named; no public/project/authority scope may be copied from INF-2AC. |
| Receipt and replay | Missing owner append-derived receipt and separate full/checkpoint-tail readers for service-result state. No combined Contract/Economy receipt may be invented. |
| Idempotency | Missing source-bound authority key and changed-duplicate behavior. Caller-supplied payment or transfer keys remain zero-write. |
| Terminal/reversal/compensation | Missing. Service completion, payment settlement, reversal, and compensation are separate business choices; none may be inferred. |
| Needs Owner-Admission Contract? | Yes. The Contract source owner and Economy target owner must each retain their facts and append only their fixed fragments. |
| Minimum business approval | Named service semantic; exact provider/consumer source evidence; target owner and one exact outcome; currency/account/amount policy if economic; event family/stream/revision; privacy; receipt/replay; idempotency; terminal/reversal/compensation; and admission pins. |

## Row INF-2-SLOT-C: Inventory/Ownership Economic Result

### Current State

`owner-contract blocked`. InventoryAuthorityService and
OwnershipAuthorityService exist, and Economy has fixed ledger owners, but the
terminal audit found no additional committed source plus exact Economy outcome
after INF-2AA and INF-2AC. A custody or right transfer is not itself a payment
or generic transfer result.

| Required contract field | Current evidence / missing boundary |
| --- | --- |
| Existing owner contract | Inventory owns item custody; Ownership owns rights; Economy owns only exact admitted ledger outcomes. No single existing contract joins a new Inventory/Ownership source to a new economic result. |
| Committed source evidence | Missing a distinct committed item/right source, provenance event id/revision, holder/container binding, and current source stream head. INF-2AC's accepted source modes are closed row evidence, not a discovery shortcut. |
| Owner-owned fact | Missing exact economic consequence and its account/asset meaning. No inventory transfer, right transfer, account transfer, or price may be generalized. |
| Event family and stream | Missing target owner, event family, target stream, write revision, and whether source and target writes are one bounded owner composition or separate owner commits. |
| Revision fence | Missing source provenance and current Inventory/Ownership heads, package/eligibility/policy revisions, target Economy head, and account-opened/currency pins if applicable. |
| Privacy | Missing source and target scope. Existing authority-only or project-scoped views cannot be widened or combined. |
| Receipt and replay | Missing one owner-derived append receipt and owner-local full/checkpoint-tail projections. A cross-owner aggregate receipt is not available. |
| Idempotency | Missing exact source-bound key, duplicate replay rule, and changed-duplicate rejection. Caller-selected transfer coordinates remain zero-write. |
| Terminal/reversal/compensation | Missing explicit custody/right terminal state and economic reversal/compensation policy. INF-2AA compensation cannot be reused. |
| Needs Owner-Admission Contract? | Yes. It must preserve Inventory/Ownership truth and make Economy's exact result separately owner-bound. |
| Minimum business approval | One named source owner/evidence kind; one exact target economic outcome; asset/account/party binding; currency and amount/price policy; target event family/stream/revision; privacy; receipt/replay; idempotency; terminal/reversal/compensation; and all package/descriptor/catalog pins. |

### 2026-08-28 Source Partition Recheck

The current committed Inventory/Ownership event families were rechecked after
INF-1AL/2AL/4AL/4AM. No new Slot-C source tuple formed:

| Existing committed fact | Existing partition | Why it cannot form INF-2 Slot C |
| --- | --- | --- |
| `inventory.output_received` | P1D production output receipt | Output custody is already Inventory-owned reference truth; no new economic consequence is named. |
| `inventory.delivery_committed` / rejected / cancelled | INF-2AA delivery payment and compensation | The source, parties, account vector and compensation semantics are already closed. |
| inventory/right package-exchange fragments | INF-2AC exact immutable exchange | The unique custody/right source rule and Economy settlement vector are already consumed by their named package outcome. |
| item/right transfer through gift or fixed-offer paths | gift/fixed-offer owner partitions | Transfer intent is not a new Economy fact; assigning price/payment would invent a business outcome. |
| municipal certificate `right_granted` | INF-4U certificate / Government acknowledgment | The right is authority-only administrative evidence and explicitly cannot become transferable or an economic source. |

No remaining source carries a distinct asset/holder/container/provenance tuple
plus an independently named Economy outcome. Slot C therefore remains
`owner-contract blocked`, not implementation-ready. The minimal next business
decision is still one named Inventory or Ownership source partition together
with a fixed Economy outcome, parties/accounts, currency/price, privacy,
idempotency, owner receipt/replay and lifecycle semantics.

#### Production-Output Non-Substitution

The current `ConstructionProductionAuthority.run_finished` payload has only a
recipe/output-item reference. It is not Inventory custody. The existing
`InventoryAuthorityService.record_output_receipt` accepts a caller-supplied
`source_ref`, actor, item id, definition id and container id; it does not
currently bind an output receipt to a specific committed run, active facility,
frozen reinforcement provenance, owner-derived container, or immutable item
definition. The live default Inventory registry also registers only the archive
token fixture, not a district-milled flour definition/container partition.

Therefore a future `mill_reinforced` output-sale row first needs an approved,
row-specific Inventory receipt contract that fixes all of those ownership and
provenance fields. Treating a test recipe's `output_item` or a P1 bakery
fixture as committed Slot-C custody would violate the Inventory truth boundary.

## Durable Generic Arbitrary-Payment/Transfer Blocker

### Current State

`owner-contract blocked`, now `admission-evidence pending`. The generic
arbitrary-payment lane has a documented three-audit exhausted result. The
durable evidence is that fixed Economy, Commerce, Government/Treasury,
Inventory, Ownership, and Debt owners each close only their own rows; none
defines a canonical arbitrary-payment owner, source, event vector, receipt,
replay view, idempotency recipe, or compensation policy.

This disposition does not authorize a fourth discovery. The next artifact may
only be admission evidence for one separately named business outcome and one
existing owner contract. Until such evidence exists, generic payment,
generic transfer, caller-open amount/account selection, and arbitrary
compensation remain pre-append zero-write.

| Required contract field | Current evidence / missing boundary |
| --- | --- |
| Existing owner contract | Fixed Economy payment/transfer, Treasury collector identity, Commerce commitment, and Debt settlement contracts exist only for named rows. There is no generic owner contract. |
| Committed source evidence | No canonical arbitrary-payment source. Existing reservations, tax obligations, delivery evidence, debt events, or negotiated proposals cannot be substituted without a row-specific decision. |
| Owner-owned fact | Missing named business outcome and owner of its economic truth. No new settlement authority may be introduced. |
| Event family and stream | Missing exact event family, target stream, and atomic write vector. Existing `gameplay:economy` events cannot become a generic route. |
| Revision fence | Missing source identity/revisions, target head, package/policy/descriptor/catalog pins, and account ownership/currency pins. |
| Privacy | Missing arbitrary-row scope and redaction rules. Existing authority-only/project scopes are not a generic default. |
| Receipt and replay | Missing canonical append-derived receipt contract and full/checkpoint-tail owner projection. No aggregate receipt or second store is permitted. |
| Idempotency | Missing exact owner-derived key and changed-duplicate semantics. Caller-open keys/amounts/accounts remain zero-write. |
| Terminal/reversal/compensation | Missing canonical terminal and compensation policy. INF-2AA/AB/AC rules are not fallback semantics. |
| Needs Owner-Admission Contract? | Yes for one named outcome only; no contract may be approved for the generic class itself. |
| Minimum business approval | Select one concrete economic outcome, existing owner, committed source evidence, party/account/currency binding, policy/amount bounds, exact event vector, privacy, revision/idempotency, receipt/replay, terminal/compensation, and admission pins. |

## Caller-Open Policy Registration And Generic Cross-Domain Settlement

### Current State

`unimplemented` and `owner-contract blocked`. Existing policy-instance and
lifecycle registrations are finite, immutable, owner-local rows. The existing
planner/recipe surfaces do not authorize caller-open registration or arbitrary
cross-domain business settlement.

| Required contract field | Current evidence / missing boundary |
| --- | --- |
| Existing owner contract | Existing Economy, Government, Commerce, Debt, and lifecycle contracts admit only closed policy kinds and owner-local event families. No open registration owner exists. |
| Committed source evidence | Missing a named committed policy instance/source event and an exact target owner outcome. A caller-supplied policy revision, fragment, or event family is not evidence. |
| Owner-owned fact | Missing the business fact owner and exact target consequence. A planner may compose approved fragments but cannot become a writer or settlement authority. |
| Event family and stream | Missing per-row target event family, stream, write revision, and atomicity boundary. Generic cross-stream batches remain unadmitted. |
| Revision fence | Missing source/target stream heads, policy/declaration/descriptor/catalog revisions, and source binding pins. |
| Privacy | Missing policy/source/target scope. No caller-selected privacy or broad cross-domain projection is permitted. |
| Receipt and replay | Missing owner-derived append receipt and owner-local full/checkpoint-tail replay contract. A unified settlement receipt is prohibited. |
| Idempotency | Missing exact owner-derived key and duplicate/change semantics. Caller-provided arbitrary idempotency coordinates remain zero-write. |
| Terminal/reversal/compensation | Missing named lifecycle and compensation semantics for each policy kind. Existing closed lifecycle rows cannot be generalized. |
| Needs Owner-Admission Contract? | Yes, separately for every named row; no generic registration contract is admissible. |
| Minimum business approval | One named policy kind, business owner, committed source, exact target owner/event vector, stream/revision/privacy, idempotency, append-derived receipt, full/tail replay, terminal/reversal/compensation, and package/descriptor/catalog pins. |

## Cross-Row Admission Rule

No remaining INF-2 row may advance on the basis of a generic payment,
transfer, treasury, or settlement label. The minimal next approval is one
named business outcome with an existing owner and committed source evidence.
Only after that approval may a row-specific Owner-Admission Contract define
the fixed owner-derived coordinates and procedural package/descriptor/catalog
gates. All unknown, multiple, unadmitted, digest-mismatched, missing/private/
stale, binding-conflicting, revision-conflicting, duplicate, and
changed-duplicate inputs remain zero-write before `GameplayEventStore.append_batch()`.

## Integration Recommendation

Use this packet as the current INF-2 blocker/design evidence in the mainline
audit. Keep INF-2AA/AB/AC recorded as completed narrow verticals, keep the
generic arbitrary-payment result in durable `admission-evidence pending`, and
require one fresh business decision plus one row-specific Owner-Admission
Contract before any package, catalog, runtime, test, or Harness work. Do not
open a fourth existing-owner discovery or introduce a generic settlement
authority.
