# INF-2Y Exact Lifecycle Owner-Contract Catalog

Status: `implemented and independently verified; broader INF-2 remains incomplete`

## Purpose

The existing lifecycle registry already names closed owner-local policies, but
the governed catalog compresses them into one synthetic `inf:state-lifecycle@1`
row. INF-2Y replaces that placeholder with source-controlled exact contracts
and requires the affected existing authorities to check their own contract
before their existing formal append path.

## Closed Contract Rows

| Contract | Sole existing owner | Stream | Lifecycle family | Scope |
| --- | --- | --- | --- | --- |
| `inf:survival-state-expiry@1` | `actor_gameplay.survival_domain` | `gameplay:survival:{actor_ref}` | existing survival state/obligation lifecycle events | project |
| `inf:construction-maintenance-state-expiry@1` | `actor_gameplay.construction_production_domain` | `gameplay:construction_production:{facility_ref}` | existing maintenance apply/open/expired/settled/dispel/cancel events | project |
| `inf:ecology-frost-state-expiry@1` | `authority:ecology` | `gameplay:ecology:{region_ref}` | existing crop-state open/expired/settled/cancel events | project |
| `inf:ecology-drought-state-expiry@1` | `authority:ecology` | `gameplay:ecology:{region_ref}` | existing drought apply/open/expired/settled events | project |
| `inf:economy-wage-accrual-obligation@1` | `actor_gameplay.econ1_economy_domain` | `gameplay:economy:wage:{worker_ref}` | existing wage open/accrual/retry/cancel/expired/settled/compensation events | project |

Each row derives its permitted event family from the existing closed lifecycle
registration. It retains the existing append-derived receipt and existing
owner-local replay reader; it introduces no registry write surface.

## Admission

Immediately before an affected owner constructs its formal
`GameplayCommandEnvelope` / owner fragment / `SettlementPlan` batch, it calls
`GovernedAuthorityContractCatalog.require_operation()` using its fixed row,
owner, stream, event types, and project scope. A catalog mismatch rejects
before `GameplayEventStore.append_batch()` and leaves the store unchanged.

The catalog is read-only. It cannot add a policy, choose a settlement owner,
append, advance a clock, create a receipt, or widen a policy event family.

## Evidence Requirements

Focused tests prove exact rows, removal of the synthetic row, successful
owner-local append, catalog-mismatch zero-write for Survival and a second
non-Survival owner, idempotency, revision conflict, privacy, and replay. The
package has a dedicated Harness profile with one assertion per capability,
including full and checkpoint-tail replay evidence.

## Non-goals

This does not open caller policy registration, generic activation-obligation
binding, arbitrary cross-domain atomic settlement, a scheduler, a second
receipt/store/runtime, or a generic effect/state matrix.
