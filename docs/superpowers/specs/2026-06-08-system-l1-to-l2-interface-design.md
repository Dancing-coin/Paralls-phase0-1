# System L1 To System L2 Interface Design

## Goal

Define the stable interface boundary between:

- `System L1` raw fact production
- `System L2` candidate percept compilation
- `System L2` `Per-Character` filtering

## Required Event Layers

The interface must distinguish at least:

1. `RawFactEvent`
2. `CandidatePerceptEvent`
3. `CharacterPerceivedEvent`

These three objects must remain distinct.

## RawFactEvent

Represents:

- structured low-level world-adjacent facts

Produced by:

- `System L1`

## CandidatePerceptEvent

Represents:

- what could be perceived in principle

Produced by:

- the system-level `L2` percept compilation layer

## CharacterPerceivedEvent

Represents:

- what one specific role is considered to have perceived after filtering

Produced by:

- the system-level `L2` `Per-Character` filter

Consumed by:

- character-agent `L1`

## Interface Rules

1. `System L1` must not emit `CharacterPerceivedEvent`.
2. `System L1` must not emit role-private conclusions.
3. `System L2` candidate compilation must remain distinct from `Per-Character` filtering.
4. Character-agent inputs should move toward `CharacterPerceivedEvent` and away from direct shared raw-fact consumption.

## Success Criteria

This child spec is satisfied when the repo has a stable, explicit, three-stage interface between raw facts, candidate percepts, and role-private perceived inputs.

