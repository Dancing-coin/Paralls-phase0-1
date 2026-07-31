# Inventory, Container, And Encumbrance Plan

Status: `drafted-for-spec-review`

## Dependencies

Event/projection spine, state-group facade, and effective-stat explanation.

## Work

1. Define item instances, stack policy, location references, container identity,
   capacities, access policy, binding, and type/tag restrictions.
2. Implement authoritative transfer commands with read sets, idempotency,
   expected revisions, and no-loss rejection behavior.
3. Implement carried-weight propagation and explanation, including the
   `none_to_wearer` storage-ring policy while retaining volume/slot checks.
4. Expose filtered inventory/encumbrance snapshots without granting Godot or
   character cognition direct domain writes.

## Exit Criteria

An item retains identity across backpack, hand, equipment staging, world, and
storage-ring locations. Invalid moves append no events and alter no projection.

## Evidence

Focused inventory replay tests; `gameplay-possession-equipment` becomes green
only when equipment's dependent cases are also complete.
