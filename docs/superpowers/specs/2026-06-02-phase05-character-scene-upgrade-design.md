# Phase 0.5 Character And Scene Upgrade Design

## Status

- Date: `2026-06-02`
- Scope: current `paralls-phase-0-demo` project only
- Purpose: upgrade the current `Phase 0` demo into a stronger `Phase 0.5` base for character execution and scene structure
- Approval source: current user thread

## Design Goal

Upgrade the current demo in two full lines at the same time:

1. `Character line`
   - turn the current character replicas into one unified execution base that can support both:
     - `A/B` as AI-driven in-world characters
     - `C` as a player-driven in-world character
   - keep all three on the same character-agent foundation

2. `Scene line`
   - turn the current open greybox field into a semi-formal relationship space that supports:
     - `A` controlling the key object
     - `B` observing the situation
     - `C` entering as the player-driven intervener

This is not a Phase 1 implementation. It is a stronger demo base that reduces rework before Phase 1.

## Frozen Narrative Relationship

The relationship model is now frozen as:

- `A`: controlling the key object
- `B`: observing `A` and the key object
- `C`: player-driven intervener entering an already established tension field

This relationship must drive both the character architecture and the scene layout.

## Source-Of-Truth Alignment

This design explicitly follows the main-project documents instead of inventing a local-only model.

### Character truth

The main-project character design freezes the following:

- all in-world characters share one unified character-agent foundation
- `AI` characters and `player projection` characters do not use different base systems
- the key difference is who currently holds high-level initiative

Relevant source documents:

- [01-角色智能体总纲.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/角色智能体/01-角色智能体总纲.md)
- [08-玩家接管、挂机接管与旅人-角色边界设计.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/角色智能体/08-玩家接管、挂机接管与旅人-角色边界设计.md)
- [07-L4执行层与具身表达总纲.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/角色智能体/07-L4执行层与具身表达总纲.md)
- [19-角色智能体与事件总线契约.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/角色智能体/19-角色智能体与事件总线契约.md)

### Event-bus truth

The main-project event-bus design freezes the following:

- backend authority and Godot local presentation are not the same bus
- characters should not directly consume raw global facts
- characters should consume filtered per-character perception inputs and emit structured behavior outputs

Relevant source documents:

- [01-事件总线总纲.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/事件总线/01-事件总线总纲.md)
- [03-Godot本地表现总线设计.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/事件总线/03-Godot本地表现总线设计.md)
- [04-感知链路与候选事件设计.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/事件总线/04-感知链路与候选事件设计.md)
- [19-角色智能体与事件总线契约.md](/d:/Projects/Paralls/docs/phase1/core/01-运行时核心/角色智能体/19-角色智能体与事件总线契约.md)

## Reuse-First Rule

This upgrade must prefer copying, adapting, or vendoring focused main-project documents and support files into the demo project instead of re-describing the same architecture from scratch.

### Explicit reuse policy

Allowed and recommended:

- copy selected design documents from the main project into a local `docs/reference/` or similar demo-safe reference folder
- copy small schema or contract fragments when the demo needs local, versioned copies
- mirror the naming and folder structure of the main character-agent and event-bus documents where that reduces drift

Not allowed:

- re-implementing Phase 1 architecture wholesale inside the demo
- importing the entire main docs tree without a scoped selection
- creating a second conflicting local truth for driver modes, L4 channels, or event-bus audience rules

## Character Upgrade Design

### 1. Unified execution base

The current [CharacterReplica.gd](/d:/Users/User/Documents/paralls-phase-0-demo/scripts/character/CharacterReplica.gd:1) already acts as a minimal execution shell, but it is still too demo-specific.

It must evolve into a stable unified execution base for all in-world characters:

- `A`
- `B`
- `C`

It should no longer be treated as “AI shell only.”

### 2. Two driving modes on one base

The execution base must support at least two explicit driver modes:

- `ai`
- `player`

#### AI mode

Used by:

- `A`
- `B`

Meaning:

- high-level initiative comes from the backend character-agent side
- Godot executes movement, orientation, action playback, posture, voice, and spatial response

#### Player mode

Used by:

- `C`

Meaning:

- player takes over the active `L3/L4` initiative surface
- the shared role substrate still preserves:
  - role continuity
  - micro-expression and micro-motion support hooks
  - future idle/afk conservative handoff hooks
  - social-spatial and physiology auto layers

This is the core standard-version requirement. `C` is not a separate “normal game player object.” `C` is a driven in-world character on the same role-agent substrate.

### 3. L4-oriented execution structure

The execution base should align with the main-project L4 channel split, even if the demo only implements a reduced subset.

Main-project L4 channels:

- `Speech Channel`
- `Face Channel`
- `Body Channel`
- `Social-Spatial Channel`
- `Physiology Channel`

The demo does not need all channels fully implemented, but the local execution base should be shaped so it can grow in that direction without being rewritten.

### 4. Minimal execution interface surface

The local unified execution base should move toward explicit control entrypoints such as:

- `set_driver_mode(mode)`
- `set_move_target(target)`
- `clear_move_target()`
- `set_look_target(target)`
- `perform_action(action_spec)`
- `interrupt_action()`
- `set_attention_state(spec)`
- `set_social_spatial_state(spec)`

The exact method names can still be finalized later, but the architecture should shift from demo callbacks and patrol-only logic toward a stable execution API.

### 5. mixabridge role

`mixabridge` is not just a visual polish addon in this plan. It is the main bridge for turning the current shell into a reusable character execution substrate.

It should be used for:

- skeleton discovery
- bone map generation
- character asset normalization
- animation scene extraction
- future shared action playback preparation

Its job in this plan is to support:

- one unified animation and skeleton pipeline for `A/B/C`
- not one separate pipeline for AI roles and another for player roles

### 6. First action set

The first shared action set should stay focused on the relationship field:

- idle
- locomotion
- turn / look
- speak
- inspect / guard
- alert / recoil
- hold-ground / observe

That is enough to support:

- `A` controlling the object
- `B` observing and reacting
- `C` entering and intervening

## Scene Upgrade Design

### 1. Space type

The scene should remain:

- single-scene
- open and traversable
- suitable for free movement

But it should stop feeling like:

- empty greybox field

And it should not regress into:

- chopped-up multi-room demo maze

The target is:

- semi-open relationship space

### 2. Spatial story logic

The space must clearly answer:

- where `C` enters from
- where `A` holds control
- where `B` observes from
- where the key object sits
- where environment reaction expands outward

### 3. Main spatial zones

The upgraded space should contain at least:

1. `Player intervention entry band`
2. `Central relationship focus zone`
3. `A control position`
4. `B observation position`
5. `Environment reaction zone`

These are conceptual zones, not necessarily separate rooms.

### 4. A control zone

`A` should be nearest to:

- the table
- the key object
- the center of control

The zone should visually imply:

- possession
- control
- readiness to block or hold position

### 5. B observation zone

`B` should not mirror `A` symmetrically.

Instead `B` should sit in a side observation position that supports:

- seeing `A`
- seeing the key object
- seeing `C` enter
- becoming the first clean receiver of Siming amplification after `A`

### 6. C intervention entry

`C` must enter through a readable spatial path.

The first player impression should be:

- there is already a live situation here
- `A` is in control of something
- `B` is not neutral, but not yet fully committed
- I am entering a tension field, not spawning in an empty sandbox

### 7. homebuilder role

`homebuilder` should be used as the main tool for turning the field into a meaningful semi-open structure.

Its role in this plan:

- form ground logic
- create low structural dividers
- build focal furniture and prop grouping
- shape entry/observation/control relationships
- avoid returning to multi-room fragmentation

It is not being used just for decoration. It is being used to encode narrative-readable space.

## Key Object And Environment Logic

The current:

- `obj_letter`
- `EnvironmentStateNode`

must be upgraded from minimal technical triggers into spatial narrative nodes.

### Key object

The key object should function as:

- relationship focal point
- reason for `A`'s control stance
- reason for `C`'s intervention

### Environment reaction node

The environment node should function as:

- an outward expansion of the central tension
- not a disconnected faraway state indicator

The target feeling is:

`C enters -> A control is disturbed -> object interaction matters -> environment shift amplifies -> B notices and reacts`

## Recommended Main-Project Material To Copy Locally

Instead of re-explaining the same architecture later, the demo project should consider copying a focused subset of main-project documents into a demo-local reference area.

### Recommended local reference set

Candidate source files:

- `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\角色智能体\07-L4执行层与具身表达总纲.md`
- `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\角色智能体\08-玩家接管、挂机接管与旅人-角色边界设计.md`
- `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\角色智能体\12-Embodiment Binder v0.1 规范.md`
- `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\角色智能体\13-FACS-SACS Planner 规范.md`
- `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\角色智能体\14-Canonical Rig 与 Asset Adapter 规范.md`
- `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\角色智能体\19-角色智能体与事件总线契约.md`
- `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\事件总线\03-Godot本地表现总线设计.md`
- `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\事件总线\04-感知链路与候选事件设计.md`

### Why copy these

- they define the exact role of player takeover vs AI driving
- they define the L4 execution split
- they define the Binder / FACS-SACS / asset-adapter direction
- they define the per-character event contract
- they reduce local drift in the demo project

### Suggested local destination

One acceptable destination is:

- `docs/reference/phase1-character-agent/`
- `docs/reference/phase1-event-bus/`

This keeps the demo project self-sufficient during implementation without pretending it owns the global architectural truth.

## What This Plan Does Not Do

This plan does not yet implement:

- full Phase 1 character cognition
- full Siming
- full event-bus contract rollout
- full FACS/SACS runtime stack
- full database or replay architecture

It only prepares the demo so those systems can attach cleanly.

## Success Criteria

This plan is successful if the next implementation round can produce:

1. one shared character execution shell for `A/B/C`
2. explicit `ai` and `player` driver modes on the same role substrate
3. `mixabridge`-based character asset and skeleton pipeline readiness
4. a homebuilder-upgraded semi-open relationship scene
5. a scene where:
   - `A` clearly controls the key object
   - `B` clearly observes
   - `C` clearly enters and intervenes
6. no breakage of the existing `Phase 0` demo loop

## One-Sentence Close

This `Phase 0.5` upgrade is not about adding “more content.” It is about converting the current demo into a unified role-agent execution base plus a readable intervention space, so `A/B` can remain AI-driven, `C` can become the first real player-driven in-world role, and both lines are already shaped for Phase 1 rather than fighting it later.
