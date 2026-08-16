# INF-2 Time, Obligation, And Cross-Domain Settlement Design

Status: `historical narrow clock/coordinator vertical verified; August INF-2 lifecycle closure remains incomplete`

## Purpose

INF-2 turns the existing caller-driven `SimulationClock` into an owner-scoped
obligation settlement boundary. It extends `world_runtime`, existing domain
authorities, `SettlementPlan`, `GameplayEventStore`, outbox, and replay; it
does not create a scheduler, clock, event store, or authority beside them.

## Existing Owner And Boundaries

`world_runtime/simulation_clock.py` selects due work only. Domain owners own
their obligations and state. The clock/coordinator is reusable infrastructure,
not proof that economy, survival, production, and population continuity each
has a completed lifecycle row. A coordinator may only assemble
already-authorized `OwnerAuthorizedFragment` values into one existing atomic
batch. It may neither decide an owner outcome nor mutate world state.

All writes follow:

```text
caller -> GameplayCommandEnvelope / SettlementPlan -> owner fragments
-> GameplayEventStore.append_batch() -> outbox/replay -> scoped projection
```

Clients, Godot, LLMs, Siming, creator tooling, and MCP submit proposals,
intents, or evidence only.

## Contracts And Events

`ScheduledObligation` gains stable lifecycle fields: `open`, `due`,
`settling`, `retryable`, `closed`, `cancelled`, and `failed`. Each instance
carries its owner, source refs, due tick, policy revision, expected revisions,
idempotency key, retry/compensation policy, and visibility scope.

`ActivationLock` is a population-continuity admission boundary. The only
implemented pending row is INF-4C's event-derived `schedule_gated_supply`
admission, released into the existing Organization fragment after its own pins
are revalidated. It is not a generic obligation pending queue and does not
bind `ScheduledObligation` settlement to activation.

The verified slice validates lifecycle state values at the contract boundary
and appends owner consequence events. Event-sourced `world.obligation.*`
lifecycle transitions, retry, cancellation, and compensation are planned
INF-2R work, not current verified behavior. Activation lock/pending merge has
its own append-backed population-continuity path.

`SettlementReceipt` is the one post-append outcome: transaction ID, committed
event IDs, stream revisions, projection digests, rejected/deferred effects,
audit refs, pinned revisions, idempotency status, and explicit zero-write
failure code. It is derived from append result and scoped projections, not a
second persistence record.

## Determinism, Failure, Privacy, And Replay

Clock advancement is explicit and monotonic. Due selection is sorted by due
tick then obligation ID and bounded by the supplied catch-up budget. No timer,
thread, or read-path mutation is permitted. Duplicate owner/idempotency pairs
replay their original receipt. Any stale revision, missing owner authorization,
unsupported status, lock conflict, or fragment overlap rejects before
`append_batch()` and writes nothing. Transition-history validation and policy
mismatch handling are INF-2R work.

Authority views receive the needed owner facts; public and actor views expose
only their scope-filtered receipt/projection. Checkpoint-plus-tail replay must
match full replay for committed owner consequences under the same active
revisions. Versioned lifecycle readers, upcasters, cancellation, and
compensation are INF-2R work and are not claimed by this vertical.

## Harness And Completion

`infra-time-obligation` is retained as historical evidence for the explicit
clock/coordinator surface and named owner-fragment tests. Its old activation
fixture proves legacy deferral/release only, not generic or event-derived
pending merge; the authoritative event-derived schedule row is covered by
`infra-activation-pending-schedule-merge`.

August INF-2 remains incomplete until event-derived
`open/due/settled/cancelled/expired/retry/compensated` lifecycle rows exist for
construction and at least one survival/economy owner, with bounded catch-up,
owner-approved activation-pending integration, and a single-store receipt. The
existing narrow evidence is not a completion substitute.

## Non-Goals

No background simulation loop, generic economic model, new population owner,
direct client writes, arbitrary creator code in replay, or P6/P7 work is in
scope.
