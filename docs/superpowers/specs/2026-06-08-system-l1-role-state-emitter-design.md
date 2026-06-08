# System L1 Role-State Fact Emitter Design

## Goal

Define the role-state raw-fact emitter expected inside `System L1` for `Phase 1`.

## Responsibilities

The role-state emitter should capture structured low-level role state facts such as:

- stance class
- locomotion state
- execution mode transitions
- hard runtime state changes that materially affect the world or perception chain

## What It Must Not Do

It must not become a character-cognition output channel.

It should not emit:

- private belief state
- social suspicion
- intent explanations

It stays strictly in the low-level runtime state domain.

## Relationship To Other Emitters

This emitter complements rather than replaces:

- physiology facts
- spatial-behavior facts
- visual facts

It covers role runtime state that is not cleanly represented by those other emitters alone.

## Success Criteria

This child spec is satisfied when role-state facts are explicitly represented as part of `System L1`, instead of being implied only by local runtime implementation details.

