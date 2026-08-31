# INF-4U Municipal Drought Assessment Certificate Owner-Admission Contract

Status: `implemented and verified narrow vertical; generic certificate/title paths remain fenced`

## Product Fact

```text
committed INF-3S municipal assessment contract
 + exact committed service completion and fulfilled record
-> existing OwnershipAuthorityService
-> one authority-only municipal assessment certificate initial title
```

The result is only an Ownership-owned certificate title initially held by `organization:district-works`. It does not establish a Government inspection result, permit, weather effect, maintenance result, social reputation, population fact, payment, material, inventory, service completion, or generic certificate system. Existing generic title transfer is not admitted by this row.

## Matrix Preflight

Disposition: `new`. The source is the distinct fixed INF-3S contract/completion vector; the target fact is a new asset/right pair on the existing Ownership owner. It does not collide with land-title, fixed-offer, gift, debt, package exchange, wage or inspection outcomes. Privacy is authority-only; the row has its own idempotency key, receipt and Ownership replay reader.

## Fixed Boundary

| Field | Rule |
| --- | --- |
| capability/outcome | `capability:municipal-drought-assessment-certificate@1` / `outcome:municipal-drought-assessment-certificate@1` |
| source | exact INF-3S advisory-derived contract id; `simple_service`, fixed terms `service:municipal-drought-assessment@1`, fixed evidence kind `evidence:municipal-drought-assessment@1`, completed then fulfilled contract events, contract stream revision/head pinned |
| target owner | existing `OwnershipAuthorityService` |
| target stream/event | `gameplay:ownership`; exactly one `gameplay.ownership.right_granted@1` |
| deterministic asset/right | `asset:municipal-drought-assessment-certificate:{contract_id}` / `right:municipal-drought-assessment-certificate:{contract_id}` |
| holder | fixed `organization:district-works`; caller cannot choose holder, asset, right, owner, stream, event, privacy or receipt |
| privacy | authority-only |
| idempotency | authority-derived `ownership:municipal-drought-assessment-certificate:{contract_id}:{contract_revision}:{ownership_revision}:v1` |
| receipt/replay | append-derived receipt; Ownership full and checkpoint-tail replay |
| lifecycle | one terminal initial grant; no retry-as-new, reversal, compensation, fanout or title transfer in this row |

## Zero-Write

Unknown/private/non-INF-3S advisory; missing, non-service, wrong terms, wrong evidence, incomplete, unfulfilled or stale contract; source/target revision conflict; certificate/right collision; invalid/changed idempotency; catalog mismatch; duplicate; or privacy conflict reject before append.

The existing generic `grant_initial_title()` helper rejects the fixed municipal
certificate asset/right prefixes before append. It remains available for other
Ownership titles, but cannot reserve INF-4U's deterministic identity.
The generic `transfer_title()` helper rejects the same prefixes, preserving the
fixed district-works holder and v1 terminal/no-transfer rule.
The existing package-exchange Ownership fragment builder rejects the same asset/
right identity before constructing a transfer fragment.

## Implementation Sequence

1. Add RED tests for exact contract proof, fixed title payload, zero-write, idempotency, receipt, full/tail Ownership replay and no transfer method.
2. Add the one immutable catalog row and a row-specific Ownership envelope/plan adapter. Do not alter generic grant or transfer entrypoints.
3. Add independent Harness and synchronize matrix, audit and checkpoint.

## Implementation Closure

The exact fulfilled municipal-assessment Contract now grants the fixed
authority-only Ownership certificate title through the existing append spine.
Focused RED-to-green tests, independent Harness, deterministic identity and
holder checks, zero-write fences, append receipt, and full/checkpoint-tail
Ownership replay pass. This closure applies only to INF-4U; generic title
grant, transfer, promotion, population, and social truth remain outside the
row.
