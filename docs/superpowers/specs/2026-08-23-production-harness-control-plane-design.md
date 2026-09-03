# Production Harness Control Plane

## Status

- Date: `2026-08-23`
- Scope: `D:\Paralls-phase0-1`
- Decision mode: user-approved architecture

## Goal

Turn the current process-local Harness execution contract into a production-oriented control plane that can correlate, recover, authorize, redact, and verify real ESM, Gameplay, embodied, transport, and Godot tasks without owning their domain truth.

## Design

### Control-plane ownership

`HarnessTaskControlPlane` owns only task execution metadata:

- task/run/correlation/causation identities;
- lifecycle phase and compare-and-set revision;
- attempt/retry budget and checkpoint reference;
- capability grant and consumption state;
- failure disposition;
- redacted trace records and evidence references.

ESM remains the owner of object/environment/physical results. Gameplay authorities and `GameplayEventStore` remain the owners of gameplay facts. `EmbodiedInteractionSessionService` remains the owner of session lifecycle. Godot remains a presentation and local realization consumer.

### Durable task ledger

The ledger is SQLite-backed and uses one transaction per task mutation. Each row contains the latest envelope and each trace row is append-only. Transition writes use an expected task revision; a mismatch returns `stale_revision` and performs zero mutation. Task startup is idempotent by `(task_id, run_id)` and task recovery reads the ledger before asking a domain owner about external authority state.

Recovery distinguishes:

```text
unsent -> retryable
sent_unconfirmed -> reconcile_required
authority_confirmed -> terminal_success
failed -> recovering | terminal_failure
```

The control plane never replays a committed domain command blindly.

### Capability gate

Capabilities are durable, scoped grants with `principal_ref`, `task_id`, `phase`, `policy_revision`, `expires_at`, `nonce`, and state. A capability can be consumed once for a matching phase and correlation. A commit requires the `commit` capability plus the authority and idempotency pins supplied by the domain owner.

### Failure adapters

Each integrated boundary maps its native result to a common `FailureKind` while preserving its native error code:

```text
transient, invalid_input, permission_denied, constraint_conflict,
dependency_missing, stale_revision, delivery_failed, unknown
```

The mapping is explicit per boundary and is not inferred from model text.

### Evidence join

The task trace accepts only references and bounded metadata. A terminal verification record may join:

- authority receipt/result reference;
- Gameplay transaction, event IDs, stream/global sequence and replay hash;
- outbox delivery reference;
- Godot receipt/runtime artifact reference;
- final verifier report and run ID.

Raw private payloads, secrets, hidden state, full skeletal payloads, and chain-of-thought are rejected.

### Full Harness gate

The `all` profile must fail on any registered profile failure. The existing `siming-heavenly-runtime` marker issue is handled as a verification/runtime wiring repair only; this design does not add Siming business behavior.

## Acceptance criteria

1. Durable task create, transition, trace append, capability consume, and recovery survive process restart.
2. Concurrent stale transitions fail with `stale_revision` and no partial mutation.
3. Native ESM, Gameplay, embodied, and transport failures map to the common failure contract.
4. Real embodied and at least one Gameplay/ESM/transport path emit correlated task evidence.
5. A committed task cannot be re-executed by recovery.
6. Trace metadata redaction is enforced at write time and tested with forbidden fields.
7. The full `all` profile passes with fresh evidence.

## Non-goals

- No new world/gameplay authority.
- No expansion of Siming or CharacterAgent business behavior.
- No generic Agent framework.
- No automatic model-driven policy mutation.
