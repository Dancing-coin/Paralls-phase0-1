# Character Connected Action And Physical Replication Sub-Specification

Date: `2026-09-14`

Status: `final child specification of the unified character action foundation`

Parent:
`2026-09-14-unified-character-action-foundation-and-inf-tag-contract-design.md`

## Purpose And Scope

This specification separates the connected semantic-action path that can be
delivered in the first migration from future multiplayer physical authority.
It prevents the existing Gameplay mirror protocol from being mistaken for a
complete networked physics solution.

## Three Runtime Modes

### Mode A: Local embodiment

Godot runs the local `CharacterMotor`, consumes local control leases, and
produces presentation plus provisional physical evidence. Backend ESM/Gameplay
settles world consequences when connected; offline fixtures may use registered
test authorities only.

### Mode B: Connected semantic authority (Phase 1 target)

Godot sends structured control/action requests and `ActionAttempt` records over
the existing session transport. Backend validates and settles semantic
consequences. Gameplay state returns through the existing snapshot/delta and
prediction mirror. Local Motor movement remains reversible embodiment, not
world-truth confirmation.

### Mode C: Networked physical authority (future)

A separately selected fixed-tick `PhysicalAuthority` owns body simulation for
the connected world. It sends body snapshots/corrections. This mode cannot be
enabled by merely installing a networking or animation plugin.

## Control Message

```text
ActorControlIntent {
  session_id
  actor_ref
  connection_epoch
  client_sequence
  physics_tick
  lease_revision
  control_intents[]
  action_request_ids[]
  sent_at
}
```

The message expresses desired control and action IDs, never a claimed final
Transform or raw skeleton pose. Leases expire when renewals stop, the session
becomes stale, or the authority revokes the source.

## Action Transport

`ActionRequest` and `ActionAttempt` use the same actor/session identity and
carry stable `action_instance_id`, `physics_tick`, `client_sequence`,
`idempotency_key`, expected revisions, and causation/correlation data. They are
ordered locally by the deterministic action key, but backend settlement order
is determined by the authority event/aggregate revision contract.

The canonical `ActionAttempt` fields and `canonical_payload()` rules are owned
by the ESM child specification. In particular, `submitted_at` is audit-only
and excluded from the canonical payload, while `owner_contract_ref` must point
to a registered ESM, Gameplay, or Composite owner. INF is never a generic
transport or settlement route.

For the Phase 1 weapon slice, an action request may also carry the semantic
`action_family` (`melee` or `hitscan`) and a `weapon_ref`. It may carry bounded
aim/contact evidence references, but never client damage, confirmed-hit state,
ammo mutation, raw projectile truth, or a final transform.

Admission and settlement are different messages:

```text
request -> local admission/queue/reject
       -> optional local presentation
       -> ActionAttempt at marker
       -> authority result
```

An admission ack does not confirm damage, pickup, occupancy, or any other
world consequence.

Phase 1 transport limits are strict: serialized `ActionAttempt` <= `32 KiB`,
`target_refs` <= `8`, `physics_evidence_refs` <= `8`, `control_intents` <= `8`,
and `action_request_ids` <= `16`. Evidence records are limited to `32`
colliders, `16` hit sensors, and `32` contact points, with each serialized
`PhysicsContactEvidence` <= `16 KiB`. Any violation returns
`payload_limit_exceeded`; clients cannot rely on truncation.

## Existing Gameplay Mirror Relationship

The current Gameplay mirror fields remain authoritative for gameplay
projection transport:

```text
connection_epoch
delivery_sequence
facade_revision
base_facade_revision
snapshot_checksum
prediction_id
```

They must remain separate from future physical fields:

```text
authority_epoch
body_revision
physics_tick
body_snapshot_checksum
```

Gameplay projection deltas cannot be used to reconstruct body motion, and body
snapshots cannot be interpreted as committed gameplay events.

## Future Body Stream

```text
ActorBodySnapshot {
  actor_ref
  authority_epoch
  physics_tick
  body_revision
  position
  velocity
  facing
  grounded
  support_ref?
  active_action_ids[]
  correction_reason?
  snapshot_checksum
}
```

```text
ActorBodyCorrection {
  actor_ref
  authority_epoch
  base_body_revision
  target_physics_tick
  position
  velocity
  facing
  correction_envelope_ref
  reason
}
```

Godot applies a Mode C `body_correction` as a typed `MotionContribution` on a
later physics tick. It does not directly assign a remote Transform outside
Motor. Remote actors interpolate snapshots and do not create a second
world-truth physics simulation. This is distinct from Mode B
`runtime_correction`, which is a local Gameplay/runtime projection correction
and has no physical-authority meaning.

## Prediction And Failure Rules

- Local movement and pose prediction is reversible and may be discarded.
- Contact-dependent root motion follows the asset policy `hold`,
  `bounded_continue`, or `reversible_continue`.
- Gameplay prediction uses the existing `prediction_id` overlay and must be
  confirmed/rejected by a server-issued result.
- Duplicate messages are idempotently ignored or return the original result.
- Sequence gaps, stale revisions, unknown actors, and old connection epochs
  trigger resync or rejection; they never fall back to local truth.
- On reconnect, increment `connection_epoch`, clear stale leases and
  predictions, receive a complete actor/gameplay snapshot, then resume control.
- A late result cannot resurrect an expired action or lease.

## Physical Authority Gate

Mode C requires a separate decision and implementation for:

1. physical authority owner and trust boundary;
2. fixed physics tick and body-state schema;
3. collision/rigid-body determinism policy;
4. client prediction and correction budget;
5. remote interpolation and interest management;
6. body revision/replay/rollback evidence;
7. abuse validation for client-supplied control and contact evidence.

Until these are implemented, the project must report Mode B rather than
multiplayer authoritative physics. `netfox` remains a future option only after
its rollback assumptions are proven compatible with the chosen physical owner;
it is not part of the current action foundation.

## Verification Requirements

Phase 1 verifies control/action transport, idempotency, prediction
confirmation/rejection, old-epoch rejection, lease expiry, reconnect snapshot,
and ESM/Gameplay result projection. It does not claim Mode C.

Future Mode C verification must include two clients observing the same body
snapshot stream, correction under divergence, duplicate/gap recovery, remote
interpolation, and physical-authority replay evidence.
