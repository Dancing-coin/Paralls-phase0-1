# System L1 Visual Fact System Phase 1 Design

## Goal

Define the full `Phase 1` visual-fact system expected inside `System L1`.

This child spec consolidates:

- source domains
- emitter layout
- derived evidence projection role
- Godot-side processing chain

## Role

The visual-fact system is the structured visible-truth output of `System L1`.

It answers:

- what visually changed
- who is visually present
- what object state is visibly different
- what environment state is visibly different
- what spatial relation is visibly salient

It does not answer:

- who definitely perceived it
- what it means socially
- whether it has already become role-private knowledge

## Processing Chain

The fixed local chain is:

`Visible Runtime State -> Local Sampling -> Semantic Extraction -> Source-Domain Emitters -> Evidence Projection -> Event Bus`

## Required Source Domains

The `Phase 1` visual-fact system must implement:

1. `CharacterVisualFactEmitter`
2. `ObjectVisualFactEmitter`
3. `EnvironmentVisualFactEmitter`
4. `SpatialRelationVisualFactEmitter`
5. `EvidenceProjectionEmitter`

## CharacterVisualFactEmitter

Responsible for:

- gaze
- visible anomaly state
- visible motion or stance cues
- visible orientation or signaling

## ObjectVisualFactEmitter

Responsible for:

- object visible presence
- object movement or removal
- open/closed or intact/damaged-like visible object state
- concealment / reveal surface state

## EnvironmentVisualFactEmitter

Responsible for:

- light
- smoke
- fire
- visible access boundary changes
- visible environment transitions

## SpatialRelationVisualFactEmitter

Responsible for:

- actor-actor visible relation
- actor-object visible relation
- actor-spacepoint visible relation
- conversation-circle visibility-adjacent spatial patterns

## EvidenceProjectionEmitter

Consumes the previous four domains and emits:

- evidence-relevant projections

It does not sample the world directly.

## Current Priority

The current repo already has partial character and environment emission plus some spatial-access adjacent coverage.

The first missing `Phase 1` completions should be:

- `ObjectVisualFactEmitter`
- `SpatialRelationVisualFactEmitter`
- `EvidenceProjectionEmitter`

## Success Criteria

This child spec is satisfied when all four primary source-domain emitters and the evidence-projection layer are present as explicit `System L1` subcomponents.

