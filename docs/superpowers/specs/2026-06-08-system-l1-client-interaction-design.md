# System L1 Client Interaction Execution Design

## Goal

Define the `Phase 1` client-side interaction execution subsystem inside `System L1`.

This subsystem is responsible for:

- accepting player and already-authorized AI action intents
- executing low-level local interaction behavior
- producing deterministic, replayable interaction facts

It is not responsible for:

- candidate percept compilation
- character-private filtering
- narrative interpretation
- final environment/constraint meaning

## Responsibilities

The client-side interaction subsystem must provide:

1. input adaptation
2. deterministic action execution
3. precise interaction fact production
4. state-change trigger handoff to `ESM`
5. local feedback for the human player

At minimum, it should be able to represent:

- movement intention execution
- interaction request execution
- object-use request execution
- focus-target changes
- coarse contact or reachability-related interaction facts

## Required Outputs

This subsystem should emit structured facts describing:

- who attempted what
- what target was involved
- where it happened
- what low-level local execution state was entered

It may also emit raw sensory-adjacent facts when the interaction itself changes observability.

It must not emit:

- membership conclusions
- perception conclusions
- dialogue group final membership

## Relationship To ESM

The client-side interaction subsystem does not finalize world truth.

It produces:

- interaction requests
- deterministic local execution facts

`ESM` then decides:

- whether the action succeeds
- which state transitions occur
- what result facts must be written back

## Relationship To Fact Emitters

The interaction subsystem is an upstream producer for multiple `System L1` fact emitters:

- social-distance / spatial-behavior facts
- role-state facts
- raw interaction and environment-triggering facts

It should not own all emitter logic inline.

Its job is to expose enough deterministic local state that the emitters can work cleanly.

## Minimum Phase 1 Interfaces

The subsystem should stabilize:

- action request input shape
- focus/target change shape
- movement execution feedback shape
- interaction attempt shape

And should integrate with the shared `raw_fact_event` emission path rather than creating separate ad hoc send surfaces.

## Success Criteria

This child spec is satisfied when:

1. the client-side interaction layer is clearly separated from `ESM`
2. it emits replayable low-level interaction facts
3. it feeds the emitter layer without mixing in candidate or private-perception logic

