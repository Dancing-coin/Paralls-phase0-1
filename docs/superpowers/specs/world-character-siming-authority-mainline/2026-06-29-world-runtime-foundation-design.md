# World Runtime Foundation Design

Status: `execution-active`

Date: `2026-06-29`

Parent:

- [2026-06-29-world-character-siming-authority-mainline-master-design.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-world-character-siming-authority-mainline-master-design.md>)

## Scope

Define the outer runtime organism that roles live inside:

- world interface
- fact fabric
- world-state projection
- runtime identity of actors/objects/environments/zones
- outer-loop state change semantics

## Required Outcomes

1. one canonical world-runtime vocabulary
2. explicit actor/object/environment/zone abstractions
3. stable fact-family routing rules
4. clear writeback ownership boundaries

## Execution Truth

This design now has direct implementation evidence in the repository.

Current implementation/proof anchors include:

- `backend/app/world_runtime/models.py`
- `backend/app/world_runtime/fact_registry.py`
- `backend/app/world_runtime/projection.py`
- `backend/tests/test_world_runtime_models.py`
- `backend/tests/test_world_runtime_fact_registry.py`
- `backend/tests/test_world_runtime_projection.py`
