# Character Gameplay Foundation Verification And Acceptance Matrix

Status: `implemented-foundation; broader-closure-planned`

Date: `2026-07-23`

## Purpose

Define the machine-checkable evidence required before any implementation phase
of the character gameplay foundation may be described as complete.

The profile names in this document are now a mix of implemented foundation
proofs and planned closure gates. Implemented profiles record the bounded
slices described by the current gameplay README/baseline docs; deferred rows
remain non-executable targets until their own code and harness evidence exist.

## Verification Principles

- Test authority failures as deeply as successful paths.
- Verify event replay, not only current in-memory state.
- Verify projections against event truth and Godot mirrors against projections.
- Use exact revision, transaction, causation, and source references in evidence.
- Never treat a static schema check as runtime integration proof.
- Retain generated evidence under `.harness/verification/`.

## Harness Mapping

| Profile | Required proof |
|---|---|
| `gameplay-foundation-contract` | Commands, events, errors, manifests, snapshots, deltas, IDs, versions, and privacy scopes validate. |
| `gameplay-event-replay` | Empty-stream replay, checkpoint recovery, upcasting, idempotency, revision conflicts, and atomic event batches are deterministic. |
| `gameplay-state-groups` | Current profile proves the versioned registry, explicit-context lifecycle batches, lifecycle read projection, read-only facade composition, consumer-filtered views, and exact-base snapshot/delta reconstruction. Policy-activation loading, persistent rebuild, transport delivery, and Godot mirror delivery remain deferred. |
| `gameplay-possession-equipment` | Item location, container capacity, storage-ring weight rules, equipment grants, grant removal, and presentation refs work. |
| `gameplay-economy-authority` | The implemented account, fixed-purchase, gift, ownership transfer, simple-debt, payment-record correction, cancellation-record reversal, registered-terms contract record, registered service-completion fulfillment, backend privacy-query primitives, and configured audience field redaction remain atomic or fail closed. Payment correction is append-only and idempotent; it restores an active claim or explicitly reopens a satisfied claim/fulfilled simple-debt contract in the same batch. Cancellation reversal is a separate append-only and idempotent path that restores only the cancellation record's pinned outstanding amount without account movement. Service completion accepts only a matching registered evidence kind and fulfills without cross-domain settlement. Redacted payloads are backend-only and do not authenticate transport principals or grant sessions. Broader contract execution, transport authorization, persistence, and Godot delivery remain deferred. |
| `gameplay-patch-runtime` | Manifest validation, Rule IR limits, capability authorization, conflicts, upgrades, disable, and replay work. |
| `godot-gameplay-mirror` | Current profile proves the filtered Godot envelope, backend-issued session scope, bounded `/ws` read commands, after-commit fanout plumbing, and a local Godot bridge scope/disconnect probe. It does not prove production identity adapters, end-to-end live reconnect/resync, prediction/rollback, or broad scene coverage. |
| `adventure-basic` | Deferred closure gate only. The five approved end-to-end reference scenarios remain required before execution-ready status; current code and harness evidence do not satisfy this row. |
| `gameplay-foundation-all` | Planned aggregate after the remaining closure gates exist. Broad repository completion still uses the top-level `all` profile rather than a finished gameplay-only aggregate. |

## Contract Matrix

| Area | Success evidence | Failure evidence |
|---|---|---|
| Command identity | Repeated idempotency key returns the original result. | Conflicting payload under the same key is rejected. |
| Revision control | Matching expected revision appends events. | Stale expected revision produces no events. |
| Atomic settlement | All events in a purchase share one transaction ID and commit. | Any invalid effect leaves currency, inventory, ownership, and audit projections unchanged. |
| Replay | Full replay and checkpoint-plus-tail produce identical hashes. | Unknown event version blocks recovery with a typed migration error. |
| Projection rebuild | Rebuilt facade equals live facade. | Projection failure leaves event truth intact and marks the projection unhealthy. |
| State-group lifecycle | Enabled group materializes and synchronizes. | Missing dependency or conflicting schema blocks enablement. |
| Modifier resolution | Sources and ordering produce a stable explained value. | Ambiguous override/exclusive conflict blocks activation. |
| Capability handler | Authorized bounded handler returns a typed proposal. | Unauthorized, timed-out, or malformed handler output rejects settlement. |
| Privacy | Actor-safe and Godot-safe views contain allowed fields only. | Actor-private refs are rejected from Siming/public projections. |
| Godot synchronization | Ordered deltas advance the actor mirror revision. | Gap, duplicate conflict, or schema mismatch requests a full snapshot. |

## Domain Acceptance Scenarios

### Resource, status, and body

- A stamina cost commits with the successful action event.
- Insufficient stamina produces no cost event.
- A right-arm injury blocks the sword affordance without deleting learned
  sword skill state.
- Removing or resolving the injury restores affordance through projection.
- Effective-stat explanation names every accepted and rejected modifier.

### Inventory, container, and equipment

- Item identity survives moves between backpack, hand, equipment slot, and
  storage ring.
- Capacity, volume, type, access, and binding failures are structured.
- A storage ring contributes its own weight while its contents do not propagate
  carried weight.
- Unequipping removes all grants, modifiers, container access, and presentation
  bindings from that equipment source.
- No item disappears during a rejected move or unequip.

### Economy and ownership

- Sword purchase atomically changes balance, item possession, ownership, and
  transaction audit projection.
- Land purchase creates a right and an optional deed item with separate
  identities.
- Losing the deed item does not delete the land right.
- Unauthorized, insufficient-fund, bound-item, and stale-revision transactions
  append no partial events.
- An actor-related command right references an actor and contract; it never
  serializes the actor as an item.

### Gameplay patch runtime

- Installing a valid patch registers only declared state and capabilities.
- Missing dependency, circular dependency, schema collision, and unresolved
  modifier conflict block activation.
- Rule IR execution is deterministic under the declared budgets.
- Disabling a patch stops new rules without deleting historical events.
- An active transaction remains pinned to its starting patch revision during
  upgrade.

### Godot mirror

- The global bridge routes updates to the correct per-actor mirror.
- Consumers read typed mirror APIs rather than raw WebSocket payloads.
- A confirmed prediction aligns with the authoritative revision.
- A rejected prediction restores UI, animation, and temporary local state.
- Reconnection and revision gaps produce one full resync without duplicating
  effects.

## adventure-basic End-To-End Evidence

Each scenario must retain:

- command request and typed result
- appended event batch
- event-stream revisions before and after
- rebuilt domain projection
- `CharacterGameRuntimeState` facade snapshot
- Godot snapshot/delta and final mirror state
- explanation trace for permissions, costs, modifiers, and failures
- replay result hash

The five required scenarios are:

1. purchase and equip a sword
2. reject a known sword action because of injury or stamina
3. equip and use a storage ring with correct encumbrance
4. preserve land ownership after losing the deed item
5. complete a minimal gift, debt, and contract lifecycle

## Migration And Reliability Gates

- Every event type has an explicit version.
- Every supported historical version has an upcaster or a deliberate hard
  compatibility boundary.
- Checkpoint schema and projection schema versions are recorded separately.
- Clean replay from the oldest supported fixture is part of CI.
- Patch upgrades include before/after replay fixtures.
- No migration test mutates retained historical events.
- Failure injection covers event-store write failure, projection crash,
  capability timeout, WebSocket disconnect, duplicate delta, and stale command.

## Acceptance Criteria

An implementation phase is complete only when:

1. its focused tests pass
2. its planned focused harness profile passes
3. all predecessor profiles still pass
4. `gameplay-foundation-all` passes
5. the repository `all` profile passes for broad completion
6. fresh reports exist under `.harness/verification/`
7. known gaps are recorded rather than hidden

## Non-goals

- claiming current profile implementation from this design document
- replacing runtime proof with schema-only checks
- requiring deferred cultivation, market, relationship-graph, or Siming-graph
  implementations for the first closure
