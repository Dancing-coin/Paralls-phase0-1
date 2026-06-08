# System L1 Thermal Fact Emitter Design

## Goal

Define the thermal raw-fact emitter expected inside `System L1` for `Phase 1`.

## Responsibilities

The thermal emitter should capture low-level thermal facts such as:

- local heat source presence
- coarse heat intensity band
- thermal proximity change
- thermal hazard relevance

## What It Must Not Do

It must not produce:

- role-private thermal perception
- injury meaning
- fatigue or fear interpretation

## Relationship To ESM

Thermal field changes may come from environment-state execution in `ESM`, but the emitter is responsible for exposing the structured raw thermal fact surface.

## Success Criteria

This child spec is satisfied when thermal facts are represented as a real `System L1` emitter path with stable structured output.

