# INF-2 Slot A Business Decision Packet

Status: `historical Slot-A decision packet; superseded by implemented INF-2AG; Slots B/C remain pending`

The original Slot-A TBD table below is retained as historical audit evidence.
It is superseded only for the exact `INF-2AG public-workshop service exchange`
row, whose package, owner contract, runtime, tests, Harness, receipts and
replay evidence are implemented. It must not be reopened or reused as a
generic payment/service template. The remaining INF-2 Slots B/C still require
their own source, parties/accounts, policy, outcome and package decisions.

## Decision Purpose

INF-2-SLOT-A was originally defined as one new, distinct, package-defined
economic outcome. The existing `package_declared_negotiated_exchange@1` vertical is
reference evidence only. It is neither a reusable exchange authority nor a
default for item, service, price, parties, accounts, privacy, receipt, replay,
or compensation.

Approve the following one source-to-one target tuple before any Owner-Admission
Contract, package authoring, descriptor/catalog admission, RED test, runtime,
or Harness work:

```text
one committed canonical source event or state
-> one existing target truth owner
-> one exact target outcome and event vector
```

All fields below are required. A blank field means the slot remains unformed
and pre-append zero-write.

## Approval Record

| Decision field | Required approved value |
| --- | --- |
| Business outcome name and purpose | `TBD` |
| Source owner and canonical source event/state | `TBD` |
| Source stream, event/state revision, and committed evidence identity | `TBD` |
| Source subject, party, and any item/service binding | `TBD` |
| Existing target truth owner | `TBD` |
| Exact target outcome and canonical target event family/revision | `TBD` |
| Target stream and expected write revision | `TBD` |
| Immutable package identity/version and named item or typed service | `TBD` |
| Currency and fixed or bounded price/amount policy revision | `TBD` |
| Eligibility, consent, and party/account binding | `TBD` |
| Source and target visibility/redaction rules | `TBD` |
| Owner-derived idempotency inputs; exact replay and changed-duplicate rule | `TBD` |
| Append-derived receipt fields and owner-local full/checkpoint-tail replay state | `TBD` |
| Terminal, correction, reversal, and compensation semantics | `TBD` |
| Required package/declaration/policy/descriptor/catalog/active-set pins | `TBD` |

## Non-Negotiable Boundaries

- The selected target owner must already own the proposed truth. This packet
  does not create an Economy, Inventory, Ownership, Contract, Service, or
  generic settlement owner.
- Package content may define its named item/service, eligibility, currency,
  and bounded price policy. It may not choose owner, event coordinates,
  privacy, idempotency, receipt, replay reader, or compensation.
- The eventual authority must derive all source and target coordinates, validate
  committed evidence and revisions before append, and produce an
  `append_batch()`-derived receipt. Caller-selected amount, account, event,
  receipt, or idempotency coordinates remain zero-write.
- There is no default terminal, reversal, refund, or compensation behavior.
  It must be approved for this exact outcome, or the slot remains blocked.
- One approval creates at most one row. It does not authorize INF-2-SLOT-B,
  INF-2-SLOT-C, generic payment/transfer, open policy registration, or
  cross-domain settlement.

## Next Gate After Completion

Once every value is approved, write a row-specific Owner-Admission Contract
that fixes owner-local source verification, target event vector, privacy,
revision fences, idempotency, receipt, replay, and terminal behavior. Only
then may immutable package/declaration/policy authoring and the separate
descriptor/catalog and runtime gates begin.

## Evidence Basis

- [INF-2 candidate register](2026-08-20-inf-2-owner-admission-candidate-register.md)
- [INF-2 remaining rows blocker packet](2026-08-20-inf-2-remaining-rows-blocker-design-packet.md)
- [INF-2 candidate plan](../../../plans/world-character-siming-authority-mainline/inf-2/2026-08-20-inf-2-owner-admission-candidate-plan.md)

## 2026-08-26 Autonomous Evidence Check

Status: `admission-evidence pending; no runtime row formed`.

The current Economy implementation can technically consume the existing
`completed_service@1` source mode, but that capability is not a blank business
outcome. It requires one immutable package-declared `typed_service_ref` and one
committed fulfilled `simple_service` contract whose terms and exact parties
match that service. The August analysis contains only reference fixtures such
as tutoring, fixed-offer purchase, delivery payment, and wage settlement; none
is an approved new service identity, terms/evidence contract, price policy,
party/account policy, or package content row for Slot A.

Reusing any of those fixtures would collide with an implemented source/outcome
partition. Inventing a service name, a policy authority, or a price from the
runtime's generic test surface would violate the owner-operation matrix. The
smallest missing business evidence remains a literal package service declaration
plus its terms/evidence and price/party policy; until it exists, this slot stays
candidate-only and zero-write. This is not a Goal-level blocker and does not
authorize generic service payment.
