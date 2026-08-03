# Inventory, Container, And Encumbrance Plan

Status: `minimum-core-implemented; broader-possession-planned`

## Dependencies

Event/projection spine, state-group facade, and effective-stat explanation.

## Work

The first backend-only authority slice is implemented and verified by
`gameplay-inventory`: definitions, container creation, one active item
location, sealed/capacity rejection, and atomic move. The following work items
remain the expansion plan.

1. Define item instances, stack policy, location references, container identity,
   capacities, access policy, binding, and type/tag restrictions.
2. Implement authoritative transfer commands with read sets, idempotency,
   expected revisions, and no-loss rejection behavior.
3. Implement carried-weight propagation and explanation, including the
   `none_to_wearer` storage-ring policy while retaining volume/slot checks.
4. Expose filtered inventory/encumbrance snapshots without granting Godot or
   character cognition direct domain writes.

## Embodied Custody Continuation

The first narrow bridge is now planned as a two-way backend authority pair:

1. `stow_from_custody` commits verified custody into a policy-resolved actor
   container. It may release a source occupancy projection only when that
   source is backend-tracked.
2. `retrieve_to_custody` must validate event-derived item location, source
   custody, unsealed access, and an empty backend-registered receiver before
   atomically committing custody, inventory transfer-out, receiver occupancy,
   and retrieve evidence.
3. Both commands replay an identical idempotency key before mutable state
   checks and refresh local custody/occupancy projections only after commit.

This is not authorization for a default-scene retrieve interaction, a
client-selected container/receiver, inventory UI, ownership transfer, generic
world placement, or Godot inventory mirror delivery. Those require a reviewed
policy binding and separate transport/presentation evidence.

## Exit Criteria

An item retains identity across backpack, hand, equipment staging, world, and
storage-ring locations. Invalid moves append no events and alter no projection.

## Evidence

Focused inventory replay tests; `gameplay-possession-equipment` becomes green
only when equipment's dependent cases are also complete.
