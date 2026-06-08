# System L1 ESM Phase 1 Design

## Goal

Define the `Phase 1` `ESM` implementation expected inside `System L1`.

The goal is to move the current repo from:

- a minimal interaction/environment result slice

to:

- a real `Phase 1` execution-state subdomain

without turning `ESM` into a cognition or narrative system.

## ESM Role

`ESM` is responsible for:

- deterministic action settlement
- environment and entity state-machine execution
- environment-field updates that materially affect interaction or perception
- structured world-result emission

`ESM` is not responsible for:

- evidence interpretation
- narrative significance
- character subjective meaning
- Siming judgment

## Required Phase 1 Capabilities

### 1. Action Settlement

`ESM` must be able to answer:

- was the action legal
- did it succeed
- what state changed
- what constraints blocked it

### 2. State-Machine Templates

It must expose stable templates for:

- object states
- environment states
- entity interaction state transitions

### 3. Regional Environment Field And Propagation

It must support at least a minimal regional environment field concept for:

- light
- noise
- thermal reach
- visibility-affecting conditions

This does not require a giant simulation, but it does require more than one-off environment toggles.

### 4. Event-Bus Contract

It must emit structured results into the system boundary, not only mutate local state.

### 5. Replay / Debug Hooks

It must support:

- audit-friendly state result emission
- deterministic replay inputs
- debug workbench visibility

## Relationship To Visual Facts

`ESM` does not generate visual facts directly, but it creates world conditions that the visual-fact system may later observe and emit.

Example:

- `ESM` settles door or light state
- visual-fact system later emits the visible consequences

## Relationship To Character Systems

Character systems may request actions.

`ESM` returns:

- what physically or logically happened

Characters then interpret that result; `ESM` does not do it for them.

## Success Criteria

This child spec is satisfied when:

1. `ESM` is more than a tiny demo helper
2. its contracts, environment state transitions, and propagation boundaries are explicit
3. it remains firmly inside `System L1`

