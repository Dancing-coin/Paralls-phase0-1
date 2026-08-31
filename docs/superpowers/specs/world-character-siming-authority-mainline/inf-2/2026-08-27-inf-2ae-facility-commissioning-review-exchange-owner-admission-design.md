# INF-2AE Facility Commissioning Review Exchange Owner-Admission Contract

Status: `implemented and verified narrow vertical; generic service payment remains blocked`

## Product Loop

```text
committed INF-1AI facility_operationally_verified
-> existing ContractAuthorityService creates and fulfills one fixed
   industrial commissioning-review service contract
-> existing EconomyAuthority settles one immutable package exchange
```

This is a concrete economic loop for a facility that has completed real
production: an existing municipal assessment office performs a fixed
commissioning review for the facility operator. It creates no new owner. It
does not alter Construction facility kind/revision, Production output,
Inventory custody, Ownership title, weather, maintenance, permit, technology,
social, population, tax, treasury, or generic payment/transfer truth.

## Fixed Business Literals

| Field | Value |
| --- | --- |
| package | `package:industrial-facilities`, revision `package:industrial-facilities:v4`, version `4.0.0`, patch `4.0.0`, author `author:repo`, trust `trust:repo` |
| service | `service:industrial-facility-commissioning-review@1`; evidence `evidence:industrial-facility-commissioning-review@1` |
| parties | provider `organization:municipal-assessment-office`; receiver is the committed `facility_acquired.plot.owner_ref` for the verified facility; caller cannot choose either |
| price | fixed `12` minor units of `currency:local`; policy `policy:industrial-facility-commissioning-review-price@1` |
| capability / outcome | existing `capability:package-declared-negotiated-exchange@1`; `outcome:industrial-facility-commissioning-review-settlement@1` |
| source | exact project-visible INF-1AI `gameplay.construction_production.facility_operationally_verified` event plus its committed facility acquisition and completed run source vector |
| Contract owner fact | active -> fulfilled `simple_service` Contract with terms ref equal to the service ref and completion evidence kind equal to the evidence ref |
| Economy owner fact | one fixed package exchange: receiver debit, provider credit, then `package_declared_negotiated_exchange_settled`, all authority-only |
| lifecycle | Contract and Economy settlement are each terminal v1; no refund, reversal, compensation, retry-as-new, fanout, or combined receipt |

## Owner And Replay Boundaries

Contract owns the service Contract creation/completion events on
`gameplay:contracts`; Economy owns debit/credit/settled events on
`gameplay:economy`. Each append has its own receipt. Contract and Economy
projectors must each support full/checkpoint-tail replay. The package declares
only typed service, source eligibility, fixed currency/price and consent; it
cannot choose owner, event family, stream, privacy, receipt, replay or
compensation.

## Source And Eligibility Contract

The row-specific source proof is
`construction:facility-operationally-verified@1`, owned by
`ConstructionProductionAuthority`. It must identify exactly one project-visible
facility verification event, its `facility_ref`, `project_ref`, completed
`run_ref`, run-start/run-finished event ids/revisions, current facility
revision, and the acquisition event whose `plot_ref` and `owner_ref` bind the
receiver organization. The Contract creation method derives receiver party and
all source coordinates from that proof. A missing/ambiguous/private/stale or
owner-mismatched plot binding is zero-write.

The Contract completion method is the exact INF-2AE operation; generic Contract
create/complete/fulfill/terminate methods cannot create or alter its service
terms. Economy uses the existing completed-service source mode and exact
provider/receiver pair; zero or multiple matching accounts is ambiguity, never
a default.

## Package And Admission Pins

The immutable v4 package's declaration digest is derived from its canonical
declaration payload with any author claim excluded, then content digest is
derived from the normalized complete v2 record with only `content_digest`
excluded. Caller-supplied missing, malformed, mismatched or conflicting claims
are zero-write. After digest validation, the existing registry binds the exact
package/declaration/binding/descriptor/active-set pins; no package mutation is
allowed.

## Zero-Write And Isolation

Unknown/inactive/untrusted package; digest mismatch; unknown service/evidence;
wrong or multiple INF-1AI source; wrong facility/project/owner binding;
private/stale/revision-conflicting source; contract duplicate or changed
duplicate; wrong party/consent; missing or multiple currency accounts;
insufficient funds; price mismatch; catalog/descriptor/binding mismatch;
caller-selected owner/stream/event/revision/privacy/receipt; and any payment,
inventory, ownership, material, maintenance, permit, technology, weather,
social, compensation or fanout fragment reject before either owner appends.

## Implementation Closure

The exact v4 package, Contract creation/fulfillment path, and Economy
12-unit settlement are implemented through the existing append spine. Focused
package/Contract/exchange tests, independent Harness, continuation gate,
append-derived receipts, source/privacy/revision/idempotency fences, and full
and checkpoint-tail replay all pass. The original implementation-pending
disposition is historical; no generic service payment, transfer, account
selection, or settlement authority is admitted.

## Conflict-Matrix Preflight

Disposition: `new`. INF-1AI owns only Construction verification. Contract owns
the service agreement, and Economy owns this exact fixed exchange. It does not
reuse municipal drought-assessment terms, the INF-2AC outcome, or the existing
wage/delivery/tax rows. The product value is a real post-commissioning service
loop; the fixed 12-unit amount is a package policy, not a generic market price.
