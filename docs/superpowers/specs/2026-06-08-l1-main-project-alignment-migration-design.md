# L1 Main-Project Alignment Migration Design

## Goal

Define how the current `paralls-phase-0-demo` repository should evolve from:

- a working `L1` raw-fact skeleton

into:

- a migration-grade `L1` layer that matches the main project’s architecture direction closely enough to serve as the real entrypoint to the perception chain

without pretending to implement the entire Phase 1 stack at once.

This is a migration spec, not a “finish all of Phase 1” spec.

## Why This Spec Exists

The current repo already has a real `L1` base:

- shared raw fact contract
- unified fact emitter path
- `visual_fact`
- `spatial_access_fact`
- low-level backend runtime projection
- reconnect / replay-safe minimum state recovery
- initial `ttl_ms` fallback on nearby actor evidence

That means the problem is no longer “how do we get facts out of Godot”.

The real problem now is:

> how to connect this working `L1` skeleton to the main project’s required perception chain without collapsing boundaries again.

The main-project requirement is not just:

- “emit low-level facts”

It is:

- `L1/ESM` produce raw / structured world facts
- a perceptible compilation layer converts them into candidate percepts
- a `Per-Character` filter produces role-private perceived events
- character systems consume only the role-private version

The current repo is only at the first segment of that chain.

## Main-Project Constraints This Spec Must Respect

This spec is grounded in the main-project design language found in:

- `D:\Projects\Paralls\docs\phase1\core\00-总纲\Godot源码底层基础设施与运行时约束.md`
- `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\事件总线\01-事件总线总纲.md`
- `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\事件总线\04-感知链路与候选事件设计.md`
- `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\事件总线\07-视觉事实系统接入总线规范.md`
- `D:\Projects\Paralls\docs\phase1\core\00-总纲\技术架构总纲.md`
- `D:\Projects\Paralls\docs\phase1\core\00-总纲\L1层架构初稿.md`
- `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\角色智能体\19-角色智能体与事件总线契约.md`

From those documents, the non-negotiable architecture constraints are:

1. `L1` is the local high-frequency execution and fact-production layer, not the cognition host.
2. Raw pose / AU / local animation state must not become business-bus payloads.
3. Cross-boundary output from Godot must be structured facts.
4. Candidate percept compilation is a distinct layer between world facts and role-private perception.
5. Characters do not consume the full raw world stream by default.
6. `Per-Character` filtering is mandatory if the system is to produce role-private world versions.
7. Backend authority and Godot local presentation remain separate concerns.

## Current Repo Position

The current repo already satisfies the following part of the main-project direction:

- `L1` has a unified structured fact egress path
- facts route into backend authority, not only local presentation
- facts can update low-level projected state
- edge cases like reconnect, explicit clear, repeated environment cycles, and minimal TTL fallback are already addressed

But it still lacks the following major pieces:

- a formal candidate percept event layer
- a formal percept compilation layer
- a `Per-Character` filter layer
- a formal role-private perceived event layer
- a clear shift of character-side consumption from global low-level facts toward role-private percepts

So the migration target is not to replace current `L1`.

It is to place the missing middle layers after it.

## Target Architecture

The target migration architecture is a four-layer chain:

### 1. L1 Raw Fact Layer

This stays where it is conceptually:

- Godot / ESM edge
- local high-frequency sampling
- structured low-level world facts

Responsibilities:

- sample world-adjacent, body-adjacent, and environment-adjacent evidence
- emit normalized structured facts
- preserve replay- and audit-friendly payloads

It still must not do:

- candidate percept judgments
- role-private filtering
- cognition or meaning inference

### 2. Perceptible Compilation Layer

This is a new backend-side formal layer.

Responsibilities:

- consume raw `L1` facts
- determine which parts are perceptible in principle
- compile them into candidate percept events

This layer answers:

- what could be seen
- what could be heard
- what spatial-access or privacy evidence is candidate-relevant
- what environment changes are candidate-visible

This layer does not answer:

- what a specific character definitely perceived
- whether a candidate should survive role-private filtering
- what the event means to the character internally

### 3. Per-Character Filter Layer

This is the first place where private world versions exist.

Responsibilities:

- take candidate percept events
- apply role-specific filtering rules
- output role-private perceived events

This layer should be able to apply, at minimum:

- distance limits
- line-of-sight or occlusion policy hooks
- orientation / facing rules
- zone or privacy-band modifiers
- current focus or attention modifiers
- role-level sensory enablement switches

This layer still does not do:

- memory updates
- belief formation
- planning
- social interpretation

Those remain above it.

### 4. Character Perceived Event Layer

This is the proper downstream character-facing consumption surface.

Characters should consume:

- role-private perceived events

They should not consume directly:

- full raw fact events
- shared candidate percept streams
- Godot-local execution artifacts

## Migration Strategy

This spec recommends a two-stage migration.

### Stage A: Connect L1 To A Formal Candidate Percept Layer

Objective:

- keep the current `L1` fact-production skeleton
- add a first formal candidate percept event object and compiler layer

What changes in Stage A:

- `raw_fact_event` becomes an explicit upstream input to percept compilation
- visual and spatial-access facts no longer flow only into ad hoc runtime projections and scattered candidate logic
- the repo gains a named candidate percept layer

What does not change yet:

- characters do not switch over fully to consuming only perceived events
- no full multi-sense coverage is required
- no large role-profile system is required yet

Stage A should treat the currently working facts as the first candidate-percept source set:

- `visual_fact`
- `spatial_access_fact`

### Stage B: Connect Candidate Percepts To Per-Character Filtering

Objective:

- make role-private world versions real

What changes in Stage B:

- candidate percept events go through a formal `Per-Character` filter
- character-facing consumption shifts to perceived events, not direct raw facts

What still remains out of scope even after Stage B:

- full character memory semantics
- full L2 understanding layer
- all sensory domains

The goal is not to finish all downstream cognition.

The goal is to stop the pipeline at the correct architectural seam.

## Recommended Stage-A Deliverables

Stage A should produce these concrete architecture units.

### CandidatePerceptEvent

A new event type representing:

- a fact that is perceptible in principle
- before role-private filtering

It should carry enough information to support later filtering, including:

- source domain
- percept channel
- producer time
- room / scene / zone
- source identity
- target identity
- coarse observability or access metadata
- causation / correlation IDs

It should not contain:

- role-private certainty
- role-private salience scores
- role-private meaning judgments

### Percept Compilation Service

A backend service that:

- consumes `RawFactEvent`
- converts supported facts into one or more `CandidatePerceptEvent`

The first supported fact families should be:

- `visual_fact`
- `spatial_access_fact`

This service should be deterministic and audit-friendly.

### Candidate Event Bus Boundary

Even if implementation remains in-process, the architecture should treat candidate percepts as a distinct event boundary, not just another helper return type.

That means:

- clear models
- clear message naming
- clear debug / replay identity

## Recommended Stage-B Deliverables

### PerCharacterPerceptFilter

A backend component that:

- receives `CandidatePerceptEvent`
- a target `actor_id`
- the minimum role-specific context needed for filtering

and returns:

- zero or one `CharacterPerceivedEvent`

or a small bounded set if the input compiles into multiple private percept fragments.

### CharacterPerceivedEvent

A role-private event object representing:

- what this specific role is considered to have perceived

It should be the first object that can safely enter character-facing systems by default.

### Character Consumption Boundary

Any existing character-facing path that currently consumes shared candidate or raw fact state should be migrated to consume:

- `CharacterPerceivedEvent`

instead.

## Scope Freezes

This spec intentionally freezes some things now, and intentionally does not freeze others.

### Freeze Now

1. `L1` remains the raw fact production layer, not the candidate or private perception layer.
2. `raw_fact_event` remains the primary structured fact egress surface.
3. Candidate percept compilation becomes a formal backend layer.
4. `Per-Character` filtering becomes mandatory for role-private world versions.
5. Character systems should migrate toward consuming perceived events, not raw facts.

### Do Not Freeze Yet

1. Full all-senses schema across every sensory domain
2. Final occlusion or sensory-confidence math
3. Final replay/event-store persistence model
4. Complete role profile modeling
5. Full downstream cognition semantics

This keeps the migration tractable.

## What This Migration Must Not Do

The migration must not:

- move candidate filtering back into Godot
- turn `fact_router` into the new all-purpose cognition layer
- let characters directly subscribe to the full raw fact stream indefinitely
- explode the number of fact families before the middle layers exist
- replace the current stable `L1` skeleton with a larger but less disciplined abstraction

## What Success Looks Like

This migration spec is successful if, after implementation:

1. The current `L1` raw fact path remains intact and stable.
2. The backend has a real candidate percept compilation layer.
3. The system can distinguish clearly between:
   - raw world facts
   - candidate percepts
   - role-private perceived events
4. At least the current visual and spatial-access facts enter that chain cleanly.
5. Characters have a defined migration path away from direct shared-fact consumption.
6. The repo is materially closer to the main-project `L1` architecture rather than merely adding more demo-local fact families.

## Final Summary

This repository does not need a new `L1`.

It needs to stop treating the current `L1` skeleton as the end of the perception pipeline.

The correct next move is:

- keep `L1` as the structured raw fact layer
- add candidate percept compilation behind it
- add `Per-Character` filtering behind that
- move character-facing consumption to the filtered layer

That is the shortest migration path from the current demo architecture to the main-project design intent.
