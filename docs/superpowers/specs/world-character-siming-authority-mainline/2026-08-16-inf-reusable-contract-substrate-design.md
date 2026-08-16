# INF Reusable Contract Substrate Design

Status: `INF-C1 through INF-C5 implemented and independently verified; no external runtime or dependency is introduced`

## Decision

Before further domain-specific INF owner rows are added, complete the reusable,
bounded contract substrate already implicit in the existing authority spine.
The substrate must make a new approved row cheaper to add without allowing a
caller, client, LLM, ecology planner, or branch preview to select an owner or
write world truth.

The only formal write path remains:

`existing authority -> GameplayCommandEnvelope / SettlementPlan -> GameplayEventStore.append_batch() -> outbox -> scoped projection`.

## Reusable Layers

1. **State transition planning.** `EffectLifecycleEvaluator` remains pure and
   becomes the single decision shape for registered `add`, `replace`,
   `refresh`, `reject`, expiry, dispel, and transform transitions. Its output
   is a typed owner proposal, never an event or writer. Every registered owner
   adapter validates its own source vector and converts that proposal to its
   own fragment.
2. **Closed obligation lifecycle.** `ObligationLifecycleRegistration` remains
   the one closed owner contract for `open -> due -> settled/cancelled/expired/
   retry/compensated`. Event-derived materialization and bounded catch-up stay
   read-only. Owner terminal builders remain responsible for domain outcome,
   privacy, revision and compensation semantics.
3. **Atomic settlement recipe.** `SettlementPlan` remains the only shared
   planner shape. It assembles already-authorized owner fragments and derives
   one receipt from the one append result. It never chooses fragments, creates
   a policy, or commits a batch itself.
4. **Ecology consumer admission.** The finite catalog becomes a reusable
   contract check for source pin, target owner, stream, event family, scope,
   revision and replay reader. Ecology can plan a consequence, but only the
   target owner can build and commit its fragment.
5. **Branch replay boundary.** `FixedBaseBranchReplayContract` retains fixed
   base revision, calibration/source digest, deterministic input ordering and
   projection digest. It is consumed by the existing isolated branch reader
   and the fixed Organization supply admission; branches have no promotion
   authority and listed production owners still validate and commit their own
   consequences.

## External Research

- `pyeventsourcing/eventsourcing` demonstrates aggregate reconstruction,
  snapshots, optimistic concurrency and notification/projector separation.
  We reuse those principles, not its application runtime or persistence layer:
  Paralls already has its one event store and scoped projections.
- `temporalio/sdk-python` demonstrates deterministic workflow history replay.
  We reuse deterministic input/replay tests only. Its durable workers,
  task queues and workflow server are rejected because they would create a
  second scheduler/runtime authority.
- `renew-engine/renew` demonstrates fixed timestep, seed/input traces and
  replay digest comparison. We reuse fixed-base/digest checks for branch
  replay, not its engine or ECS.
- `oskardudycz/EventSourcing.NetCore` reinforces event-as-past-fact,
  stream-position concurrency and projection separation. It informs naming
  and tests, not a dependency migration.

## Non-goals

This package does not add open registration, a generic expression/script
executor, a generic writer, an external workflow engine, a second event store,
a second clock, generic branch promotion, population/NPC/social truth, or
civilization simulation.

## Completion Boundary

The substrate is complete only when each layer has:

- one typed contract/plan API with no append capability;
- at least two existing-owner consumers where the layer claims reuse;
- independent focused assertions for success, zero-write rejection, duplicate,
  revision conflict, scope/privacy and full/checkpoint-tail replay where
  applicable; and
- a Harness report that proves the layer rather than a single domain sample.

An owner row remains incomplete until it independently names its owner, stream,
event family, projection scope, revision/idempotency rule, receipt and replay
reader.

INF-C5 completion evidence:
`.harness/verification/infra-fixed-base-branch-replay-contract-report.json`.
This closes only the reusable deterministic branch replay contract; generic
branch settlement, generic promotion and complete group simulation remain
outside the completion boundary.
