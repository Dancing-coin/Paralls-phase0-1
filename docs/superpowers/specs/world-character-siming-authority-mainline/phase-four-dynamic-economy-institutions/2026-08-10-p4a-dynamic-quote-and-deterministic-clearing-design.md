# P4A Dynamic Quote And Deterministic Clearing

Status: `implemented-and-verified; matching focused Harness evidence fresh on 2026-08-11`

## Purpose

Evolve P1 fixed offers into versioned public quote and order proposals while
retaining Economy as the owner of consideration and posting.

## Contract

A quote/order declares issuer, item/quality class, side, quantity limit,
integer/fixed-point price, validity window, delivery/cancellation policy,
inventory/capacity reference, public digest and pinned policy revision.
A deterministic clear receives a bounded scope and returns candidate matches
plus an explanation digest. Authority revalidates every candidate against
current revisions/reservations, creates the `SettlementPlan`, then atomically
commits domain facts.

## Exclusions And Gate

No hidden order-book owner, auction, float arithmetic, AI price writer,
cross-region exchange or macro price index. Test expiry, cancellation, race for
stock, stale quote, deterministic ordering, partial reject and replay equality.
