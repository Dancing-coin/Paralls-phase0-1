# L1 Raw Fact Emitter Design

## Status

- Status: draft design for Phase 0 -> Phase 1 compatible migration
- Date: 2026-06-06
- Scope: `D:\Users\User\Documents\paralls-phase-0-demo`
- Upstream truth:
  - `D:\Projects\Paralls\docs\phase1\core\00-总纲\L1层架构初稿.md`
  - `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\视觉事实系统\12-M1-M2 Godot端类接口契约.md`
  - `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\事件总线\07-视觉事实系统接入总线规范.md`
  - `D:\Projects\Paralls\docs\superpowers\specs\2026-05-28-conversation-membership-and-privacy-design.md`

## 1. Goal

This design upgrades the current Phase 0 visual fact slice into a broader `L1` raw-fact emitter skeleton without breaking the existing demo loop.

The design must satisfy both constraints:

1. Keep the current repo runnable with its existing `VisualFactEmitter -> backend -> runtime/siming` chain.
2. Create a stable `L1` fact-production surface that can later absorb conversation/privacy/access facts without inventing a second pipeline.

This design does **not** implement:

- full Phase 1 event bus
- full conversation membership engine
- full Siming high-order knowledge graph
- full eight-family fact emitter rollout

## 2. Frozen Boundaries

### 2.1 L1 responsibilities

`L1` is responsible for:

- detecting that a low-level fact has become true in local runtime
- packaging that fact into a structured raw fact object
- sending that raw fact across the Godot -> backend boundary

`L1` is **not** responsible for:

- conversation membership conclusions
- mutual-knowledge confirmation
- exclusion / rejoin decisions
- narrative meaning
- evidence interpretation

### 2.2 Cross-layer sequence

The sequence must remain:

`fact production -> fact transport -> higher-order inference`

Concretely:

- Godot `L1` produces raw facts
- backend ingress transports and routes them
- runtime projection / Siming / future session-knowledge services interpret them

### 2.3 Phase 0 compatibility rule

No migration step may break the current verified Phase 0 slices:

- `fixed_gaze_on_target`
- `actor_near_object`
- `light_level_drop`
- backend runtime projection from visual facts
- minimal Siming attention prompt from environment visual fact

## 3. Current State

The current repo already contains a narrow `L1` slice:

- Godot emits `visual_fact_event`
- backend consumes it directly in `backend/app/main.py`
- `ConversationRelationService` projects it into runtime state and conversation candidate hints
- `SimingService` consumes selected visual facts

Files currently carrying this slice:

- `scripts/visual/VisualFactEmitter.gd`
- `scripts/phase0/MainDemoController.gd`
- `scripts/environment/EnvironmentStateController.gd`
- `backend/app/models/visual_fact.py`
- `backend/app/main.py`

The main structural problem is that the current chain is too specialized:

- it assumes every future fact is a visual fact
- controller files both detect facts and shape transport payloads
- backend routing is hardcoded on `message_type`

## 4. Target Architecture

### 4.1 Runtime chain

The target `L1` chain is:

`Scene Runtime / ESM callback -> Sampler -> Fact Adapter -> RawFactEmitter -> Backend Fact Ingress -> Fact Router -> Consumer`

### 4.2 Layer roles

#### Sampler

Sampler lives near scene/runtime code and answers only:

- did a fact become true?
- what local runtime values describe it?

Examples in this repo:

- focused actor/object gaze settled
- player is close enough to target object
- environment state changed to alerted/dimmed
- actor crossed a zone boundary

#### Fact Adapter

Adapter converts local runtime data into a structured fact object.

Adapter responsibilities:

- normalize field names
- select `fact_family`, `fact_type`, and `relation_type`
- fill source/target/world/observability payloads

Adapter non-responsibilities:

- sending over bridge
- dedupe policy
- backend routing
- high-order interpretation

#### RawFactEmitter

This is the only Godot-side cross-boundary fact transport surface.

Responsibilities:

- build final envelope
- apply dedupe/throttle
- send through `BackendBridge`
- write debug messages to `LocalPresentationBus`

Non-responsibilities:

- local scene sampling
- taxonomy decisions at call sites
- backend-specific business logic

#### Backend Fact Ingress

Backend ingress receives a single generalized raw-fact message type and parses it into `RawFactEvent`.

#### Fact Router

Fact router dispatches by `fact_family`, not by top-level `message_type`.

Consumers in Phase 0:

- visual fact handler
- spatial access fact handler
- future environment execution fact handler

## 5. Minimal Fact Families

This design intentionally freezes only three fact families for now.

### 5.1 `visual_fact`

Purpose:

- visible facts already proven in Godot runtime

Initial fact types:

- `fixed_gaze_on_target`
- `spatial_relation`
- `light_level_drop`

Initial relation types:

- `actor_looks_at_actor`
- `actor_looks_at_object`
- `actor_near_object`
- `environment_light_drop`

### 5.2 `spatial_access_fact`

Purpose:

- low-level access/privacy/conversation-entry evidence

Initial fact types:

- `actor_entered_zone`
- `actor_left_zone`
- `actor_proximity_changed`
- `privacy_boundary_changed`
- `occlusion_boundary_changed`
- `door_state_changed`

Initial relation types:

- `actor_approached_actor`
- `actor_moved_away_from_actor`
- `public_to_local`
- `local_to_private`
- `private_to_local`
- `line_of_sight_blocked`
- `line_of_sight_cleared`
- `door_opened`
- `door_closed`

Important boundary:

These facts support future membership/privacy logic, but do not themselves state:

- `candidate_member`
- `passive_member`
- `excluded`
- `mutual_knowledge_confirmed`

### 5.3 `environment_execution_fact`

Purpose:

- world execution results that already became true in environment/object state

Initial fact types:

- `object_state_changed`
- `environment_state_changed`
- `interaction_blocked`

Initial relation types:

- `object_interaction_succeeded`
- `environment_shift_applied`
- `constraint_rejected`

## 6. Canonical Message Shape

The backend should converge on a single top-level message type:

- `message_type = "raw_fact_event"`

Payload contract:

```json
{
  "event_type": "raw_fact_event",
  "fact_family": "spatial_access_fact",
  "fact_type": "actor_proximity_changed",
  "relation_type": "actor_approached_actor",
  "producer_ts": 0,
  "room_id": "",
  "scene_id": "",
  "zone_id": "",
  "source": {
    "layer": "L1",
    "system": "godot.raw_fact_emitter",
    "actor_id": "",
    "object_id": "",
    "environment_id": ""
  },
  "targets": {
    "actor_id": "",
    "object_id": "",
    "environment_id": ""
  },
  "world": {
    "position": null,
    "distance_m": null,
    "state_before": "",
    "state_after": ""
  },
  "observability": {
    "visual": false,
    "auditory": false,
    "occluded": false
  },
  "causation_id": "",
  "correlation_id": ""
}
```

Design notes:

- keep `relation_type` because the current repo already uses it meaningfully
- keep `source` and `targets` separate to avoid future flat-field drift
- keep `world.state_before/state_after` so environment and privacy transitions can reuse the same schema
- do not introduce the full future event-bus envelope yet; Phase 0 does not need it

## 7. Godot File Layout

Target Godot-side file structure:

```text
scripts/l1/facts/
  RawFactEmitter.gd
  FactEnvelopeBuilder.gd
  FactDeduper.gd
  emitters/
    CharacterVisualFactEmitter.gd
    EnvironmentVisualFactEmitter.gd
    SpatialAccessFactEmitter.gd
  adapters/
    VisualFactAdapter.gd
    SpatialAccessFactAdapter.gd
    EnvironmentExecutionFactAdapter.gd
```

### 7.1 `RawFactEmitter.gd`

Responsibilities:

- accept normalized fact dictionary
- call `FactEnvelopeBuilder`
- call `FactDeduper`
- send envelope via `BackendBridge`
- write local debug logs

### 7.2 `FactEnvelopeBuilder.gd`

Responsibilities:

- fill `message_type`
- fill `event_type`
- merge common context fields

### 7.3 `FactDeduper.gd`

Responsibilities:

- protect against noisy repeated fact bursts
- handle cooldown/dedupe windows for facts such as:
  - `actor_near_object`
  - `actor_approached_actor`
  - `door_state_changed`
  - `privacy_boundary_changed`

### 7.4 `CharacterVisualFactEmitter.gd`

Initial methods:

- `emit_fixed_gaze_on_actor(...)`
- `emit_fixed_gaze_on_object(...)`

### 7.5 `EnvironmentVisualFactEmitter.gd`

Initial methods:

- `emit_light_level_drop(...)`
- `emit_door_visual_state_changed(...)`

### 7.6 `SpatialAccessFactEmitter.gd`

Initial methods:

- `emit_actor_entered_zone(...)`
- `emit_actor_left_zone(...)`
- `emit_actor_approached_actor(...)`
- `emit_actor_moved_away_from_actor(...)`
- `emit_privacy_boundary_changed(...)`
- `emit_occlusion_boundary_changed(...)`

## 8. Backend File Layout

Target backend-side file structure:

```text
backend/app/models/
  raw_fact.py
backend/app/services/
  fact_router.py
  fact_handlers/
    visual_fact_handler.py
    spatial_access_fact_handler.py
```

### 8.1 `raw_fact.py`

Defines:

- `RawFactSource`
- `RawFactTargets`
- `RawFactWorld`
- `RawFactObservability`
- `RawFactEvent`

### 8.2 `fact_router.py`

Responsibilities:

- route by `fact_family`
- isolate `backend/app/main.py` from growing fact-family branching

### 8.3 `visual_fact_handler.py`

Responsibilities:

- preserve the current visual-fact behavior
- feed runtime projection
- feed conversation candidate hints
- feed minimal Siming visual-fact path

### 8.4 `spatial_access_fact_handler.py`

Responsibilities in Phase 0:

- maintain a minimal access snapshot
- expose raw access evidence to runtime and Siming

Allowed state examples:

- current zone id
- nearby actor refs
- privacy band
- latest access fact timestamp

Not allowed in Phase 0:

- final membership state
- mutual-knowledge confirmation
- exclusion resolution

## 9. Migration Plan

### Stage A: unify transport surface

Actions:

- convert current `VisualFactEmitter` role into generalized fact emitter behavior
- keep existing fact semantics unchanged

Success condition:

- current visual-fact tests still pass

### Stage B: introduce emitter/adapters

Actions:

- move payload shaping out of controllers
- keep controllers as samplers/triggers

Success condition:

- `MainDemoController` and `EnvironmentStateController` stop building transport payloads directly

### Stage C: introduce backend fact ingress + router

Actions:

- add `raw_fact_event`
- add `RawFactEvent` model
- add `fact_router`

Success condition:

- backend can accept routed raw facts without losing current visual behavior

### Stage D: add first spatial access slice

Actions:

- implement the smallest useful `spatial_access_fact` subset

Required first facts:

- `actor_entered_zone`
- `actor_approached_actor`
- `privacy_boundary_changed`

Success condition:

- L1 now emits raw access/privacy evidence through the same pipeline as visual facts

## 10. Initial Acceptance Criteria

This design is successful when all of the following are true:

1. Existing Phase 0 visual fact chain still works:
   - gaze -> visual fact -> runtime projection
   - near object -> candidate/runtime hint
   - environment light drop -> Siming attention prompt
2. Godot has exactly one generalized raw-fact transport surface to backend.
3. Controller files no longer construct cross-boundary payloads directly.
4. Backend routing no longer depends on adding one new top-level message type per fact family.
5. At least one spatial access/privacy raw fact can be emitted without inventing a second pipeline.

## 11. Explicit Non-Goals

This design does not attempt to solve:

- full event-bus public envelope parity with the main repo
- full hearing-fact family
- full conversation membership engine
- full replay/audit event identity model
- full Godot-side visual fact subsystem from the main repo contracts

## 12. Current Session Note

Godot MCP Pro was not available in the current Codex session environment:

- no Godot MCP tools were exposed through tool discovery
- the local Codex MCP config showed only OMX servers
- no local Godot MCP Pro package or command was found in the checked standard locations

So this design was grounded through repository inspection and upstream source documents, not through live Godot MCP editor/runtime inspection.
