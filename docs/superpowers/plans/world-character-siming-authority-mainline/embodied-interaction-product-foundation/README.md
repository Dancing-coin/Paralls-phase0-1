# Embodied Interaction Product Foundation Plan Tree

Status: `drafted-for-spec-review`

Date: `2026-07-29`

This plan tree implements the matching embodied-interaction specification only
after its `awaiting-user-review` gate is approved. It intentionally excludes
TTS, streamed dialogue, visemes, and broad presentation-content work.

## Plan Order

1. [Implementation plan](2026-07-29-embodied-interaction-product-foundation-implementation-plan.md)
2. [Atomic action library and default scene coverage](2026-08-01-atomic-action-library-and-default-scene-coverage-plan.md)

The plan's phases are sequential at their contract boundaries. Within a phase,
backend tests and isolated Godot asset/controller work may be parallelized only
after their shared schemas are frozen.
