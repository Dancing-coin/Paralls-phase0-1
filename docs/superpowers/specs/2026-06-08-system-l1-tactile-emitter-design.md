# System L1 Tactile Fact Emitter Design

## Goal

Define the tactile raw-fact emitter expected inside `System L1` for `Phase 1`.

## Responsibilities

The tactile emitter should capture structured low-level tactile facts such as:

- contact occurred
- contact source / target
- contact persistence
- collision category
- surface contact class
- touch or impact intensity band

## What It Must Not Do

It must not produce:

- pain interpretation
- social meaning
- “this character noticed the touch”

Those belong above `System L1`.

## Relationship To ESM

`ESM` may settle whether a contact/impact changes state.

The tactile emitter expresses:

- the contact fact itself
- its low-level characteristics

## Success Criteria

This child spec is satisfied when tactile raw facts are a first-class `System L1` emitter domain, not a missing placeholder.

