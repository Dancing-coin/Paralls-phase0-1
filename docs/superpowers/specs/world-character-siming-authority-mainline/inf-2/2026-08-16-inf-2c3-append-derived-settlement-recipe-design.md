# INF-2C3 Append-Derived Settlement Recipe

Status: `implemented and focused-verified; reusable substrate only`

## Decision

`AppendDerivedSettlementRecipe` is a pure typed wrapper around the existing
`build_multi_stream_atomic_event_batch_from_fragments()` adapter and
`SettlementReceipt.from_append_result()` factory. It accepts only already
authorized owner fragments, produces one `AtomicEventBatch`, and derives a
receipt only from the single append result supplied by the committing owner.

The recipe has no event store, callback, scheduler, owner selection, policy
registration or domain outcome logic. Existing Survival obligation planning
uses it for settle/retry/compensate/cancel/expire batch materialization.

## Reuse and fences

- Single-owner fragments and the existing multi-owner Organization/Economy
  shapes use the same recipe input.
- Overlapping write streams, incomplete revision vectors, read-set conflicts,
  pin conflicts and visibility mismatches remain rejected by the existing
  adapter before any append.
- A rejected append result produces a zero-write receipt; a committed result
  preserves committed event IDs and resulting stream revisions exactly.

## Non-goals

This does not make arbitrary cross-domain settlement legal, create account or
payment truth, or let a caller select an owner/event family. Each existing
owner still validates its own fragment and commits through the one event store.

## Evidence

Independent focused evidence is recorded by
`scripts/verification/verify_infra_reusable_settlement_recipe.py` and
`.harness/verification/infra-reusable-settlement-recipe-report.json`.
