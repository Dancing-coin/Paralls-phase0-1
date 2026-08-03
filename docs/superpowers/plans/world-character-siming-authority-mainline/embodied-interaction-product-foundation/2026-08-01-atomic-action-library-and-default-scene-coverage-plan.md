# Atomic Action Library And Default Scene Coverage Plan

Status: `partially-implemented; waves-1-to-3-planned`

Date: `2026-08-01`

## Scope And Preconditions

This plan executes the companion atomic-action/coverage design. Existing
verified interaction slices are its regression floor, not unfinished work to
reimplement. VLA deep is parked and non-blocking; VLA fast remains advisory
only. TTS, dialogue streaming, and voice-profile work are consumed as
presentation dependencies and are not implementation targets here.

Before each behavior change, add a focused failing test. Do not add a new
dependency or a second action-asset contract.

## Phase 1: Inventory Existing Atoms And Controller Hooks

1. Audit `selected_skill_path`, `primitive_action_tags`, and
   `primitive_realization_keys` emitted by L4 against registered local action
   assets.
2. Extend `CharacterActionAssetDescriptor` / `CharacterEmbodimentAssetRegistry`
   only where a stable atom, root-motion profile, modifier, or equipment
   override is missing.
3. Add controller-to-asset selection tests that prove semantic input does not
   permit a clip to claim authority success.

Exit: every first-wave semantic action has explicit atom metadata or a typed
unavailable route; no controller receives raw motion control input.

Current status: partially implemented. The existing descriptor registry now
resolves requested primitive tags/realization keys and the controller returns
`action_assets_unavailable` for missing reviewed descriptors. The inventory
of every first-wave semantic action is still open.

## Phase 2: Make Controller/Asset Composition Concrete

1. Bind phase-specific atoms to controller phases: approach/align use movement
   atoms; prepare/contact use action atoms; recovery uses recovery atoms.
2. Apply root motion only inside the locally reserved approach/contact window;
   navigation and stance reservation remain the large-displacement owner.
3. Add interruption, missing asset, target motion, and recovery probes.

Exit: a local action can select atoms and recover safely, while all terminal
results remain bounded observations awaiting backend settlement.

Current status: partially implemented. Selection, the missing-asset
precondition, and phase binding are verified: movement/alignment, prepare,
contact, and recovery atoms are separated in the controller trace, and
root-motion profiles are limited to align/prepare/contact/recover local
windows. Per-phase atom playback, CharacterMotor/IK binding, motion-warping
output, and the listed interruption probes remain planned.

## Phase 3: Default Main-Scene Wave 1

1. Inventory current default-scene objects and classify reviewed families:
   seats, doors, switches, tables, and small pickup props.
2. For one family at a time, add registry record, stable scene/entity IDs,
   anchors, colliders, execution profile, observation rule, and authority
   policy. Do not infer an affordance from a Godot node name.
3. Add one success and one structured constraint path per family, plus Godot
   runtime artifacts and replay evidence.

Exit: Wave 1 has evidence-backed coverage by family. Objects outside the
reviewed set stay unavailable rather than pretending to be interactive.

Current status: partially implemented. `obj_letter` remains the first
Godot-runtime-verified default-main-scene fixture. `obj_plaque` uses the same
reviewed bridge contract for `inspect/read`. `obj_lamp_switch` now adds the
first distinct semantic family: explicit `press` dispatch, an ESM-only
`switch: idle -> activated` transition, authority-owned object presentation,
and the approved lamp environment result. All three have grounding refs,
collider/anchors, focused backend success/rejection tests, static scene
binding, and Godot runtime probe evidence. They are semantic fixtures, not
`EmbodiedActionController` physical attempts or pickup/inventory claims.
`obj_archive_door` now has a stateful authority-gated `open_close` route:
the ESM state is scoped by room/scene/zone/object, commits only after its
object result is published, emits `door: closed -> open -> closed`, and rejects
a mismatched state. Occupancy occlusion, navigation blocking, and physical
animation remain planned. Imported scene meshes and all other Wave 1 families
remain unreviewed; their node names alone are insufficient to begin a family
claim. `obj_worktable` now provides the reviewed table-family reference slice:
an ESM-scoped `work_surface: ready -> engaged -> ready` transition with
authority-only local presentation and a state mismatch constraint. It does not
claim a chair pose, shared reservation, ownership, storage, or table animation.
`obj_observation_bench` now provides the reviewed seat-family reference slice:
ESM records the scoped occupant for `available -> occupied -> available`,
allows `stand` only for that occupant, and publishes posture results for the
occupant. It does not claim a seated animation, movement reservation, a
multi-seat allocator, `InteractionSession`, or a character gameplay-state
write model.
`obj_archive_token` now provides the first pickup-family reference slice:
`pickup_intent` carries only normal session/actor context and the reviewed
object ID. The backend-owned policy resolves the asset, source custody, actor
hand target, allowed actor, scene context, and range before reusing the
carry/place authority transaction. A structured rejection leaves both custody
and local display unchanged; a settled authority-only placement directive
changes local presentation. This is custody-only: it does not claim inventory
placement, possession as ownership, hand animation, or generic pickup/place
coverage.

The reviewed scene records now use `ReviewedSceneAffordanceBridge` as their
common bridge type. Each instance still carries an explicit entity, anchor,
affordance, and policy configuration; the common type is contract reuse, not
automatic affordance discovery from a node name or mesh.

## Phase 4: Authority-Gated Wave 2 And Session-Gated Wave 3

1. Add containers, shelves, lights, and room-state controls only after the
   corresponding inventory/ownership or world-state authority writer exists.
2. Add social anchors only through InteractionSession slot/reservation and
   privacy contracts; do not synchronize clips directly.
3. Keep VLA candidate review optional and test known-registry execution with
   VLA disabled, stale, and conflicting.

Exit: local presentation never establishes possession, ownership, room state,
or a shared session outcome.

Current status: backend foundation partially implemented. The inventory runtime now has
an independently verified backend-only container/location core. Carry/place
custody remains a separate authority projection, not an inventory location;
the restricted `stow_intent` is the sole reviewed bridge from the default-scene
pickup policy to that core. The new
`EmbodiedCustodyInventoryAuthorityService` bridges a verified custody holder to
an existing actor container atomically: it writes custody, inventory transfer,
and stow evidence together and rejects bad source/capacity/sealed inputs
without either projection changing. A restricted backend `stow_intent` now
derives the asset, hand source, item definition, and backpack from the reviewed
object policy; it accepts no client container or item references. Repeat calls
replay the already committed transaction before mutable custody validation.
For a backend-tracked hand source, the same batch releases its occupancy; a
generic custody source with no tracked occupancy does not acquire a fabricated
scene event.
The transport emits accepted-only `authority_only` presentation directives;
the Godot bridge consumes the stow directive only as a stowed marker, and
`submit_stow()` is a reviewed-source-only command surface. The next retrieve
reference is now wired through `obj_archive_storage_chest`: `retrieve_intent`
contains only the reviewed chest object ID and standard context, while the
backend policy resolves the actor backpack, fixed token item, definition, and
empty hand receiver before calling the existing `retrieve_to_custody`
foundation. Its accepted result restores only a local carried marker; it does
not expose a container UI, client-selected inventory refs, hand animation, or
generic storage action. The internal authority batch still commits custody,
inventory-out, receiver occupancy, and evidence together. Do not expose it as
a direct Godot mutation or a second unlinked transaction after carry/place
settlement. Durable inventory-view delivery and generic multi-item/container
policies remain planned.

## Verification

Run focused tests for each changed asset/controller/registry family, then:

```powershell
python scripts/verification/harness.py --profile embodied-interaction-foundation-all
python scripts/verification/harness.py --profile vla-provider-backend
python scripts/verification/harness.py --profile mainline-unified-runtime
python scripts/verification/harness.py --profile docs
```

Run `python scripts/verification/harness.py --profile all` only after all
changed predecessor profiles pass and fresh evidence is retained.
