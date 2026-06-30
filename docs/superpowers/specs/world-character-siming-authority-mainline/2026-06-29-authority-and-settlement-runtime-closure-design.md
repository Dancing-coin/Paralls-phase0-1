# Authority And Settlement Runtime Closure Design

Status: `execution-active`

Date: `2026-06-29`

Parent:

- [2026-06-29-world-character-siming-authority-mainline-master-design.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-world-character-siming-authority-mainline-master-design.md>)

## Scope

Define how role intent becomes world-truth requests and replayable settlement outcomes.

## Required Outcomes

1. explicit request-to-settlement pipeline
2. broadened action classes without authority collapse
3. structured success/fail/partial result semantics
4. writeback that becomes next-round world and role input

## Execution Truth

This design now has direct implementation evidence in the repository.

Current implementation/proof anchors include:

- `backend/app/main.py`
- `backend/app/models/world_result.py`
- `backend/app/services/frontend_authority_event_projection.py`
- `backend/tests/test_ws_protocol.py`
- `backend/tests/test_visual_fact_pipeline.py`
