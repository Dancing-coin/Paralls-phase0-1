# Atomic Action Library And Default Scene Coverage Plan

Status: `implementation-active; waves-1-to-3-planned`

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

## Phase 2: Make Controller/Asset Composition Concrete

1. Bind phase-specific atoms to controller phases: approach/align use movement
   atoms; prepare/contact use action atoms; recovery uses recovery atoms.
2. Apply root motion only inside the locally reserved approach/contact window;
   navigation and stance reservation remain the large-displacement owner.
3. Add interruption, missing asset, target motion, and recovery probes.

Exit: a local action can select atoms and recover safely, while all terminal
results remain bounded observations awaiting backend settlement.

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

## Phase 4: Authority-Gated Wave 2 And Session-Gated Wave 3

1. Add containers, shelves, lights, and room-state controls only after the
   corresponding inventory/ownership or world-state authority writer exists.
2. Add social anchors only through InteractionSession slot/reservation and
   privacy contracts; do not synchronize clips directly.
3. Keep VLA candidate review optional and test known-registry execution with
   VLA disabled, stale, and conflicting.

Exit: local presentation never establishes possession, ownership, room state,
or a shared session outcome.

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
