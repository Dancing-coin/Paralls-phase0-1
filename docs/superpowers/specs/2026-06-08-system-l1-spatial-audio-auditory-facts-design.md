# System L1 Spatial Audio And Auditory Fact Emission Design

## Goal

Define the `Phase 1` spatial-audio subsystem and auditory raw-fact emitter inside `System L1`.

This subsystem must support both:

- human-heard local output
- AI-compilable auditory raw facts

## Responsibilities

The spatial-audio subsystem inside `System L1` is responsible for:

1. source localization
2. distance attenuation
3. obstruction / muffling behavior
4. loudness band classification
5. speech mode classification
6. environment noise baseline capture
7. auditory fact emission

## Auditory Fact Scope

At minimum, the auditory fact emitter should be able to express:

- source actor
- source object or environment if relevant
- sound source position or coarse zone
- loudness band
- whisper / normal / shout mode
- clear / muffled / silent reachability
- ambient noise context

## What It Must Not Do

The auditory emitter must not directly produce:

- candidate hearing events
- eavesdropping success conclusions
- role-private “this character definitely heard X” outputs

Those remain downstream `System L2` work.

## Relationship To Human Output

The same subsystem may drive human 3D audio playback, but:

- the audio stream itself is not the raw fact
- the raw fact is the structured summary of the sound event and its propagation-relevant characteristics

## Phase 1 Minimum Deliverable

The first `Phase 1` slice should cover:

- actor speaking facts
- loudness band facts
- speech mode facts
- coarse auditory reachability facts
- ambient-noise baseline facts

## Success Criteria

This child spec is satisfied when:

1. the repo has a formal auditory fact path under `System L1`
2. auditory facts are structured and replayable
3. human-heard output and AI-compilable input remain related but distinct

