# Coupled Event Store And Authority Bus Design

Status: `drafted-for-spec-review`

Date: `2026-07-31`

## Purpose

This design narrows the first Gameplay Foundation event-sourcing closure around
one operational rule:

```text
store first, bus second, one backend commit pipeline
```

The gameplay event store is the durable authority ledger. The existing
authority event bus remains the committed-event distribution surface for Godot
mirrors, Observatory, debug streams, and projection refresh. They must be
tightly coupled in one backend settlement path, but they must not collapse into
one mutable mechanism.

This file refines:

- `2026-07-23-event-sourcing-and-authority-settlement-design.md`
- `2026-07-23-persistence-replay-migration-and-hot-reload-design.md`
- `2026-07-23-godot-runtime-mirror-and-prediction-design.md`
- `2026-07-23-verification-and-acceptance-matrix-design.md`

It is also the explicit prerequisite consumed by embodied-interaction Phase 6.

## Problem

Cross-domain gameplay actions are not one notification. A handoff, handshake,
or body-gated shared action changes several authority facts at once:

```text
session state
participant slot reservation
body/posture reservation
object possession
ownership/right/audit records
presentation binding request
```

The authority event bus can distribute those facts after they exist, but it
cannot prove that all of them were committed together, that duplicates are
idempotent, that stale revisions are rejected, or that replay rebuilds the same
truth. Treating the bus as the ledger creates half-commit failure modes such as
"A lost possession but B never gained it" or "Godot mirrored an attachment that
backend authority never settled".

## Design Rule

Every gameplay settlement writes one `AtomicEventBatch` that includes:

- committed domain events
- expected stream revisions
- idempotency record
- outbox entries for the authority event bus
- result digest
- projection refresh hints

The outbox entries are committed in the same atomic batch as the events. The
dispatcher publishes only committed outbox entries to the existing authority
event bus.

## Authority Pipeline

```text
GameplayCommand
  -> settlement validates permissions, pinned revisions, and policy
  -> GameplayEventStore.append_batch(events, idempotency, outbox)
  -> committed result with global sequence and stream revisions
  -> GameplayOutboxDispatcher publishes pending committed entries
  -> existing AuthorityEventBus distributes to mirrors/projections/observatory
```

The bus is therefore not optional or secondary in product behavior. It is the
first-class delivery surface for committed facts. The store remains the source
of truth.

## Required Contracts

### `GameplayEvent`

Minimum fields:

```text
event_id
event_type
schema_version
stream_id
stream_revision
global_sequence
transaction_id
command_id
causation_id
correlation_id
visibility_policy
payload
```

Events are immutable after commit. Projections and bus consumers may store
derived views, but they must be rebuildable from committed events.

### `GameplayOutboxEntry`

Minimum fields:

```text
outbox_id
transaction_id
event_id
global_sequence
topic
audience
payload_projection
delivery_state
attempt_count
last_error
```

`payload_projection` is already filtered for the target audience. Private
payload fields must not rely on consumers to filter them after delivery.

### `AtomicEventBatch`

Minimum fields:

```text
transaction_id
command_id
expected_stream_revisions
pinned_revisions
events[]
idempotency_record
outbox_entries[]
result_digest
```

The batch has exactly two observable commit results:

```text
committed=true
  all events, idempotency result, and outbox entries are durable

committed=false
  no events, idempotency result, or outbox entries are durable
```

Partial stream commit is invalid for the first Gameplay Foundation closure.

### `AppendBatchResult`

Minimum fields:

```text
committed
transaction_id
command_id
committed_event_ids[]
resulting_stream_revisions
global_sequence_range
idempotency_status
failure
projection_refresh_hints[]
```

Failures must be typed. Revision conflict, duplicate payload mismatch,
invalid event schema, outbox projection failure, and storage failure are
different results.

## Outbox And Bus Coupling

The outbox dispatcher is the only component allowed to publish gameplay
committed events onto the authority event bus.

Rules:

1. No outbox entry exists unless the event batch committed.
2. No bus publish occurs before commit.
3. Bus publish failure does not roll back committed event truth.
4. Failed delivery leaves the outbox entry pending or retryable.
5. Every bus message carries `transaction_id`, `event_id`,
   `stream_revision`, and `global_sequence`.
6. Consumers that detect sequence gaps request resync from the store-backed
   projection surface instead of guessing.

## Reuse Of Existing Authority Event Bus

The current authority event bus remains valid for delivery. The new Gameplay
Foundation work must not fork a second runtime notification bus unless a later
approved plan replaces the bus globally.

The required change is upstream:

```text
before: settlement may publish directly to bus
after: settlement commits events + outbox, dispatcher publishes committed outbox
```

Existing ESM and Phase 0 paths may continue to publish through their current
compatibility paths. New Gameplay Foundation cross-domain actions must use the
event-store/outbox path.

## Embodied Interaction Dependency

Embodied Phase 6 may start only after the following are verified:

- `gameplay-foundation-contract`
- `gameplay-event-replay`
- an outbox/bus delivery proof showing committed events are published with
  ledger sequence and can be resynced after a simulated missed delivery

Embodied `InteractionSession`, handshake, and handoff work must consume this
store/outbox/bus pipeline. It must not emulate cross-domain authority through
`esm_compatibility_adapter`.

## Acceptance Criteria

1. Duplicate batch with the same idempotency digest returns the original
   committed result without appending new events or outbox entries.
2. Duplicate batch with a different digest rejects with zero mutation.
3. Any stream revision conflict rejects the whole batch.
4. Any outbox projection construction failure rejects the whole batch before
   commit.
5. Dispatcher retry publishes the same committed event identity and sequence,
   not a new event.
6. Full replay and checkpoint-plus-tail replay produce identical projection
   hashes.
7. Bus consumers can detect a skipped `global_sequence` and resync from the
   store-backed projection/read API.
8. No accepted batch can be observed as partial truth by projections, Godot
   mirror, Observatory, or replay.

## Non-Goals

- Implement inventory, equipment, economy, ownership transfer, or relationship
  graph domain behavior in this first coupled spine.
- Replace existing Phase 0/ESM compatibility publishing.
- Make Godot or the authority event bus a durable event store.
- Add a new dependency or external database without explicit approval.
