# Complete Character Mind Core Design

Status: `awaiting-user-review`

Date: `2026-06-29`

## Problem

The repository no longer has the right top-level target for character-agent work.

Current in-repo truth still reflects a `Phase 0` validation slice:

- prove a runnable dramatic loop
- keep authority boundaries honest
- land a partial `CharacterAgentRuntime`
- keep execution visible enough for the demo

That target was useful for earlier convergence work, but it is now too narrow.

The new required objective is:

- this repository becomes the implementation home for the **complete character mind core**
- perception through planning must be fully implemented as a real role-mind runtime
- execution may remain intentionally light, as long as it preserves all contracts needed for later full embodiment

The current repository is not there yet.

What exists now is stronger than a stub, but weaker than a full role mind:

- `L1` private snapshot already covers multiple modalities and quality traces, but its final mind-core semantics are not yet frozen
- profile loading exists and runtime consumption has begun, but some planning and cognition logic still treat profile/goal data too loosely
- memory has reached event / observation / knowledge / social / higher-order pools, but the cognition architecture is not yet fully closed around them
- `L2` already emits belief, social, higher-order, and dynamic-state deltas, but the cognition engine is still partly scenario-heuristic rather than a unified update system
- `L3` already has broader candidate space and goal-frame persistence, but goal layering, reorganization, repair, and recovery semantics are still incomplete
- player-priority and execution-preservation paths already carry much richer mind data, but they do not yet prove final mind-core closure by themselves
- the repository still carries old `Phase 0` mission statements and older character-runtime docs that understate the new target

So the next step is not “one more implementation patch.”

The next step is to redefine the source of truth for character-agent work in this repository.

## New Repository Mission For Character-Agent Work

For character-agent work, this repository now targets:

- **complete character mind core first**
- **minimal smoke-preserving Phase 0 compatibility second**

This is a dual-track strategy:

1. the mainline target is the full role-mind core
2. the repository should preserve a minimal `Phase 0` smoke path when reasonable
3. the smoke path must not freeze the old architecture or block the mind-core design

This is not a “keep the demo as the final truth” strategy.

It is:

- preserve enough demo continuity to stay testable
- but let the mind-core architecture become the primary source of truth

## Primary Sources

This design is grounded in the current character-agent source material:

- `docs/phase1/core/01-运行时核心/角色智能体/01-角色智能体总纲.md`
- `docs/phase1/core/01-运行时核心/角色智能体/02-人格形成链与静态档案设计.md`
- `docs/phase1/core/01-运行时核心/角色智能体/03-感知链路与角色私有世界模型设计.md`
- `docs/phase1/core/01-运行时核心/角色智能体/04-记忆系统与知识状态设计.md`
- `docs/phase1/core/01-运行时核心/角色智能体/06-L3规划层与三重过滤器设计.md`
- `docs/phase1/core/01-运行时核心/角色智能体/07-L4执行层与具身表达总纲.md`
- `docs/phase1/core/01-运行时核心/角色智能体/08-玩家接管、挂机接管与旅人-角色边界设计.md`

It also respects current in-repo runtime constraints:

- `System L1 / ESM` remain world-truth settlement authority
- `Siming` remains a catalyst, not a direct role-replacement brain
- the shared Godot actor ingress remains the only local embodiment family

## Scope Decision

This design covers the **character mind core**.

That means:

- `L1` perception
- profile system
- memory and knowledge architecture
- dynamic state
- `L2` interpretation and belief update
- `L3` planning and intent selection
- control arbitration between AI / player-priority / away-conservative / scripted modes
- observability, storage, replay, and verification needed to make the above auditable

This design does **not** require full embodiment completion right now.

Execution may remain light if all of the following are true:

- `L4` still receives a complete mind-core output contract
- current execution remains compatible with the shared actor ingress
- no temporary execution shortcut collapses, distorts, or hides the upstream mind semantics
- the resulting contracts are sufficient to support later full face/body/physiology embodiment work

## Non-Goals

This design does not attempt in this stage to finish:

- full `FACS/SACS/Binder` rollout
- final animation-system richness
- final canonical-rig adapter generalization
- final production database topology
- final multi-scene story orchestration
- final world simulation architecture outside what the character mind core consumes

## Definition Of “Complete Character Mind Core”

The role mind is considered complete only when all of the following are true.

### 1. Stable Long-Term Character Core

Every role runtime instance is anchored by:

- structured long-term profile truth
- profile immutability during normal runtime
- explicit separation between long-term profile and short-term runtime state

Required long-term profile strata:

1. identity core
2. origin seed
3. life memory backbone
4. virtue / value layer
5. trait vector layer
6. capability / constraint layer
7. style / expression bias layer
8. conversation personality layer

### 2. Full `L1` Private Perception

`L1` must be a complete role-private world entrance, not just a small event wrapper.

Required perceptual qualities:

- clarity
- certainty
- partial observation
- distorted observation
- missed details
- salience
- attention focus
- anomaly retention

Required modality coverage:

- vision
- audition
- smell
- heat / atmosphere
- touch / proximity
- self-body state
- Siming catalyst effects on attention / vigilance / distraction

Required snapshot families:

- visible / audible / sensed entities
- unresolved signals
- active anomalies
- attention targets
- short-horizon social presence
- local spatial confidence map
- body-state hints
- recent world changes
- recent constraints
- active catalyst pressure
- current perception quality state

### 3. Full Cognitive Memory Architecture

The complete mind core uses **five** memory pools:

1. `Event Memory`
2. `Observation Memory`
3. `Knowledge Memory`
4. `Social Memory`
5. `Higher-Order Memory`

#### Event Memory

Stores what happened, regardless of later interpretation.

#### Observation Memory

Stores the role’s perceived version of what it sensed.

#### Knowledge Memory

Stores proposition-like believed content with confidence and state.

#### Social Memory

Stores durable relationship cognition toward other roles.

#### Higher-Order Memory

Stores subjective reasoning about who knows what, who suspects what, and who knows that others know.

This layer is mandatory for “complete mind core” status.

Without it, the system cannot honestly claim full social-cognitive completeness.

### 4. Explicit Knowledge-State Progression

Knowledge is not a flat belief string.

Every proposition must support state transitions such as:

- `noticed`
- `suspected`
- `tentatively_believed`
- `believed`
- `high_confidence_believed`
- `disputed`
- `abandoned`

The runtime must preserve:

- proposition source
- confidence
- contradiction references
- current belief status
- lineage back to perception or writeback

### 5. Dynamic State As A First-Class Runtime Layer

The complete mind core must maintain runtime-dynamic state separate from profile truth and memory truth.

Minimum state families:

- current tension / stress
- vigilance / distraction
- current social pressure
- emotional direction or affective pressure
- motivation activation
- unresolved conflict load
- masking / concealment pressure
- body-linked subjective burden signals

This state is the bridge between archive-like memory and live decision bias.

### 6. Full `L2` Subjective Interpretation

`L2` must do more than summarize events.

It must convert current role-private reality into:

- interpreted situation
- belief deltas
- social read
- perceived risk
- perceived opportunity
- attention pressure
- inner-state shift
- reasoning trace summary

It must also be able to update:

- `Knowledge Memory`
- `Social Memory`
- `Higher-Order Memory`
- dynamic state

`L2` is therefore a live cognition-update layer, not just a structured classifier.

### 7. Unified Cognition Engine Semantics

`L2` cannot remain a bag of one-off scenario handlers.

The complete mind core requires a consistent cognition-update engine that merges:

- current private perception
- active knowledge state
- social memory
- higher-order memory
- dynamic state
- recent settlement and dialogue writeback
- Siming pressure and retrieval bias

Required properties:

- the same classes of evidence must produce the same classes of cognitive updates regardless of whether the trigger was social, environmental, bodily, or catalyst-driven
- every belief / social / higher-order / dynamic / goal-directed update must preserve source and confidence lineage
- cognition outputs must be structured runtime objects, not only anonymous loose dictionaries
- the system must be able to explain why a current update was produced in terms of evidence family, not only via free-text narration

This means the remaining work is not “add more cases.”

It is:

- unify the evidence-to-update rules
- make update provenance explicit
- keep the model-facing contract and local fallback contract semantically aligned

### 8. Goal System As A First-Class Runtime Layer

The complete mind core requires a formal goal system, not only transient candidate scoring.

Required goal layers:

- long-term motive
- mid-term social or situational strategy
- immediate tactical goal
- supporting goals
- blockers
- explicit goal sources

Required runtime goal artifacts:

- structured `goal_hint` objects rather than raw strings
- a structured active-goal frame carried from `L2/L3` into runtime outputs
- persisted current goal state
- previous goal state and short history tail
- explicit transition semantics
- explicit reorganization semantics
- explicit repair / recovery semantics after failure, contradiction, or blocked execution

Required transition semantics include at minimum:

- `initial`
- `maintained`
- `shifted`
- `escalated`
- `deescalated`
- `reorganized`
- repair / recovery-oriented transitions when the role must abandon, patch, or replace a failing active strategy

The goal system is complete only when the runtime can answer all of the following:

- what the role wants long-term
- what strategy it is currently pursuing
- what it is trying to do right now
- what evidence changed that goal frame
- whether the current frame is a continuation, escalation, reorganization, or repair

### 9. Full `L3` Planning

`L3` must implement the full action-possibility-space manager shape.

Required modules:

1. goal activator
2. candidate generator
3. constraint projector
4. triple filter engine
5. priority ranker
6. intent selector

Required candidate-space posture:

- not only reactive observation
- not only narrow dialogue actions
- includes approach / avoidance / concealment / escalation / alliance / probing / silence / delay / distancing / follow / break-contact / self-protection / object interaction / public-private speech
- includes non-escalatory and non-action outcomes such as pause, defer, silence, hold-position, and preserve-optionality

Required filter families:

- persona filter
- logic filter
- gain / loss filter

Required output semantics:

- rejected
- weakly viable
- viable
- highly compelling

The complete mind core requires this layer to be:

- profile-aware
- memory-aware
- knowledge-state-aware
- higher-order-memory-aware
- dynamic-state-aware

It must also be:

- goal-frame-aware
- transition-aware
- able to favor repair, withdrawal, concealment, or strategy change when the active goal frame is blocked or contradicted

### 10. Control Arbitration That Preserves One Role Species

All roles remain one role-runtime species.

Differences are carried by control mode, not by separate brain species.

Required modes:

- `agent_full_auto`
- `player_priority_assisted`
- `away_conservative_takeover`
- `scripted_override`

Requirements:

- player-related roles still run `L1/L2`
- player-priority mode still produces suggestion packets and automatic micro-continuity
- away-takeover stays conservative and low-risk
- scripted override still writes the same runtime lineage and does not bypass the mind core invisibly

### 11. `L4` Contract Completeness Without Full Embodiment Completion

Execution can remain light, but the upstream contract cannot be shallow.

The mind core must already emit a complete `L4`-ready execution contract across:

- speech
- face
- body
- social-spatial
- physiology

Even if the current live implementation simplifies some of those channels downstream, the contract must be rich enough that later embodiment work does not require redesigning `L1-L3`.

## System Boundaries

### Upstream Input Rule

The character mind core accepts only:

1. role-private perceived events
2. self-body perceived events
3. Siming high-level catalyst input
4. world / constraint / dialogue / settlement writeback already narrowed to role meaning

It must not directly consume:

- raw global world truth as business input
- hidden omniscient state
- local keyboard/mouse/camera noise as cognition input

### Downstream Output Rule

The character mind core may output:

- intent plans
- dialogue acts
- speech requests
- body / face / physiology expression plans
- social-spatial action requests
- state writeback candidates

It may not:

- directly settle world-truth outcomes
- directly rewrite physical truth
- bypass `System L1 / ESM`

### Siming Rule

`Siming` may:

- change salience
- bias attention
- elevate vigilance
- inject pressure
- bias retrieval priority
- bias interpretation and ranking

`Siming` may not:

- inject hidden truth the role never perceived
- bypass `L2`
- bypass `L3`
- defeat explicit player-priority control
- directly finalize embodiment or world settlement

## Migration Strategy

This repository will move from “Phase 0 slice with partial mind” to “mainline complete mind core” through three linked artifact tracks.

### Track A: Source-Of-Truth Rewrite

Update repository-local character-agent design truth so that:

- character-mind work no longer inherits the old `Phase 0` cap as its primary target
- the new top-level target is explicit and durable
- stale docs are marked transitional or superseded

### Track B: Mind-Core Implementation

Implement the missing core layers and deepen existing ones:

- full `L1`
- five-pool memory
- dynamic state
- higher-order cognition
- full `L2`
- full `L3`
- goal-system closure
- stronger typed runtime state and provenance
- stronger storage, replay, and auditability

### Track C: Execution Preservation

Keep the current execution path usable enough that:

- the repository remains smoke-testable
- the shared actor ingress remains the only embodiment family
- later full embodiment work can attach without redesigning the mind core

## Documentation And Truth Policy

This spec supersedes the old narrow mission **for character-agent mind-core work**.

It does not erase:

- authority boundaries
- shared actor-ingress constraints
- `System L1 / ESM / Siming` contracts

But it does replace the old idea that this repository should stop at a `Phase 0`-bounded mind slice.

After approval, the follow-on documentation work must:

- mark outdated runtime docs as transitional where needed
- align `docs/INDEX.md` and `docs/character/` entry points
- preserve a clear map from old partial-runtime artifacts to new mainline mind-core artifacts

## Acceptance Criteria

This character mind core is accepted only when all are true.

1. The repository has an approved top-level source of truth that defines complete character mind core as the primary character-agent objective.
2. `L1` supports full role-private perception with modality coverage, quality semantics, and private snapshot continuity.
3. The runtime owns five real memory pools:
   - event
   - observation
   - knowledge
   - social
   - higher-order
4. Knowledge objects preserve explicit state progression, confidence, source, contradiction, and lineage.
5. Dynamic state exists as its own first-class runtime layer rather than being smeared into snapshot or memory.
6. `L2` consumes profile + snapshot + memory + dynamic state and produces real cognition-update outputs.
7. `L2` updates knowledge, social, higher-order, and dynamic state rather than only returning a summary object.
8. `L2` uses a unified cognition-update logic across social, world, body, and Siming-triggered evidence rather than only disconnected scenario patches.
9. Goal hints, active-goal frames, and persisted goal-state are structured runtime objects with explicit provenance and continuity semantics.
10. The goal system preserves long-term motive, mid-term strategy, immediate goal, supporting goals, blockers, sources, and repair/recovery semantics.
11. `L3` consumes `L2` outputs and manages a broad role action space rather than a narrow demo-only reaction set.
12. `L3` uses persona / logic / gain-loss filtering grounded in profile, memory, knowledge state, higher-order cognition, dynamic state, and current goal-frame state.
13. Player-priority, away-conservative, scripted, and full-auto modes all remain one runtime species.
14. The output of the mind core is already sufficient to support later full embodiment completion without redesigning upstream layers.
15. `System L1 / ESM / Siming` boundaries remain intact.
16. A minimal `Phase 0` smoke path remains available unless a later approved plan explicitly and temporarily suspends it.

## Verification Requirements

Minimum proof for the complete mind core must include:

- backend unit tests for:
  - profile loading and projection
  - full `L1` perception updates across modality and quality cases
  - five-pool memory deposition and retrieval
  - knowledge-state transitions
  - higher-order-memory updates
  - dynamic-state updates
  - `L2` cognition outputs and writebacks
  - unified cognition-update behavior across social / world / body / Siming evidence families
  - goal-hint typing, provenance, and normalization
  - goal-state transitions, reorganization, and repair/recovery behavior
  - `L3` candidate generation breadth
  - `L3` filter behavior under profile / memory / higher-order / goal-frame conditions
  - control-mode arbitration
- runtime integration tests for:
  - full-auto roles
  - player-priority suggestion roles
  - away-conservative takeover
  - Siming pressure and salience bias
  - memory and cognition writeback after settlement/dialogue
  - suggestion packets and observability snapshots preserving current goal frame and reasoning lineage
- fresh smoke verification proving the minimal `Phase 0` path still runs
- fresh shared actor ingress verification proving the preserved execution path still consumes mind-core outputs

## Planned Decomposition

After this spec is approved, follow-on work must be split into multiple plans rather than one monolithic execution plan.

At minimum:

1. `mind-core-foundation`
   - source-of-truth rewrite
   - runtime object model
   - storage and observability seams
2. `full-l1-and-memory`
   - full perception semantics
   - five-pool memory
   - dynamic state
3. `full-l2-and-l3`
   - cognition update layer
   - higher-order reasoning
   - broad action-space planning
   - control arbitration and suggestion semantics
4. `execution-preservation-and-readiness`
   - preserve smoke path
   - preserve shared actor ingress
   - make `L4` contracts embodiment-ready without requiring full embodiment completion now
5. `mind-core-closure`
   - unify remaining cognition-engine semantics
   - formalize typed goal and mind-state runtime artifacts
   - complete goal transition / reorganization / repair semantics
   - preserve observability and assisted-mode carry-through for the final mind-core contract

## Summary

This repository now needs a different character-agent destination.

The real target is not:

- “a better Phase 0 demo agent”

The real target is:

- a complete role mind core with
  - stable profile truth
  - full private perception
  - five-pool cognition memory
  - dynamic state
  - full interpretation
  - full planning
  - unified control arbitration
  - light but future-complete execution contracts

That is the architecture this spec defines.
