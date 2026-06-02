# Phase 0.5 Runtime Alignment Design

## Status

- Date: `2026-06-02`
- Scope: `d:\Users\User\Documents\paralls-phase-0-demo`
- Purpose: align the current `Phase 0.5` demo with the main project runtime direction before deeper implementation
- Decision mode: brainstorming-approved design, not implementation

## Problem

The current demo already proves:

- `Phase 0.5 relationship-space demo base`
- one open relationship field
- five-zone layout
- `CharacterReplica` as a shared execution shell
- `A/B/C` on one role-shell substrate
- first-layer `player drives C` through the current `Player` locomotion/camera shell

However, the runtime core is still too demo-local.

The main project already defines stronger canonical directions for:

- character agents
- event bus layering
- Siming
- `ESM`
- visual facts

If `Phase 0.5` keeps growing without aligning to those directions now, later `Phase 1` work will have to undo local shortcuts.

## Design Goal

Turn the current `Phase 0.5` demo into a **Phase-1-shaped minimum runtime slice** without pretending to implement full `Phase 1`.

The target is:

- `Player` continues using the current third-person locomotion and camera path
- `CharacterC` becomes the first genuine player-driven in-world role shell
- backend becomes the real host for:
  - authority-side event routing
  - minimal character runtime state
  - minimal Siming judgment
- Godot remains the host for:
  - local embodiment
  - local presentation
  - local visual fact extraction

## Chosen Approach

Use the **main-project-shaped runtime skeleton** now, but keep the feature surface very small.

This design chooses:

1. `Backend-first authority lane`
2. `room_id + scene_id + zone_id` as real canonical scope fields
3. `dialog_group_id` reserved in the contract but not yet fully activated
4. `visual_fact_event` produced on the Godot side, then sent into the backend authority bus
5. a dedicated backend `conversation / relation compiler`
6. a dedicated backend `character runtime state service`
7. a dedicated backend `Siming minimum judgment service`
8. a Godot-side local presentation lane that consumes sync messages instead of owning truth

## Architecture

### Runtime Topology

The minimum aligned topology is:

`Godot input / embodiment`
-> `Godot local sampling / visual facts`
-> `backend authority event bus`
-> `conversation / relation compiler`
-> `character runtime state service`
-> `Siming minimum judgment service`
-> `character runtime snapshot / delta + siming_output`
-> `Godot local presentation bus`
-> `CharacterReplica / UI / camera-adjacent feedback`

### Responsibility Split

#### Godot

Godot is responsible for:

- player input
- third-person locomotion shell
- camera
- local embodiment execution
- local scene-visible feedback
- local visual fact extraction

Godot is not responsible for:

- world-truth authority
- canonical character runtime state
- canonical Siming judgment
- replay / audit truth source

#### Backend

Backend is responsible for:

- authority event routing
- canonical event envelopes
- character runtime state
- relation compilation
- Siming minimum judgment
- replay / audit truth source

## Event Bus Alignment

### Dual-Bus Position

This design preserves the main-project two-layer bus model:

- backend authority event bus
- Godot local presentation bus

They are connected, but they are not the same bus.

### Canonical Scope

`Phase 0.5` must use these real scope fields:

- `room_id`
- `scene_id`
- `zone_id`

Reserved but not fully activated yet:

- `routing.dialog_group_id`

### Canonical Envelope Fields

All authority-side runtime events should converge on:

- `event_id`
- `event_type`
- `producer_ts`
- `room_id`
- `scene_id`
- `zone_id`
- `source`
- `routing`
- `priority`
- `durability`
- `causation_id`
- `correlation_id`
- `payload`

Canonical source naming should prefer:

- `source.layer`
- `source.system`
- `source.actor_id`
- `source.object_id`

Canonical routing naming should prefer:

- `routing.audience_mode`
- `routing.routing_mode`
- `routing.dialog_group_id`
- `routing.target_ids`

## First Real Visual Facts

### Visual Fact Insertion Point

`visual_fact_event` must follow the main-project direction:

`Godot visible state`
-> `local sampling`
-> `local semantic extraction`
-> `Visual Fact Emitter`
-> `backend authority event bus`

Do not send raw bone streams or raw `AU` streams into the backend business bus.

### First Required Visual Facts

First aligned set:

- `door_opened_partial`
- `object_removed_from_surface`
- `light_level_drop`
- `fixed_gaze_on_target`

### First Required Spatial Relations

First aligned `spatial_relation` set:

- `actor_looks_at_actor`
- `actor_looks_at_object`
- `actor_near_object`

All of `A/B/C` may produce these relations.

However, first real `conversation_candidate_event` production is intentionally constrained so the demo stays centered on `player drives C`.

## Conversation / Relation Compiler

### Runtime Role

Create a dedicated backend `conversation / relation compiler`.

It is not:

- part of Siming
- part of a character agent
- part of Godot local presentation

Its job is to consume authority-side inputs and produce candidate relationship summaries.

### Inputs

First real inputs:

- `spatial_relation`
- `focus_state`
- `world_result`

### First Real Trigger Set

For `Phase 0.5`, first real trigger conditions are constrained to the current demo chain:

- `char_c looks_at char_a`
- `char_c looks_at obj_letter`
- `char_c near obj_letter`

This means:

- `A/B/C` all can emit spatial relations
- but the first real candidate conversation production path is intentionally centered on `char_c`

### Output

The compiler produces:

- `conversation_candidate_event`

It should be:

- `replayable`
- `p1` or `p2`

### First Event Payload

First minimal payload:

- `actor_id`
- `candidate_actor_ids`
- `candidate_object_ids`
- `engagement_pressure`
- `privacy_risk_hint`

The event also carries canonical authority-envelope fields.

### First Consumers

First required consumers:

- character runtime state service
- Siming minimum judgment service
- replay / debug chain

Godot does not consume this event directly in `Phase 0.5`.

## Character Runtime State

### State Ownership

Backend owns the real minimum character runtime state.

Godot receives a synchronized copy for presentation.

### First Required Runtime Fields

The first aligned minimum runtime state is:

- `current_focus_target`
- `current_attention_source`
- `nearby_actor_refs`
- `nearby_object_refs`
- `conversation_candidate_refs`
- `engagement_pressure`
- `privacy_risk_hint`

This is intentionally deeper than a pure focus-only demo state, but still far smaller than full `L2/L3`.

### Sync Shape

Use:

- `character_runtime_state_snapshot`
- `character_runtime_state_delta`

#### Snapshot

Used for:

- initial scene entry
- reconnect
- runtime rebuild

#### Delta

Used for:

- ongoing updates after the snapshot baseline exists

### Sync Granularity

These sync messages are sent **per actor**, not per scene bundle.

### Sync Message Identity

These messages are:

- backend-to-Godot client sync messages

They are not treated as public fact broadcasts, even though they reuse the same canonical envelope frame.

## Siming Minimum Judgment Service

### Runtime Role

Siming in `Phase 0.5` is a real runtime judgment node, but still narrow.

It should consume:

- `conversation_candidate_event`
- key `world_result`
- relevant `visual_fact_event`

It should produce only high-level outcomes.

### First Required Output

First required output remains:

- `siming_output.attention_prompt`

Optional reserved future direction:

- `siming_output.opportunity_hint`

### Hard Limits

Siming must not:

- directly drive low-level motion
- directly write physical truth
- directly inject final beliefs into characters
- replace `ESM`

## Godot Local Presentation

### Consumption

Godot local presentation should continue consuming:

- `dialogue_response`
- `world_result`
- `siming_output`
- `focus_state`
- `character_runtime_state_snapshot`
- `character_runtime_state_delta`

### First Response Layer

The already-written `Phase 0.5` response path stays valid:

- `CharacterReplica` uses player-shell-driven `CharacterC`
- `A/B` can react to `focus_state`
- local response may include:
  - look target shifts
  - short attention posture
  - visible highlight
  - nameplate emphasis

This is the first acceptable aligned embodiment proof for `player drives C`.

## Non-Goals

This design explicitly does not require:

- full character memory implementation
- full `L2` interpretation stack
- full `L3` planning stack
- full `dialog_group` conversation machinery
- full six-event conversation confirmation rollout
- full Siming high-order graph
- full persistent replay platform
- replacement of the `Player` shell with `CharacterC` as the physics root

## Verification Shape

To claim this aligned runtime slice is working, evidence must show:

1. backend tests pass
2. Godot scene loads
3. `Player -> CharacterC` control handoff remains live
4. authority-side events carry `char_c` as the player-driven actor where appropriate
5. `focus_state` can round-trip from backend to Godot
6. at least one other character visibly reacts to `char_c`
7. existing `Phase 0.5` dialogue / interaction / environment / Siming demo path remains intact

## Tradeoff Summary

### Why this approach

- maximizes alignment with the main project
- minimizes future teardown
- keeps authority where the main project expects it
- keeps Godot focused on embodiment and presentation
- keeps the current demo path alive

### What it postpones

- full conversation semantics
- full belief / intent machinery
- deep Siming policy coverage
- full physical-root takeover by `CharacterC`

## One-Sentence Close

`Phase 0.5` should not become a fake pre-Phase-1 shell; it should become a small but real runtime slice where `Player` still reuses the current third-person shell, `CharacterC` already functions as the first player-driven in-world role shell, visual and spatial facts already enter the backend authority bus, relationship candidates already feed both character-state and Siming judgment, and Godot already reacts as a presentation runtime rather than pretending to be the authority host.
