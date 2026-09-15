# Character Connected Action And Physical Replication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver connected semantic action/control transport for Phase 1 while reserving a separate, honest path for future network-authoritative body simulation.

**Architecture:** Mode A runs local Motor and presentation. Mode B sends structured intent/action messages and receives Gameplay/ESM results through the existing session transport. Mode C is not implemented here; its body stream, authority epoch, and correction contracts are reserved but cannot be confused with the Gameplay mirror.

**Tech Stack:** Existing WebSocket/session protocol, Python backend protocol models, Godot `BackendBridge`, Gameplay mirror, CharacterAgent adapters, pytest, and Harness integration checks.

**Spec:** `docs/superpowers/specs/2026-09-14-character-connected-action-and-physical-replication-subspec.md`

**Execution status:** Task-level reference for Task 11 of
`docs/superpowers/plans/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-implementation-plan.md`.
The unified plan is the only implementation order; this file does not define
an alternate runtime path or release gate.

## Global Constraints

- Cross-boundary messages carry semantic intent and action IDs, never raw transforms or bone poses.
- Gameplay mirror fields remain separate from future physical body fields.
- Local movement and pose prediction are reversible and do not confirm world truth.
- Lease expiry, sequence gaps, stale revisions, unknown actors, and old epochs fail closed.
- Reconnect increments `connection_epoch`, clears stale leases/predictions, and requires a complete snapshot.
- No raw-pose networking, netfox rollback, or server-authoritative rigid-body claim is made in Phase 1.
- Mode B `runtime_correction` is a bounded Gameplay/runtime projection input
  that still passes through Motor; Mode C `body_correction` is future-only and
  requires a selected `PhysicalAuthority`, epoch, body revision, and fixed tick.
- Phase 1 action transport carries semantic `melee`/`hitscan` families and
  weapon references only; it never transports client damage, confirmed hits,
  ammo mutation, raw projectile state, or final transforms.

### Task 1: Define connected control and action envelopes

**Files:**
- Modify: `backend/app/ws_protocol.py`
- Create: `backend/app/models/actor_control_intent.py`
- Create: `backend/app/models/connected_action_request.py`
- Test: `backend/tests/test_character_connected_control_models.py`

**Interfaces:**
- `ActorControlIntent.from_payload(dict) -> ActorControlIntent`
- `ConnectedActionRequest.from_payload(dict) -> ConnectedActionRequest`
- `to_payload() -> dict`

- [ ] Add session, actor, connection epoch, client sequence, physics tick, lease revision, control intents, action request IDs, and sent-at fields.
- [ ] Validate bounded intent payloads and reject transform/pose fields.
- [ ] Keep action attempts linked by stable `action_instance_id` and idempotency key.
- [ ] Apply the canonical `ActionAttempt` schema from the ESM child plan;
  exclude `submitted_at` from `canonical_payload()` and reject over-limit
  payloads with `payload_limit_exceeded`.
- [ ] Include optional semantic `action_family` and `weapon_ref` fields while
  rejecting raw hit/damage/ammo/pose payloads.
- [ ] Run focused model tests before transport changes.

### Task 2: Add lease renewal and ordering rules

**Files:**
- Modify: `backend/app/services/session_input_router.py`
- Modify: `scripts/character/CharacterControllerPort.gd`
- Modify: `scripts/autoload/BackendBridge.gd`
- Test: `backend/tests/test_character_connected_lease_ordering.py`

**Interfaces:**
- `SessionInputRouter.accept_control_intent(ActorControlIntent) -> dict`
- `CharacterControllerPort.renew_control_lease(Dictionary) -> Dictionary`

- [ ] Reject expired leases, stale lease revisions, old epochs, duplicate sequences, and impossible future ticks.
- [ ] Define stable local ordering by actor, physics tick, source priority, and client sequence.
- [ ] Ensure control lease expiry releases action claims and does not move the actor through a fallback path.
- [ ] Run lease/order tests with duplicate and gap cases.

### Task 3: Preserve Gameplay mirror separation

**Files:**
- Modify: `backend/app/gameplay/godot_mirror_delivery.py`
- Modify: `backend/app/services/gameplay_mirror_session_access_service.py`
- Modify: `scripts/character/CharacterRuntimeState.gd`
- Modify: `scripts/ui/CharacterDirectorState.gd`
- Test: `backend/tests/test_character_gameplay_mirror_separation.py`

**Interfaces:**
- `GameplayGodotMirrorSyncAdapter.apply_delta(dict) -> dict`
- `CharacterRuntimeState.apply_gameplay_projection(Dictionary) -> void`

- [ ] Keep `delivery_sequence`, `facade_revision`, `base_facade_revision`, `prediction_id`, and snapshot checksum in the gameplay projection namespace.
- [ ] Reject body revision/authority epoch fields in the Gameplay mirror handler.
- [ ] Keep `runtime_correction` out of the Gameplay mirror's body schema; it is
  a typed local Motor contribution, not a physical-authority snapshot.
- [ ] Ensure body-like local movement remains reversible embodiment state.
- [ ] Run mirror separation tests and existing prediction tests.

### Task 4: Reserve future body snapshot/correction envelopes

**Files:**
- Create: `backend/app/models/actor_body_snapshot.py`
- Create: `backend/app/models/actor_body_correction.py`
- Modify: `backend/app/ws_protocol.py`
- Test: `backend/tests/test_character_body_stream_protocol.py`

**Interfaces:**
- `ActorBodySnapshot.from_payload(dict) -> ActorBodySnapshot`
- `ActorBodyCorrection.from_payload(dict) -> ActorBodyCorrection`

- [ ] Define actor ref, authority epoch, physics tick, body revision, position, velocity, facing, grounded, support ref, active action IDs, correction reason, and checksum.
- [ ] Keep these envelopes disabled unless a selected PhysicalAuthority is configured.
- [ ] Reject direct remote transform assignment; corrections become typed Motor contributions.
- [ ] Document the physical-authority gate and the conditions required before Mode C can be enabled.
- [ ] Run protocol tests proving disabled Mode C cannot masquerade as Mode B.

### Task 5: Implement reconnect, resync, and prediction recovery

**Files:**
- Modify: `scripts/autoload/BackendBridge.gd`
- Modify: `scripts/character/CharacterReplica.gd`
- Modify: `backend/app/services/session_input_router.py`
- Test: `backend/tests/test_character_connected_recovery.py`

**Interfaces:**
- `BackendBridge.handle_reconnect_snapshot(Dictionary) -> void`
- `SessionRouter.reconnect_session(dict) -> dict`

- [ ] Increment connection epoch and clear stale leases and predictions.
- [ ] Require a complete actor/gameplay snapshot before resuming control.
- [ ] Handle gaps, duplicate messages, unknown actors, and late action results with explicit resync/rejection.
- [ ] Ensure local Motor prediction can be discarded without writing world truth.
- [ ] Run recovery tests including reconnect during an in-flight action.

### Task 6: Connected semantic integration verification

**Files:**
- Create: `scripts/verification/verify_character_connected_action.py`
- Test: `backend/tests/test_character_connected_action_profile.py`

- [ ] Start the backend and Godot bridge, send a finite control intent, and observe a committed or rejected semantic result.
- [ ] Verify lease renewal, action request ordering, idempotency, prediction confirmation/rejection, and old-epoch rejection.
- [ ] Verify one melee request reaches the normal attempt/result path and one
  hitscan request remains an authority-bound semantic fixture.
- [ ] Verify body stream fields remain absent in Mode B runtime evidence.
- [ ] Record the explicit absence of rollback and raw-pose replication claims.
- [ ] Run `python -m pytest backend/tests/test_character_connected_action_profile.py -v` and the relevant Harness profile.

## Completion Criteria

- [ ] Mode B semantic action/control transport is verified end-to-end.
- [ ] Gameplay mirror and future physical body stream have disjoint schemas and handlers.
- [ ] Reconnect, lease expiry, sequence gaps, duplicates, and old epochs are deterministic and fail closed.
- [ ] Mode C remains an explicit future gate with no accidental multiplayer physics claim.
