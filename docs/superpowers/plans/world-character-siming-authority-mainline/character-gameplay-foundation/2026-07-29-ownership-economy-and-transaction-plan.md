# Ownership, Economy, And Transaction Plan

Status: `drafted-for-spec-review`

## Dependencies

Event/projection spine, inventory, and state-group facade. Equipment may
consume purchased items afterwards but is not a prerequisite.

## Work

1. Define account/balance, offer, economic transaction, item title,
   `OwnershipRight`, `DebtClaim`, and `ContractRecord` projections separately.
2. Implement purchase, gift, right transfer, debt creation/payment, and
   contract primitives as atomic cross-domain settlements with pinned revisions.
3. Preserve the item/right boundary: actors are never item instances, and loss
   of a deed/document never changes a legal right.
4. Add rollback/audit/replay tests for insufficient funds, stale revisions,
   unauthorized right transfer, bound item, and duplicate transaction commands.

## Exit Criteria

A purchase changes balance, possession, title/right policy, and audit record in
one batch or changes none of them.

## Evidence

`gameplay-economy-authority` plus predecessor replay and possession profiles.
