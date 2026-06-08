# System L1 Debug, Replay, And Verification Design

## Goal

Define the `Phase 1` debug / replay / verification expectations for `System L1`.

## Responsibilities

This subdomain must provide:

- debug trace visibility
- replay-relevant structured evidence
- runtime verification probes
- regression harnesses for reconnect, reseed, and fact-path integrity

## Minimum Required Surfaces

### 1. Backend regression tests

The repo should continue maintaining:

- raw-fact contract coverage
- handler behavior coverage
- candidate percept compilation coverage
- `Per-Character` filtering coverage

### 2. Godot runtime verification

The repo should continue maintaining runtime harnesses for:

- Phase 0 closed-loop behavior
- Phase1-shaped L1/L2 slice behavior
- L1 reconnect / reseed / environment-cycle edges

### 3. Audit-friendly outputs

The system should preserve:

- machine-readable JSON reports
- markdown summaries
- debug trace logs
- screenshot artifacts where relevant

## What This Subdomain Must Not Do

It must not become:

- the source of truth for world state
- a substitute for the event bus
- an ad hoc dumping ground for unrelated debugging utilities

## Success Criteria

This child spec is satisfied when `System L1` remains provable through repeatable backend and Godot verification flows, not only through manual confidence.
