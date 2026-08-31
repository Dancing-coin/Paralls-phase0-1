# INF-3 Grain Harvest Custody Source Blocker

Status: `historical blocker superseded by implemented narrow Ecology row; no Inventory or Economy runtime admission added`

## Dependency Direction

`INF-2AM` could only purchase reinforced-mill flour after a real grain input
and owner-derived output custody chain exists. The plausible upstream direction
is deliberately narrow:

```text
one committed project-visible mature grain CropRecord
-> existing EcologyHazardAuthority harvest outcome
-> one existing InventoryAuthorityService grain custody receipt
```

This is not a generic harvest system, crop-to-item converter, resource
regeneration consequence, or Ecology-to-Inventory router.

## Historical Reason No Row Was Formed

The existing committed `CropRecord` provides only `crop_ref`, `region_ref`,
optional `plot_ref`, `health`, `growth_basis_points`, `revision`, and
`owner_ref`. It does not provide crop species, a maturity predicate, fixed
yield/quantity, a holder, a destination Inventory container, harvest-specific
provenance, or a terminal crop lifecycle. Using health or growth as grain
custody would invent material truth. The existing rain recovery row has a
separate fixed health-only meaning and cannot be reinterpreted as harvest
evidence.

## Resolved Contract

The approved narrow replacement is now:

```text
one committed project-visible grain_crop.admitted
  with species=grain:wheat, maturity_status=mature, yield_quantity=10
  and exact plot/project binding
-> one Ecology-owned grain_harvested
  with item_definition=grain:wheat@1
```

The existing `EcologyHazardAuthority` remains the only writer. The row is
project-visible, terminal/no-compensation, replayable, and zero-write for
unknown, private, stale, ambiguous, duplicate, or caller-shaped inputs.
Inventory and Economy remain downstream consumers that are still out of scope
for this row.

## Required Future Contract

The next business packet must define immutable crop/grain definitions, exact
source predicate and revision/privacy fences, yield and terminal/replant
policy, fixed Ecology and Inventory owner vectors, owner-derived holder and
container rules, separate receipts, full/checkpoint-tail replay, and zero-write
for unknown, immature, private/stale, ambiguous, duplicate, or caller-shaped
inputs.

This document remains as the historical blocker record for the pre-admission
state. The blocker was resolved on 2026-08-28 by the exact Ecology-owned
grain admission and harvest vertical; it is no longer the current runtime
status.
