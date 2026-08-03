# Ownership, Economy, And Transaction Plan

Status: `partially-implemented; credential-and-simple-debt-foundations-implemented`

## Dependencies

Event/projection spine, inventory, and state-group facade. Equipment may
consume purchased items afterwards but is not a prerequisite.

## Existing Narrow Slice

`embodied_handoff_authority_service` already appends one session-bound
`ownership.right_transferred` event alongside `inventory.custody_changed`.
Treat it only as an interaction-specific producer with its own evidence. It
does not authorize implementation claims for accounts, ledger balances, offers,
generic right transfer, credentials, contracts, debt, privacy views, or an
economy transaction record. Phase 5 begins by extracting those domain facts
into their own projections and authority service without changing the handoff
service's boundary.

Implemented foundations now include event-derived exclusive full-title grant
and independent transfer, same-currency account debit/credit transfer, and one
fixed-offer purchase authority. The purchase pins the published offer revision
and price, validates buyer/seller accounts, seller title, source placement and
buyer capacity, then atomically appends debit, credit, seller transfer-out,
buyer transfer-in, title transfer, offer consumption, and a transaction record.
The zero-consideration gift slice likewise atomically appends donor transfer-out,
recipient transfer-in, title transfer, and a gift transaction record. Both
retain explicit item/right separation. Credential issue/revoke/supersede is
also implemented in its own stream; it is a right reference only and neither
changes title. A read-only presentation validator requires a current item
location in the presenter's inventory plus the current right holder, but does
not write custody or title. Issue/supersede similarly validate the declared
holder's current inventory location, pin that stream revision, and retain both
values as issuance evidence. The attestation never substitutes for the current
inventory or ownership projection. The
implementation deliberately excludes generic right kinds, privacy views,
persistence, checkpoint replay, and Godot delivery.

The first debt foundation is now implemented: `simple_debt` creates an active
contract, a claim with `principal == outstanding`, creditor debit, debtor
credit, and an issue record in one batch. Payment is bounded by the
event-derived outstanding amount; the final payment additionally satisfies the
claim and contract in that same batch. A simple policy cancellation is also a
new claim/contract/transaction event batch with reason, no account mutation,
and no history deletion. A policy authority can also correct one original
payment record while the claim remains active or after it was satisfied: the
correction atomically returns the exact settled funds, restores outstanding
amount, records the original-to-correction link, and rejects a second
correction. A correction after final payment explicitly reopens the satisfied
claim and fulfilled simple-debt contract in the same batch. It neither deletes
history. A distinct policy cancellation reversal references one cancellation
record, restores its pinned remaining outstanding, and reopens the cancelled
claim/contract pair without account movement; it is not a payment correction.
The debt slice excludes generic contracts, interest, due/default handling, and
persistence. The implemented backend-only
privacy query allows an account owner, debt party, or configured authority
principal and denies third parties before returning projection values. It does
not establish transport/session authorization or Godot field projection.

The first generic contract record foundation is implemented: registered typed
`simple_transfer` or `simple_service` terms define the accepted shape, and an
active record can only be fulfilled or terminated by a configured policy
authority. A `simple_service` definition with a declared completion evidence
kind can also let that authority atomically record matching typed evidence and
fulfill the record. It does not transfer funds/assets, accept arbitrary text,
execute arbitrary terms, or establish a production authorization source.

## Work

1. Extend the implemented account/balance, fixed-offer, purchase transaction,
   item title, `OwnershipRight`, credential links, and simple-debt projections
   with broader cross-domain contract execution where later rules require it,
   transport authorization and richer
   contract records where later rules require them.
2. Extend the implemented fixed-offer purchase, zero-consideration gift, and
   simple-debt issue/payment with richer debt and contract primitives as atomic
   cross-domain settlements with pinned revisions.
3. Preserve the item/right boundary: actors are never item instances, and loss
   of a deed/document never changes a legal right.
4. Add rollback/audit/replay tests for insufficient funds, stale revisions,
   unauthorized right transfer, bound item, and duplicate transaction commands.

The current backend privacy query now also has an audience-specific allowlist
projection for account and debt payloads. It is deliberately not transport
authentication or a Godot/session grant source.

## Exit Criteria

A purchase changes balance, possession, title/right policy, and audit record in
one batch or changes none of them.

## Evidence

`gameplay-economy-authority` plus predecessor replay and possession profiles.
