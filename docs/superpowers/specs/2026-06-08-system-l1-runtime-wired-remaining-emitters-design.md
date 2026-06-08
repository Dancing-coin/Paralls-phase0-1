# System L1 Runtime-Wired Remaining Emitters Design

## Goal

Define how the five remaining `System L1` fact families move from shell-only presence to runtime-wired implementation in this repository.

Target families:

- tactile
- thermal
- olfactory
- physiology-state
- role-state

## Problem

The repository now has explicit emitters for all five families, but they are only shell-level producers.

That is enough for structural completeness.
It is not enough for full-volume `System L1`.

## Design Principle

Not every remaining family needs the same runtime depth immediately.

Use two buckets:

### Runtime-first families

These should become truly runtime-wired in this repo:

- `role-state`
- `physiology-state`

Reason:

- both can derive from already-running low-level runtime state
- they do not require inventing broad new world simulation
- they are the cheapest path from shell-complete to runtime-complete

### Bounded-but-explicit families

These may remain more bounded for now:

- `tactile`
- `thermal`
- `olfactory`

Reason:

- each depends more strongly on richer source simulation or collision/environment semantics
- fake completeness would be worse than a bounded explicit implementation

## Required Runtime-Wired Targets

### Role-state facts

Must emit at least:

- stance class
- locomotion state class
- execution-mode transition

Runtime source should come from already-running local embodiment state, not invented synthetic triggers.

### Physiology-state facts

Must emit at least:

- breathing strain band
- instability / fatigue-like anomaly band

Runtime source should come from already-running locomotion / forced-movement / body-state conditions, not psychological interpretation.

## Required Bounded Targets

### Tactile facts

Must at least gain one explicit runtime source, such as:

- interaction contact
- proximity-triggered coarse touch proxy

If true continuous contact sampling is not yet justified, the spec must state that clearly.

### Thermal facts

Must be tied to:

- repository-local environment field state
- or explicit heat-source environment state

not purely hand-authored manual emits.

### Olfactory facts

Must at least define:

- which repo-local source can legitimately emit smell state
- what the minimum structured odor-state surface is

If runtime depth remains limited, the boundary must be explicit.

## Verification Requirement

For this spec to be satisfied:

- at least `role-state` and `physiology-state` must become runtime-proved
- the other three must become more than pure file shells
- verification must distinguish:
  - static existence
  - runtime-wired proof

## Non-Goals

- full body simulation
- full chemical diffusion
- full thermal solver
- full tactile perception

