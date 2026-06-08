# System L1 Full Phase 1 Implementation Design

## Goal

Define the full `System L1` implementation target for `Phase 1` in the current repository.

This spec freezes:

- what `System L1` is
- what belongs inside `System L1`
- what does not belong inside `System L1`
- how `System L1` connects upward into `System L2`
- how `System L1` should be decomposed into child specs and implementation batches

This spec does **not** define the full implementation of:

- `System L2`
- `Character Agent L1-L4`
- `System L3`
- `System L6`

It only fixes the `System L1` domain so those higher layers can depend on it safely.

## Position In The Main Architecture

Per the main-project architecture, `System L1` is:

- the deterministic spatial layer
- the runtime execution domain
- the first structured fact-production layer

It is responsible for:

- accepting player input and upstream AI execution intents
- executing deterministic world actions
- running local high-frequency embodiment and presentation-safe runtime behavior
- producing structured, replayable raw world facts

It is **not** responsible for:

- candidate percept compilation
- role-private filtering
- character understanding
- character planning
- Siming judgment
- evidence meaning interpretation

Those belong above `System L1`.

## Terminology Freeze

### System L1

`System L1` means the world-facing execution and raw-fact layer.

### Character Agent L1

`Character Agent L1` means the character’s own private perception input layer.

These two terms must never be collapsed into one `L1`.

### Raw Fact

A structured, replayable low-level world fact emitted by `System L1`.

### Candidate Percept

A system-level `L2` object derived from raw facts, expressing what could be perceived in principle.

### Character Perceived Event

A role-private event that has already passed `Per-Character` filtering and is safe to enter character-agent processing.

## System L1 Domain Composition

`Phase 1 System L1` includes the following subdomains:

1. Client-side interaction execution
2. Spatial audio execution and auditory fact emission
3. `ESM` environment and entity state execution
4. Visual fact system
5. Eight classes of raw sensory/state fact emitters
6. `System L1 -> System L2` raw-fact interface
7. `System L1` debugging, replay, and verification surfaces

## System L1 Fact-Production Principle

Every `System L1` fact emitter follows one shared rule:

- sample or observe a low-level world-adjacent condition
- normalize it into a structured fact
- emit it without injecting narrative or subjective inference

That means `System L1` may say:

- who approached whom
- who entered which zone
- what changed in light, sound, state, position, or contact

But it must not say:

- who now belongs to a conversation group
- who definitely perceived the event
- what the event means socially
- what any character believes about it

Those are downstream `System L2` responsibilities.

## The Eight Raw Fact Emitter Classes

For `Phase 1`, the full `System L1` target includes these eight raw emitter classes:

1. visual fact emitters
2. auditory fact emitters
3. tactile fact emitters
4. thermal fact emitters
5. olfactory fact emitters
6. physiology state fact emitters
7. social-distance / spatial-behavior fact emitters
8. role-state fact emitters

Current repository status:

- visual fact emitters: partial
- social-distance / spatial-behavior emitters: partial
- the remaining six classes: largely missing

This spec treats all eight as real `Phase 1 System L1` scope, not optional placeholders.

## Visual Fact System Within System L1

The visual fact system is a first-class subdomain of `System L1`.

Its required structure is:

- local visible state sampling
- local semantic extraction
- structured visual fact emission

Its internal primary source domains are:

1. `character`
2. `object`
3. `environment`
4. `spatial_relation`

Its derived layer is:

5. `evidence_projection`

This means a complete `Phase 1` visual-fact implementation inside `System L1` requires:

- `CharacterVisualFactEmitter`
- `ObjectVisualFactEmitter`
- `EnvironmentVisualFactEmitter`
- `SpatialRelationVisualFactEmitter`
- `EvidenceProjectionEmitter`

The current repo only covers part of that set.

## Spatial Audio And Auditory Facts Within System L1

Spatial audio belongs to `System L1`, not to the event bus or character cognition layer.

`Phase 1` requires it to produce both:

- human-heard output
- AI-compilable auditory raw facts

At minimum, auditory raw facts should cover:

- who is speaking
- sound source location
- loudness band
- whisper / normal / shout mode
- coarse environment-noise context

## ESM Within System L1

`ESM` remains part of `System L1`.

Its `Phase 1` role is:

- deterministic environment/entity state execution
- action constraint and result settlement
- environment-state and execution-result fact production

For `Phase 1`, `ESM` must not be treated as only a tiny interaction helper.

It needs at least:

- action settlement interfaces
- state-machine templates
- environment-state result production
- regional environment field / propagation rules
- event-bus contract
- replay/debug hooks

## System L1 To System L2 Boundary

`System L1` outputs:

- raw world facts
- environment state results
- raw sensory/state facts

`System L2` consumes those and then performs:

- candidate percept compilation
- `Per-Character` filtering
- character-agent private event generation

`System L1` must not bypass that chain by:

- directly generating candidate percepts in Godot
- directly generating character-private perception in Godot
- directly publishing social interpretation fields

## Relationship To Character-Agent L1-L4

`System L1` is not the character’s mind.

The correct handoff is:

- `System L1` emits raw facts
- `System L2` compiles candidate percepts
- `System L2` filters them per character
- `Character Agent L1` receives role-private perceived events
- `Character Agent L2-L4` continue from there

So even when `System L1` becomes “fully implemented”, that still does **not** mean the character-agent chain is fully implemented.

## Phase 1 Priority Rules

### First priority

The following must be treated as core `Phase 1 System L1` work:

- visual fact system completion
- auditory fact emission
- `ESM` action/state/environment execution formalization
- social-distance / spatial-behavior fact maturation
- raw-fact contract stability
- `System L1 -> System L2` interface stability
- replay/runtime verification

### Second priority

The following still belong to `Phase 1`, but can be staged after the first group:

- tactile fact emission
- thermal fact emission
- olfactory fact emission
- physiology fact emission
- role-state fact emission

They are in scope, but not necessarily the first batch to implement.

## Phase 1 Non-Goals For This Domain

This spec does not require `System L1` to deliver:

- full long-horizon weather simulation
- complete biological growth systems
- final persistent-world execution architecture
- complete commercial ecosystem hooks

Those remain outside the immediate `Phase 1` minimum for this repository.

## Required Child Specs

This total spec is intentionally paired with child specs.

The child-spec bundle for this domain should include at least:

1. client-side interaction execution
2. spatial audio and auditory fact emission
3. `ESM`
4. visual fact system
5. tactile fact emitter
6. thermal fact emitter
7. olfactory fact emitter
8. physiology state fact emitter
9. role-state fact emitter
10. `System L1 -> System L2` interface
11. `System L1` debugging / replay / verification

The visual-fact child spec is expected to contain:

- object visual emitter
- spatial-relation visual emitter
- evidence projection emitter

instead of splitting those into standalone top-level specs.

## Current Repository Suitability

The current repository is suitable as a `Phase 1 System L1` implementation base because it already has:

- a stable raw-fact emission spine
- authority routing
- runtime verification harnesses
- reconnect/reseed protections
- a candidate-percept bridge into `System L2`

But it is not yet a complete `Phase 1 System L1` implementation because:

- only a subset of the eight emitter classes exist
- the visual-fact system is incomplete
- auditory facts are missing
- `ESM` is still a minimal slice rather than a full `Phase 1` subdomain

## Success Criteria

This total spec is satisfied only when:

1. all major `System L1` subdomains named here have concrete child specs
2. the eight raw emitter classes are treated as real `Phase 1` scope
3. the repo keeps `System L1` separate from `System L2` and character-agent internal layers
4. `System L1` can serve as the stable execution-and-fact base for the broader `Phase 1` architecture

## Final Summary

The next step for this repository is not to invent another `L1`.

It is to complete the full `System L1` domain as defined by the main-project Phase 1 architecture:

- deterministic world execution
- structured raw fact production
- visual facts
- auditory facts
- `ESM`
- the remaining raw emitter classes
- and a clean handoff into `System L2`
