# Character ESM Action Attempt Settlement Sub-Specification

Date: `2026-09-14`

Status: `final child specification of the unified character action foundation`

Parent:
`2026-09-14-unified-character-action-foundation-and-inf-tag-contract-design.md`

## Purpose And Boundary

This specification defines how a locally admitted action becomes an
ESM/Gameplay/Composite authority request and how accepted or rejected results return to
the actor runtime. It closes the gap between animation/contact timing and
world truth.

ESM owns environment affordances, spatial access, occupancy, and registered
world-object state. Gameplay owns actor resources, statuses, capabilities,
equipment, abilities, and their event projections. CharacterAgent and INF may
propose intent, context, evidence, constraints, and catalysts; they cannot
settle consequences.

## ActionAttempt Contract

```text
ActionAttempt {
  attempt_id
  actor_ref
  action_instance_id
  semantic_action_id
  target_refs[]
  contact_marker_id
  contact_marker_time_seconds?
  action_family?          # melee | hitscan | interaction | other
  weapon_ref?
  physics_tick
  physics_evidence_refs[]
  physics_evidence_digest?
  authority_route_ref       # esm | gameplay | composite (Phase 1)
  owner_contract_ref?
  expected_revision_vector
  idempotency_key
  command_version
  causation_id
  correlation_id
  source_ref
  privacy_scope
  submitted_at
}
```

`owner_contract_ref` is a server-issued reference to a registered ESM,
Gameplay, or Composite owner. It cannot be an INF route. `submitted_at` is
transport/audit metadata only and is excluded from `canonical_payload()`.
Therefore retries with a changed submission time but identical stable business
fields return the original result; any other canonical-field change returns
`payload_mismatch`.

Phase 1 limits are normative: serialized `ActionAttempt` <= `32 KiB`,
`target_refs` <= `8`, `physics_evidence_refs` <= `8`, `collider_refs` <= `32`,
`hit_sensor_refs` <= `16`, `contact_points` <= `32`, and serialized
`PhysicsContactEvidence` <= `16 KiB`. Exceeding a limit returns
`payload_limit_exceeded`; the server never truncates evidence.

`attempt_id` identifies one contact transaction from one action instance.
`idempotency_key` is stable across transport retries. The attempt is a
proposal until authority settlement commits an event batch.

## Phase 1 Weapon Routes

The first weapon slice uses the same `ActionAttempt` contract as ordinary
interaction. A qualified melee marker submits provisional contact evidence;
Gameplay/ESM revalidates the weapon capability, target revision, range,
occupancy, status, and resource/equipment preconditions before committing an
outcome. A hitscan request carries a semantic weapon reference and aiming or
ray evidence, but the authority recomputes or revalidates the permitted shot
envelope. The client never submits damage, hit confirmation, ammo mutation, or
ballistic truth.

Phase 1 requires an end-to-end melee settlement and a schema/route fixture for
hitscan. Magazine, chamber, projectile, spread, recoil, and reload state are
future Gameplay capabilities, not hidden fields in animation assets.

## Route Rules

### ESM route

Use for environment-facing consequences:

- affordance validity and access policy;
- spatial range and approach envelope;
- occupancy and reservation;
- object state transitions;
- environment state-machine transitions.

### Gameplay route

Use for actor-facing consequences:

- stamina/resource cost;
- ability and skill gate;
- status change;
- equipment or inventory mutation;
- actor body-runtime projection where that domain owns the fact.

### Composite route

Use when one action changes both actor and world state. The coordinator loads
all required aggregate revisions, validates both domains, and appends one
atomic multi-stream event batch when the existing authority store supports that
boundary. If it cannot, the action must expose an explicit reservation and
compensation lifecycle and must be labelled non-atomic.

## Settlement Pipeline

```text
decode/schema validation
→ authenticate and authorize
→ idempotency lookup
→ pin policy/package/world revisions
→ load expected actor + world streams
→ validate ActionWindowIntent and affordance/status preconditions
→ revalidate physical evidence against the authority envelope
→ produce typed effect proposals
→ validate complete event batch
→ atomic append or zero commit
→ publish committed projection/outbox
→ return AuthorityResult
```

Local animation completion, a contact marker, or a positive collider flag is
never a settlement result. The authority may reject an attempt even when the
local animation looked correct.

## AuthorityResult Contract

```text
AuthorityResult {
  attempt_id
  action_instance_id
  outcome                  # committed | rejected | unknown
  transaction_id?
  committed_event_ids[]
  resulting_revision_vector
  failed_stage?
  error_code?
  failed_precondition?
  recovery_action
  causation_id
  correlation_id
  authority_scope
}
```

`unknown` is reserved for an append/transport boundary where commit status
cannot yet be determined. The client must query using the original
idempotency key; it must not retry with a new key.

## Concurrency And Idempotency

- Independent same-tick attempts may settle independently.
- Attempts touching the same aggregate or declared atomic group share expected
  revisions and race through optimistic concurrency; at most one compatible
  revision commits.
- Duplicate delivery returns the original result and transaction identity.
- Same idempotency key with a different canonical payload is rejected.
- A stale attempt returns typed `revision_conflict` or `precondition_failed`;
  the client refreshes and creates a new attempt rather than mutating the old
  one.
- A late result can update a projection only if its attempt is still current;
  it cannot resurrect a cancelled or timed-out `ActionInstance`.

## Projection And Recovery

Committed results update `CharacterRuntimeState` and the Godot Gameplay mirror
only through the existing authority event/projection path. A rejected result
releases claims, cancels or recovers the action according to its descriptor,
and resumes the control lease by revision. A timeout marks the attempt
unknown, freezes unsafe authority-dependent root motion, and waits for query
or resync.

ESM/Gameplay event streams remain the world/gameplay truth. Godot stores only
the local action/runtime projection and evidence references; it does not
rebuild authority history from animation events.

## Verification Requirements

Required tests cover:

1. successful ESM interaction with a real affordance revision;
2. Gameplay resource/status rejection with zero partial commit;
3. composite actor+world action atomicity or explicit non-atomic compensation;
4. duplicate retry returning the original settlement;
5. same-key different-payload rejection;
6. concurrent same-revision attempts where at most one commits;
7. timeout/unknown commit query using the original idempotency key;
8. late-result rejection after cancellation;
9. local contact evidence that produces no world change without settlement.

## Deferred Work

- new domain event families outside existing ESM/Gameplay ownership;
- local damage or hit truth in animation assets;
- using INF or Siming as a settlement route;
- client-created authority revisions or event history.
