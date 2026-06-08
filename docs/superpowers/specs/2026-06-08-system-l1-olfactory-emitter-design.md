# System L1 Olfactory Fact Emitter Design

## Goal

Define the olfactory raw-fact emitter expected inside `System L1` for `Phase 1`.

## Responsibilities

The olfactory emitter should capture low-level smell-adjacent facts such as:

- source of odor
- odor intensity band
- local spread or proximity classification
- environmental odor-state changes

## What It Must Not Do

It must not produce:

- role-private smell perception
- narrative conclusions
- social inferences

## Relationship To L2

Olfactory raw facts enter `System L2` the same way as other sensory facts:

- as structured low-level facts
- then as candidate percepts
- then through `Per-Character` filtering

## Success Criteria

This child spec is satisfied when smell-related world facts exist as a defined `System L1` emitter domain rather than remaining absent from the architecture.

