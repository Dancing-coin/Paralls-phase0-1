# Equipment Runtime Plan

Status: `drafted-for-spec-review`

## Dependencies

Inventory/container/encumbrance, effective stats, and state-group facade.

## Work

1. Define slot schemas, item compatibility, exclusive/overlay policies, grant
   sources, equip/unequip commands, and staged inventory moves.
2. Implement atomic equip/unequip event batches, reversible grant activation,
   modifier/source explanations, and safe non-empty container policy.
3. Publish typed presentation binding references through the future gameplay
   mirror; presentation attachment never proves equipment truth.
4. Test incompatible slot, bound item, stale revision, grant removal, and
   storage-ring `reject_non_empty` behavior.

## Exit Criteria

Unequipping either succeeds atomically or leaves item location, grants,
modifiers, and presentation references unchanged.
