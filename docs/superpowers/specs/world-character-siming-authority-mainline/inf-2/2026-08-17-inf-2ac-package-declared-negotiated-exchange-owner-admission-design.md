# INF-2AC Package-Declared Negotiated Exchange Owner-Admission Contract

Status: `approved and implemented narrow vertical; authority-only verification required for every package revision`

## Decision And Scope

This contract proposes exactly one bounded capability:

```text
economic_outcome_id = package_declared_negotiated_exchange@1
```

It settles one unit of one immutable gameplay-package-declared item, abstract
right, or typed completed service. It is a need-driven resolution outcome, not
a payment API: a need or dossier can create only a typed proposal, and the same
need can instead resolve by production, consumption, aid, fixed purchase, gift,
debt, or a non-paid service. No need, agreement, or proposal is an economic
fact.

No new truth owner is proposed. Inventory owns item custody, Ownership owns an
abstract right, Contract owns registered service completion, and Economy owns
the two account movements and the exchange settlement event. Each immutable
package outcome chooses exactly one source-evidence mode; the caller chooses
none of the owners, streams, event families, revisions, privacy, receipt,
compensation, currency, or fragments.

This contract was explicitly approved on 2026-08-17. Its one fixed typed
intent, immutable catalog row, owner-local source fragments, and Economy
atomic append path are implemented. It admits no adjacent outcome family.

## Package Admission And Typed Proposal

The active `GameplayPatchManifest` revision is the only content-admission
source. The future implementation must pin `patch_revision_id`,
`content_digest`, registry revision, and active patch-set revision. It must not
create a runtime-writable package registry.

One admitted outcome definition has this closed shape:

```text
economic_outcome_id = package_declared_negotiated_exchange@1
tradeable_ref OR typed_service_ref (exactly one)
source_evidence_mode (exactly one fixed mode below)
source_owner_ref and source_evidence_kind (fixed by package revision)
currency_ref (one canonical allowed currency for v1)
price_policy_revision (fixed amount OR inclusive bounded amount)
eligibility_refs (zero or more fixed capability refs)
consent_rule_ref
privacy_policy_ref = authority_only
compensation_policy_ref = none
source_selection_rule_ref = exchange:unique-owned-source@1
```

This v1 capability admits a definition only when exactly one canonical
`currency_ref` is selected by its immutable price-policy revision. A bounded
policy permits the agreed amount only inside its inclusive immutable interval;
a fixed policy permits only its exact amount. It never chooses a default
currency.

`PackageDeclaredNegotiatedExchangeIntentV1` contains only the authenticated
requesting party, one package outcome reference, one proposal digest, the two
party consent attestations required by the fixed consent rule, and an
idempotency token. For a bounded policy it also carries the proposed amount. It
does not carry an item instance, account, currency, owner, source event type,
stream, scope, revision, receipt, compensation rule, or fragment. Provider and
receiver come from the authenticated attestations; the item/right/service comes
from the package definition and committed source evidence.

Agent agreement is a verifiable input only. It admits no ledger, custody,
right, service-completion, or transaction fact without the checks below.

`exchange:unique-owned-source@1` is a fixed owner-side admission rule, not a
caller selector. For the authenticated provider it requires exactly one
available package-matching inventory item, exactly one active package-matching
right, or exactly one fulfilled package-matching service contract, according to
the package mode. Zero or more than one match rejects before append. It never
uses first item, most recent item, default contract, or caller-supplied source
identity.

## Existing Owner Boundaries

| Fact | Existing owner | Admitted responsibility | Explicit non-ownership |
| --- | --- | --- | --- |
| physical item custody | `InventoryAuthorityService` | one source read and inventory transfer fragment | price, account movement, title, service completion, package policy |
| abstract asset right | `OwnershipAuthorityService` | one source read and right-transfer fragment | custody, price, account movement, service completion, package policy |
| registered typed service completion | `ContractAuthorityService` | one committed completion proof | payment, account movement, item/right mutation, market price |
| debit, credit, transaction | `EconomyAuthorityService` | one ledger fragment and exchange-settled event | custody, right ownership, service completion, price-policy registration |
| package content, need, dossier, agreement, market pricing, generic transfer, compensation | not admitted | none | reject before append |

The package definition selects exactly one of these source-evidence modes. It
may not compose modes, substitute a type, or select another owner at runtime:

| Mode | Fixed committed source proof | Owner-local batch contribution |
| --- | --- | --- |
| `inventory_custody@1` | `actor_gameplay.inventory_domain` projection of an item whose committed provenance event is exactly `gameplay.inventory.item_instantiated`, `gameplay.inventory.output_received`, or `gameplay.inventory.item_transferred_in`; exact item id, `tradeable_ref` definition, container, provenance event id/revision, and current inventory stream head pinned | `gameplay.inventory.item_transferred_out` and `gameplay.inventory.item_transferred_in` only |
| `ownership_right@1` | `actor_gameplay.ownership_domain` projection of a right whose committed provenance is exactly `gameplay.ownership.right_granted` or `gameplay.ownership.right_transferred`; exact right id, declared asset ref, holder, provenance event id/revision, and ownership stream head pinned | `gameplay.ownership.right_transferred` only |
| `completed_service@1` | one `gameplay.contract.service_completion_recorded` immediately followed by `gameplay.contract.record_fulfilled`, both matching the declared service and registered evidence kind; event ids and contract stream head pinned | none: service truth was committed before payment |

The package must declare the matching existing principal and evidence kind.
`inventory_custody@1`, `ownership_right@1`, and `completed_service@1` are the
only admissible values. A physical item cannot use a right/service proof; an
abstract right cannot use an inventory/service proof; a typed service cannot
use an item/right proof. These families and their provenance event sets are
closed, not caller-supplied strings or a generic source-owner registry.

## Eligibility, Accounts, And Revision Pins

Every eligibility ref is a read-only package requirement, never a package
write. V1 may admit only a project-visible active
`CivilizationCapabilityAuthority` view backed by
`gameplay.civilization_capability.activated` for its exact
`(jurisdiction_ref, capability_ref, policy_revision)` and capability revision.
Technology, institution, social, or resource requirements without that exact
committed proof are unavailable content and reject. This preserves the catalog
vocabulary without fabricating unowned social, institution, or resource facts.

Economy derives provider and receiver accounts from each party's committed
`gameplay.economy.account_opened` event. Both account refs, owner refs, currency
refs, opening event ids/revisions, and current Economy head are read-set pins.
The fixed internal binding rule is
`economy:package-declared-negotiated-exchange:party-account@1`; it must select
exactly one open account per authenticated party in the package currency or
reject. There is no first-account, default-account, caller-selected account, or
cross-currency fallback.

The pre-append vector includes: active package/content/registry/active-set
pins; exact price and consent policy; each eligibility event/revision; chosen
source event(s)/head; both account-opened pins and Economy head; every source
stream write head; and the canonical outcome/party/proposal digest. Any stale,
mismatched, private, revoked, or unavailable value is zero-write.

## Fixed Capability, Batch, And Privacy Contract

After approval, the source-controlled catalog row is exactly
`inf:package-declared-negotiated-exchange@1`; the executable surface is only
`EconomyAuthorityService.settle_package_declared_negotiated_exchange`. The
catalog remains immutable/read-only. `SettlementPlan` may compose only the
named Economy fragment and the one selected existing source-owner fragment; it
cannot select a mode, price policy, owner, or event vector.

```text
PackageDeclaredNegotiatedExchangeIntentV1
-> fixed package definition and owner validation
-> one Economy fragment + zero or one fixed source-owner fragment
-> GameplayCommandEnvelope -> SettlementPlan
-> GameplayEventStore.append_batch()
```

The one atomic vector always includes in `gameplay:economy`:

```text
gameplay.economy.account_debited
gameplay.economy.account_credited
gameplay.economy.package_declared_negotiated_exchange_settled@1
```

`inventory_custody@1` additionally contains exactly the two inventory events
above. `ownership_right@1` additionally contains exactly the ownership event.
`completed_service@1` contains no new source event because service completion
is a required prior committed fact. The settlement event identifies immutable
outcome/package/policy pins, fixed currency, source mode, source event ids, and
source revisions. It is invalid without both ledger events; a ledger-only batch
is not an exchange settlement.

All event, outbox, receipt, and projection material is `authority_only`. A
later authenticated participant acknowledgement may be redacted through the
existing scoped-projection boundary only; it reveals no balance, account ref,
source container, private completion evidence, or other-party data. Public,
project, creator-debug, or caller-selected visibility rejects before append.

## Idempotency, Receipt, Replay, And Terminal Rule

The canonical idempotency key is:

```text
package-negotiated-exchange:{package_revision_id}:{economic_outcome_id}:{proposal_digest}:v1
```

Its digest includes parties, immutable package/policy pins, source evidence
pins, account-opening pins, eligibility revisions, amount, consent
attestations, and every expected write head. An exact duplicate returns the
original append result and receipt; a changed duplicate is zero-write.

`PackageDeclaredNegotiatedExchangeReceiptV1` derives only from that one
`append_batch()` result: committed event ids/revisions, transaction id,
outcome/package/policy pins, source mode/evidence pins, and an authority-only
projection digest. It is not a combined receipt service.

`EconomyAuthorityService.package_declared_negotiated_exchange_projection` and
the selected source projector must reconstruct the same authority-only receipt
inputs from full replay. Checkpoint-plus-tail replay over the same events must
reconstruct the same mode, terminal status, ids/revisions, and digest. Historical
account, inventory, ownership, or contract events are never reinterpreted as
package facts.

Settlement is terminal. No retry after success, reversal, refund,
compensation, reopen, chargeback, source retraction, fanout, debt conversion,
or price correction is admitted. A dispute is authority-only audit state until
a separately approved owner-local correction contract names a new vector and
its own receipt/replay semantics.

## Required Zero-Write Rejections

- unknown, inactive, non-immutable, digest-conflicting, or revision-conflicting
  package/capability;
- outcome other than the exact id, more than one item/right/service, or more
  than one source mode/canonical currency;
- zero or multiple package-matching provider source facts under the fixed
  `exchange:unique-owned-source@1` rule;
- absent, wrong-owner, wrong-kind, private, stale, unavailable, or forged
  source, account-opened, or eligibility proof;
- technology, institution, social, resource, consent, party, price, currency,
  account-owner/status, or balance mismatch;
- caller-selected item instance, service proof, account, currency, owner,
  stream, event family, revision, privacy, receipt, compensation, or fragment;
- source proof unlike the exact package mode, including service proof without
  the completion-plus-fulfilment pair;
- missing ledger event, marker-only settlement, source-only settlement, mixed
  mode, split append, or stale source/Economy write head; and
- changed idempotency duplicate, retry, or compensation request.

## Implementation Evidence

The approved vertical is implemented only through
`GameplayCommandEnvelope -> SettlementPlan/AppendDerivedSettlementRecipe ->
GameplayEventStore.append_batch()`. Focused tests cover all three closed source
modes, zero-write price/source/capability rejection, authority-only receipt and
projection boundaries, exact/changed idempotency, and full/checkpoint-tail
replay. The independent `infra-package-declared-negotiated-exchange` Harness
must remain green before this row is reported verified.

## Approval Gate

The user approved this precise contract before implementation. The plan's RED
tests, independent Harness, immutable catalog row, fixed Economy method, and
owner-local source fragments are therefore permitted only for this exact row.
It admits no
generic payment, transfer, market pricing, treasury, router, registry,
coordinator, runtime, store, bus, clock, or scheduler, and no other INF-2 row.
