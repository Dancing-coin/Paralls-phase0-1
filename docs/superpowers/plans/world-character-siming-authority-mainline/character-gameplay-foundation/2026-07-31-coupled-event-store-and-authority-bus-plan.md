# Coupled Event Store And Authority Bus Implementation Plan

Status: `drafted-for-spec-review`

Date: `2026-07-31`

## Goal

Implement the Gameplay Foundation prerequisite that unblocks embodied
`InteractionSession` work: a backend authority event store, atomic event-batch
writer, committed outbox, and existing authority event-bus delivery path that
operate as one settlement pipeline.

This plan implements only the shared spine. It does not implement inventory,
equipment, ownership transfer, economy, relationship graph, or Godot gameplay
mirror behavior beyond the minimum bus/resync proof.

## Source Specs

- `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-31-coupled-event-store-and-authority-bus-design.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-23-event-sourcing-and-authority-settlement-design.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-23-persistence-replay-migration-and-hot-reload-design.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-23-verification-and-acceptance-matrix-design.md`
- Embodied gate consumer:
  `docs/superpowers/plans/world-character-siming-authority-mainline/embodied-interaction-product-foundation/2026-07-29-embodied-interaction-product-foundation-implementation-plan.md`

## Preconditions

- Existing `phase0`, `phase1-slice`, `mainline-unified-runtime`, and
  `embodied-interaction-foundation-all` profiles pass before implementation.
- No new dependency without explicit approval.
- Write failing tests before implementation behavior.
- Preserve current ESM/Phase 0 compatibility publishing.

## Phase 0: Contract Skeleton And Failing Profiles

**Primary files:** add models under `backend/app/gameplay/` or the nearest
existing backend domain package; tests under `backend/tests/`; verifier scripts
under `scripts/verification/`; profiles under `.harness/profiles/`.

1. Add Pydantic models for `GameplayEvent`, `GameplayOutboxEntry`,
   `AtomicEventBatch`, `AppendBatchResult`, idempotency record, typed failure,
   and projection refresh hint.
2. Add tests that initially fail for:
   - duplicate same digest idempotency
   - duplicate different digest rejection
   - expected revision conflict
   - invalid event schema
   - outbox projection failure
   - missing `transaction_id`, `event_id`, or `global_sequence`
3. Add `gameplay-foundation-contract` profile with meaningful failing checks.
4. Document the profile in `docs/harness.md` and `docs/INDEX.md`.

**Exit criteria:** contract profile fails for real missing behavior before
implementation and existing regressions still pass.

## Phase 1: In-Memory Event Store And Atomic Batch Writer

**Primary files:** add `GameplayEventStore`, `GameplayEventBatchWriter`, and
idempotency storage under backend gameplay services.

1. Implement append-only streams with stream revision assignment.
2. Implement global sequence assignment.
3. Implement `append_batch(...)` with all-or-nothing semantics.
4. Validate all expected stream revisions before mutation.
5. Validate idempotency digest before mutation.
6. Validate all event/outbox schemas before mutation.
7. Ensure commit result includes event IDs, stream revisions, and sequence
   range.

**Exit criteria:** no test can observe partial stream, idempotency, or outbox
mutation after a rejected batch.

## Phase 2: Projection Replay And Checkpoint Equivalence

**Primary files:** projection registry/store under backend gameplay services;
focused replay tests.

1. Implement projection registration by projection ID and schema version.
2. Implement full replay from committed events.
3. Implement checkpoint-plus-tail replay.
4. Produce deterministic projection hashes.
5. Add explicit upcast failure behavior and tests.
6. Add `gameplay-event-replay` profile.

**Exit criteria:** full replay and checkpoint-plus-tail produce the same hash;
upcast failure is typed and does not silently skip events.

## Phase 3: Committed Outbox And Existing Authority Event Bus Delivery

**Primary files:** `GameplayOutboxDispatcher` and adapter to the existing
authority event bus/projector path.

1. Store outbox entries in the same atomic batch as events.
2. Dispatch only committed pending outbox entries.
3. Mark delivery state without changing committed event truth.
4. Preserve `transaction_id`, `event_id`, `stream_revision`, and
   `global_sequence` on every bus payload.
5. Simulate bus delivery failure and retry the same outbox entry.
6. Simulate a consumer sequence gap and prove resync from store-backed events
   or projection read model.

**Exit criteria:** bus delivery is tightly coupled to committed ledger truth,
but delivery failure never rolls back committed events.

## Phase 4: Harness Aggregate And Embodied Gate Proof

1. Add `gameplay-foundation-event-spine` or equivalent aggregate profile that
   runs:
   - `gameplay-foundation-contract`
   - `gameplay-event-replay`
   - outbox/bus delivery proof
2. Update `embodied-interaction-foundation-all` report or gate metadata to
   recognize the Gameplay event-batch prerequisite when this aggregate passes.
3. Update docs/runbook status without promoting Phase 6 itself to complete.
4. Run:

```powershell
python scripts/verification/harness.py --profile gameplay-foundation-contract
python scripts/verification/harness.py --profile gameplay-event-replay
python scripts/verification/harness.py --profile gameplay-foundation-event-spine
python scripts/verification/harness.py --profile embodied-interaction-foundation-all
python scripts/verification/harness.py --profile all
git diff --check
```

**Exit criteria:** the new Gameplay event-spine aggregate and repository-wide
`all` pass with fresh evidence under `.harness/verification/`.

## Handoff To Embodied Phase 6

After this plan is implemented and verified, the embodied plan may proceed to
Phase 6. The next embodied implementation must:

- consume the Gameplay `append_batch` writer for session lifecycle events
- write `InteractionSession` proposed/accepted/rejected/authorized/realizing/
  cancelled/interrupted/committed events through the batch writer
- publish committed session events through the outbox/event bus path
- keep using the embodied evidence ledger for attempt/session observatory and
  privacy-filtered replay
- keep `esm_compatibility_adapter` only for first-closure single-object
  compatibility paths, not social/cross-domain sessions

## Non-Goals

- Implement `grab-carry-handoff` ownership transfer before inventory/ownership
  plans are implemented.
- Implement production persistence or an external database.
- Replace the authority event bus.
- Move authority state to Godot.
