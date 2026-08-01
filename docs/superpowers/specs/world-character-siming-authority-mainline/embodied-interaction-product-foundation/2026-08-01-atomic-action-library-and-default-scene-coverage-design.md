# Atomic Action Library And Default Scene Coverage Design

Status: `implementation-active; coverage-expansion-planned`

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
- `SceneAffordanceRegistry`, bridge attestation, authority settlement, replay,
  interaction sessions, handoff, and grab-carry-place have focused evidence.
- The default scene is not comprehensively covered: the verified objects and
  action profiles are narrow reference slices, not a claim that every object
  has embodied interaction.

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
| 1 | Seats, doors, switches, tables, and small pickup props in the default main scene | `approach`, `align`, `sit_or_use`, `open_close`, `press`, `grab/place` where registered | One success and one structured constraint result per family. |
| 2 | Containers, shelves, lights, and room-state controls | `open_close`, `inspect`, `store/retrieve` only after the owning authority slice exists | No local attachment or visual mutation becomes possession/world truth. |
| 3 | Social anchors and multi-participant objects | `handoff`, session-gated social slots | Requires interaction-session and privacy evidence; high-precision clips remain deferred. |

Unregistered default objects remain non-interactive or return a structured
unavailable result. “Looks reachable” is not an affordance grant.

## Non-goals

- General motion generation, remote bone streaming, or full-body VLA control.
- Making all existing scene nodes interactive in one migration.
- Replacing the current TTS/dialogue streaming boundary; audio remains a
  presentation attachment to completed dialogue text.
- Inventory, ownership, economy, or full gameplay-state implementation beyond
  their existing authority-gated slices.

## Acceptance And Evidence

1. A semantic action maps through existing realization metadata to reviewed
   local atoms without changing CharacterAgent or authority ownership.
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
