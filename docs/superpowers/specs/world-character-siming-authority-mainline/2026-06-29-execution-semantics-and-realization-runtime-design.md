# Execution Semantics And Realization Runtime Design

Status: `execution-active`

Date: `2026-06-29`

Parent:

- [2026-06-29-world-character-siming-authority-mainline-master-design.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-world-character-siming-authority-mainline-master-design.md>)

## Scope

Define the downstream execution semantics layer under `L4`, while keeping current light Godot realization as a transitional compatibility host.

## Required Outcomes

1. canonical semantics for movement, stance, speech, gesture, and physiology realization
2. no overfitting to current local lightweight realization
3. explicit seam between execution semantics and realization backends
4. future-proofing for asset-runtime and Kimodo-backed realization

## Execution Truth

This design now has direct implementation evidence in the repository.

Current implementation/proof anchors include:

- `backend/app/character_agent/execution/l4_executor.py`
- `scripts/character/CharacterPresentationInput.gd`
- `scripts/character/CharacterRuntimeState.gd`
- `scripts/character/CharacterReplica.gd`
- `backend/tests/test_character_agent_runtime.py`
- `backend/tests/test_character_actor_boundary_audit.py`
