# Atomic Action Library And Default Scene Coverage Design

Status: `partially-implemented; coverage-expansion-planned`

Date: `2026-08-01`

## Purpose

This design formally takes the 2026-08-01 input record into the mainline
embodied-interaction tree. It turns existing semantic skill output, action
asset contracts, local controller phases, and reviewed scene affordances into
one incremental coverage route for default main-scene objects.

It does not replace the existing controller, settlement, VLA, dialogue, or
TTS designs. It specifies how their already separate responsibilities compose.

## Current Code Facts

- `CharacterActionAssetDescriptor` and `CharacterEmbodimentAssetRegistry`
  already provide the sole local action-asset contract. `selected_skill_path`,
  `primitive_action_tags`, and `primitive_realization_keys` are carried from
  CharacterAgent L4 output into realization metadata.
- `EmbodiedActionController` already owns the local attempt state machine,
  navigation/alignment/contact observation, cancellation, and recovery. It
  does not settle authority results.
- `CharacterEmbodimentAssetRegistry.resolve_action_atoms()` now resolves L4
  primitive tags/realization keys through that existing descriptor contract.
  `EmbodiedActionController` consumes the selected local atoms before its
  attempt phases and returns the bounded local `action_assets_unavailable`
  precondition when a requested atom is absent. This is local realization
  evidence, not a backend settlement or a broad clip-execution system.
- The controller now binds reviewed atoms to local phases: movement to
  approach/navigation/alignment, upper-body to prepare, contact atoms to
  `execute_contact`, and recovery atoms to `recover`. Root-motion profile refs
  are exposed only for bounded local align/prepare/contact/recover windows;
  this binding does not transform world truth or execute a production clip
  graph.
- `SceneAffordanceRegistry`, bridge attestation, authority settlement, replay,
  interaction sessions, handoff, and grab-carry-place have focused evidence.
- `ReviewedSceneAffordanceBridge` is now the reusable scene bridge type for
  the reviewed `MainDemo` records. The legacy letter-named script remains its
  compatibility implementation, while each instance still supplies explicit
  entity, anchor, affordance, and policy configuration. The type does not
  infer a family from a node name or mesh.
- The default `MainDemo` contains Godot-runtime-verified `obj_letter` and
  `obj_plaque` `inspect/read` fixtures, an `obj_lamp_switch` `press` fixture,
  an `obj_archive_door` `open_close` fixture, an `obj_worktable` stateful
  `use` / `finish_use` fixture, and an `obj_observation_bench` stateful
  `sit` / `stand` fixture. Each has stable grounding refs, a
  local collider/anchors, a local registry preflight, an explicit ESM policy,
  and authority-only `object_state_result` presentation. The switch emits
  `switch: idle -> activated` plus its approved lamp result; the stateful door
  policy emits `door: closed -> open -> closed` and rejects a mismatched state.
  All six have focused success/rejection, static binding, WebSocket policy
  (for switch and door), and Godot runtime evidence.
- `obj_archive_token` is the first default-main-scene pickup reference slice.
  Godot sends only a structured `pickup_intent` with a reviewed object ID;
  `DefaultScenePickupPolicyService` resolves the asset, source custody,
  allowed actor, scene context, range, and actor hand target on the backend.
  The existing carry/place authority transaction then emits an authority-only
  placement directive. Godot hides or optionally attaches the prop only after
  that event. This proves custody/presentation, not inventory placement,
  ownership transfer, a hand animation, or a generic pickup system.
- The first restricted custody-to-inventory continuation is now implemented
  behind `stow_intent`. Its policy resolves asset, item definition, source
  hand custody, and destination backpack server-side; one atomic batch writes
  custody change, inventory transfer-in, and stow evidence. A duplicate command
  replays before mutable custody validation. The Godot runtime probe verifies
  its accepted-only local stowed marker, but there is no scene container or
  inventory view.
- The default scene is not comprehensively covered: the verified objects and
  action profiles are narrow reference slices, not a claim that every object
  has embodied interaction.

## Implementation Status

### Implemented And Verified Foundation

- Existing realization metadata is resolved through the sole action-asset
  registry; no parallel asset contract was added.
- The controller rejects a requested primitive with the typed local
  `action_assets_unavailable` precondition when no reviewed local descriptor
  can realize it.
- The controller/registry composition is exercised by the Godot
  `embodied-action-controller` verification profile, alongside its static
  regression tests.

### Implemented But Limited Slice

- Selection and phase binding prove descriptor resolution, typed unavailability,
  and which local phase may consume a reviewed atom/profile. They do not yet
  execute a production clip graph or bind the descriptors to CharacterMotor,
  IK, or motion-warping runtime output.
- Existing chair, carry, and handoff fixtures remain focused reference slices,
  rather than default-main-scene family coverage.
- `obj_letter` and `obj_plaque` are Godot-runtime-verified default-main-scene
  readable fixed-prop fixtures, `obj_lamp_switch` is the room-control `press`
  fixture, `obj_archive_door` is the stateful door `open_close` fixture, and
  `obj_worktable` is the stateful single-actor `use` / `finish_use` fixture.
  `obj_observation_bench` is the actor-scoped seat fixture: it records an
  authority occupant, rejects a non-owner `stand`, and emits posture results
  for `standing -> seated -> standing`. These cover authority-owned semantic
  `inspect/read`, `press`, `open_close`, work-surface state transitions, and
  a bounded seat occupancy transition, not
  controller-granted physical execution, possession, pickup semantics, door
  occlusion, navigation blocking, or physical door animation.
- `obj_archive_token` is the custody-only pickup fixture. It rejects unknown
  targets, unallowed actors, context/range failures, unsafe payload fields,
  source-custody mismatch, and occupied hand targets before local presentation
  changes. It reuses the carry/place transaction rather than creating an
  independent inventory or ownership writer.
- The same token has a backend-and-WebSocket-verified restricted `stow_intent`
  continuation. It accepts no client asset, item definition, source custody, or
  destination container reference. The accepted command atomically moves its
  existing hand custody into the policy-resolved backpack inventory location
  and publishes only an `authority_only` presentation marker. The local
  consumer records neither inventory truth nor ownership; its Godot runtime
  probe verifies directive filtering and the local `carried -> stowed` marker.

### Still Not Started

- Beyond the two readable fixed-prop fixtures, one switch fixture, one
  stateful door fixture, one single-actor worktable fixture, one actor-scoped
  bench fixture, one custody-only pickup fixture, and one restricted storage
  chest retrieve fixture, no other reviewed Wave 1 default-main-scene family
  has stable entity IDs, anchors/colliders, registry records, authority policy,
  and visible success/constraint evidence.
- Waves 2 and 3 remain gated on their owning authority and session contracts.

## Ownership Model

```text
Character mind / skill evaluation
  -> semantic action + selected_skill_path
  -> primitive action tags / realization keys
  -> backend authority preflight and route selection
  -> EmbodiedActionController local execution
       -> asset atoms, CharacterMotor, navigation, IK / motion warping
  -> bounded local observation
  -> backend authority settlement
```

The controller decides where to stand, when an action can enter its contact
window, whether local execution must stop, and how to recover. The action
library supplies atomic assets, root-motion profiles, modifiers, equipment
overrides, and expressive overlays. Neither replaces the other.

## Action Layers

1. **Semantic layer**: `approach`, `align`, `kick`, `grab`, `place`, and
   `handoff`. These are selected by the character/authority path and remain
   structured intent, not animation clip names.
2. **Atomic layer**: locally addressable action fragments with stable tags and
   realization keys. The first catalog contains:
   - movement: `start_move`, `stop_move`, `turn_to_target`, `step_left`,
     `step_right`, `backstep`;
   - upper body: `raise_hand`, `reach_forward`, `grip`, `release`,
     `offer_item`, `receive_item`;
   - contact: `kick_contact`, `push_contact`, `tap_contact`, `brace_contact`;
   - recovery: `recover_balance`, `reset_guard`, `return_idle`,
     `abort_contact`.
3. **Local execution layer**: `EmbodiedActionController`, `CharacterMotor`,
   navigation, stance reservation, animation state, IK, motion warping, and
   local observation. It owns local high-frequency realization only.

The existing `CharacterActionAssetDescriptor` and
`CharacterEmbodimentAssetRegistry` remain the only asset contract. New action
work must extend `action_tag`, `root_motion_profile`, `modifier_profile`,
`equipment_override`, `selected_skill_path`, `primitive_action_tags`, and
`primitive_realization_keys`; it must not introduce a parallel asset registry.

## Spatial And Authority Rules

- Controller navigation and stance reservation own large displacement and
  spatial feasibility.
- Root motion contributes only bounded local displacement, rhythm, and
  pre/post-contact expression. It never owns the full spatial truth of an
  attempt.
- IK and motion warping may align a local atom to a reviewed anchor. They may
  not create an unreviewed target, bypass a stance reservation, or revise the
  backend world result.
- Only backend authority accepts/rejects the outcome and publishes world state.
  A finished local clip or controller phase is not a settlement.
- VLA remains optional advisory input. It cannot select an atom, steer a
  controller, activate a scene affordance, or write world truth.

## Default Main-Scene Coverage Route

Coverage is driven by reviewed affordances, not by node-name inference. Each
new object family requires a scene record, anchors/colliders, local execution
profile, observation rule, authority policy, success/failure tests, and a
scene-visible authority-only presentation response.

| Wave | Object families | Required semantic coverage | Exit boundary |
| --- | --- | --- | --- |
| 0 | Existing chair and carry/handoff fixtures | `kick`, `grab`, `carry`, `place`, `handoff` | Preserve existing focused evidence; no broad-coverage claim. |
| 1 | Runtime-verified `obj_letter` and `obj_plaque` `inspect/read`, `obj_lamp_switch` `press`, `obj_archive_door` `open_close`, `obj_worktable` `use` / `finish_use`, `obj_observation_bench` `sit` / `stand`, and `obj_archive_token` `grab`; remaining small pickup props | `inspect/read` for readable fixed props, authority-gated `press`, stateful authority-gated `open_close`, a stateful single-actor work-surface transition, actor-scoped bench occupancy with posture results, and backend-resolved custody-only pickup; local approach/alignment, seated animation, shared seat reservations, hand animation, and generalized `grab/place` remain planned | Seven fixtures have focused success/constraint and Godot evidence. The token does not establish inventory, ownership, generic hand attachment, or a generalized pickup contract. Door occlusion, navigation blocking, physical animation, table seating/shared occupancy, and seat animation/session semantics are not included. |
| 2 | Reviewed archive storage chest; then containers, shelves, lights, and room-state controls | The chest supports one policy-resolved `retrieve`; further `open_close`, `inspect`, `store/retrieve` require their owning authority slices | The chest does not establish a generic container contract; no local attachment or visual mutation becomes possession/world truth. |
| 3 | Social anchors and multi-participant objects | `handoff`, session-gated social slots | Requires interaction-session and privacy evidence; high-precision clips remain deferred. |

Unregistered default objects remain non-interactive or return a structured
unavailable result. “Looks reachable” is not an affordance grant.

### Container And Possession Gate

The repository now has a backend-only `InventoryAuthorityService` reference
core for actor-scoped containers, sealed/capacity rejection, and replayed item
location. It is not yet a default-scene writer. In particular,
`EmbodiedCarryPlaceAuthorityService` records physical custody at a holder ref;
that holder ref is not an inventory container and must not be treated as proof
of possession, ownership, or an item-location transfer.

`EmbodiedCustodyInventoryAuthorityService` now supplies the first atomic
cross-domain append boundary: `stow_from_custody` commits custody change,
inventory transfer-in, and stow evidence in one transaction, then refreshes
the custody read model only after commit. It preserves item uniqueness,
container existence, sealed/capacity rejection, source-custody validation,
and replay of the same committed command before mutable custody checks. The
restricted `stow_intent` reference route is now implemented: normal actor and
scene context plus a reviewed object ID are its only client inputs; the
backend-owned pickup policy resolves the asset, item definition, hand source,
and actor backpack. Its accepted result contains an `authority_only` local
  presentation directive, while rejection sends no directive. The Godot probe
  verifies that unsafe directives leave its local state unchanged and only an
  accepted authority-only directive advances `carried -> stowed`.

When the source holder has a backend-tracked physical occupancy projection,
the same batch also writes `scene.occupancy.changed` to release that source and
only then refreshes the in-memory hand projection. A generic custody holder
without such a projection remains a valid three-event path; the inventory
service does not infer scene occupancy from holder-ref text.

This is a narrow backend-and-transport reference, not a completed
default-scene container/retrieve family. The local bridge can mark the reviewed
prop as stowed only after that accepted directive; it does not write an
inventory, custody, ownership, attachment, or world state.

`obj_archive_storage_chest` now supplies one reviewed retrieve reference. Its
`retrieve_intent` contains only normal session/actor context and the reviewed
container object ID. The backend policy resolves the fixed archive-token item,
actor backpack source, expected definition, and empty hand receiver before it
calls `retrieve_to_custody`. A success atomically writes custody, inventory-out,
receiver occupancy, and retrieval evidence; the only Godot-facing result is an
accepted `authority_only` carried marker. It is not container browsing, a
client-selected item/container/receiver route, a generic storage system,
inventory UI, hand animation, ownership transfer, or a proof of a scene-visible
chest open/close state.

The inverse `retrieve_to_custody` foundation is now backend-verified but has
no default-scene route. A policy/settlement layer must supply its actor
container, item identity, and registered empty receiver; it atomically writes
custody, inventory transfer-out, receiver occupancy, and retrieve evidence.
It preserves the item instance and removes only its actor-inventory location.
It does not license a client-selected retrieve target, a scene container,
generic world placement, Godot inventory delivery, or an ownership write.

Before a broader default-scene container/retrieve family is implemented, its
authority route must provide reviewed container affordances, source access and
retrieve policy bindings to the internal foundation, durable inventory view
delivery, and scene-visible evidence. Direct
Godot writes, a client-selected container ID, and an unlinked second
transaction remain rejected designs.

## Non-goals

- General motion generation, remote bone streaming, or full-body VLA control.
- Making all existing scene nodes interactive in one migration.
- Replacing the current TTS/dialogue streaming boundary; audio remains a
  presentation attachment to completed dialogue text.
- Inventory, ownership, economy, or full gameplay-state implementation beyond
  their existing authority-gated slices.

## Acceptance And Evidence

1. A semantic action maps through existing realization metadata to reviewed
   local atoms without changing CharacterAgent or authority ownership. The
   currently verified portion is asset selection, typed unavailability, and
   bounded phase binding; phase-specific clip execution remains planned.
2. A controller uses large-scale navigation/stance data before bounded
   root-motion/IK adjustment, and reports typed recovery on interruption.
3. Every newly covered object family has one authoritative success and one
   structured failure visible in the scene, with replayable IDs.
4. Disabling VLA or receiving stale/conflicting VLA advice does not prevent a
   known registry path from completing.
5. Existing `embodied-interaction-foundation-all`, `vla-provider-backend`,
   dialogue, TTS, Siming, and mainline regressions remain green.

## Related Formal Documents

- `2026-07-29-embodied-action-controller-and-local-observation-design.md`
- `2026-07-29-scene-affordance-registry-design.md`
- `../../2026-06-29-asset-runtime-and-kimodo-adapter-design.md`
- `../../../current-project-intelligence-upgrade/2026-07-30-advisory-vla-routing-and-tts-convergence-design.md`
- `../../2026-07-29-character-dialogue-streaming-design.md`
- `../../2026-07-29-real-tts-provider-presentation-design.md`
