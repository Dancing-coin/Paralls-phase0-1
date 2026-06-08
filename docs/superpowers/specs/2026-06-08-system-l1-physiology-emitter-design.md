# System L1 Physiology State Fact Emitter Design

## Goal

Define the physiology-state raw-fact emitter expected inside `System L1` for `Phase 1`.

## Responsibilities

The physiology emitter should surface low-level bodily-state facts such as:

- tremor
- breathing strain
- instability
- fatigue band
- involuntary body-state anomalies

These are still low-level facts, not internal psychological truths.

## What It Must Not Do

It must not decide:

- why the body is in that state
- what the role believes about it
- how another role interprets it

## Relationship To Character Systems

This emitter gives downstream systems structured evidence that the role body is in a given state.

The role-private and cognitive meaning of that state is a later-stage concern.

## Success Criteria

This child spec is satisfied when physiology facts are a formal `System L1` output domain with explicit structured shape and routing expectations.

