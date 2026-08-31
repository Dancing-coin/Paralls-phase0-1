# INF-3AB Grain Harvest to Inventory Custody Blocker

Status: `narrow vertical implemented; genericity blocker remains active`

## Candidate

```text
one committed project-visible gameplay.ecology.grain_harvested@1
-> existing InventoryAuthorityService
-> one grain:wheat@1 custody receipt
```

The candidate was product-significant because it made the newly verified
Ecology harvest usable as a real Inventory input. It is now implemented as a
fixed row; this document remains the original blocker trace.

## Historical Blocker

The committed harvest event carries crop, plot/project, region, fixed yield,
and item identity, but no owner-derived Inventory actor, holder, destination
container, or item-definition registration. The source CropRecord owner is a
different generic crop authority value and is not a committed mapping for the
admitted grain crop. Construction plot ownership cannot be assumed to be an
Inventory holder, and no committed plot-to-container fact exists.

Inventory therefore cannot choose its actor-scoped stream or a unique
destination container without caller input or a hard-coded default. Its
existing `record_output_receipt()` API is intentionally caller-shaped and
cannot be relabeled as this row.

## Required Business Facts (Resolved)

1. One committed owner/holder mapping for the exact grain crop or project.
2. One committed, project-visible destination container and its revision fence.
3. Immutable `grain:wheat@1` Inventory definition/schema/content and registration.
4. Fixed item-id derivation, event family, privacy, idempotency, receipt,
   replay, and terminal/replant semantics.

Those fields were resolved as a one-time product decision in INF-3AB:
holder `organization:district-milling-cooperative`, container
`container:district-milling-cooperative:grain-intake`, item `grain:wheat@1`,
quantity `10`, and item id derived from the committed harvest event id. The
implemented row rejects `drought_process_advanced`, fixtures, plot names, and
caller-selected actor/container values.

## Boundary

This blocker does not affect the implemented INF-3 grain-harvest row, INF-2AM
flour purchase, or any generic Inventory/Economy path. No new owner, router,
registry, writer, transfer, payment, or second runtime is admitted.

## Closed-Family Genericity Gate

`harvest_to_custody@1` remains a `bounded_adapter`. The repository currently
has one committed harvest source/content tuple only: `grain:wheat` with
`grain:wheat@1`. The focused test suite previously exercised a synthetic
barley branch by mutating the in-memory wheat event; that is not committed
source evidence and has been removed from the genericity proof. There are no
committed harvest-family manifest files for a second species. The aggregate
family verifier therefore reports a failed two-immutable-manifest/source-pair
gate and excludes this family from `genericity_evidence`.

Promotion requires two real, digest-valid manifests, two corresponding
project-visible Ecology source facts, and proof that the same owner-bound
Inventory adapter settles both without caller-selected coordinates. Until
then, the existing wheat row and its replay/receipt behavior remain unchanged.
