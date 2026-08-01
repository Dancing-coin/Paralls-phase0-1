# Gameplay Foundation Contracts, Events, And Harness Plan

Status: `drafted-for-spec-review`

## Scope

Create the shared backend-owned gameplay command/event/result vocabulary and
the durable event/projection spine. This is the first implementation plan and
owns no inventory, economy, equipment, or Godot domain behavior.

## Work

1. Add namespaced IDs, correlation/causation, actor/world/patch revisions,
   idempotency keys, visibility, schema versions, and typed failure/retry data.
2. Implement event-stream append with expected-revision validation and atomic
   multi-stream batches; conflicting idempotency payloads must reject.
   Commit authority-event-bus outbox entries in the same batch, then dispatch
   only committed entries.
3. Implement projection registration, rebuild-from-stream, checkpoint-plus-tail
   equivalence, health reporting, and upcast failure boundaries.
4. Add `gameplay-foundation-contract` and `gameplay-event-replay` profiles with
   duplicate, stale, partial-write, invalid-event, checkpoint, upcast, outbox
   retry, and bus sequence-resync tests.

## Exit Criteria

No accepted batch partially mutates event truth or outbox truth. Full replay
and checkpoint-plus-tail produce the same projection hash. Existing authority
event publication receives committed notifications through the outbox
dispatcher, but cannot become the store.

## Evidence

Run the two new focused profiles and existing authority/settlement regressions;
retain reports under `.harness/verification/`.
