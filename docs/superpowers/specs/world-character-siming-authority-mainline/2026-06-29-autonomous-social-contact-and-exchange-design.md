# Autonomous Social Contact And Exchange Design

Status: `execution-active`

Date: `2026-06-29`

Parent:

- [2026-06-29-world-character-siming-authority-mainline-master-design.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-world-character-siming-authority-mainline-master-design.md>)

## Scope

Define the runtime framework for:

- contact opportunity detection
- approach / hold / avoid / break-contact
- greeting / probe / silence / interruption / response ownership
- public/private exchange mode

## Required Outcomes

1. explicit social-contact lifecycle
2. explicit exchange ownership semantics
3. separation of reply-style dialogue from agent-initiated utterance
4. support for multi-role contact continuity rather than one-shot reactions

## Execution Truth

This design now has direct implementation evidence in the repository.

Current implementation/proof anchors include:

- `backend/app/services/dialogue_service.py`
- `backend/app/services/character_service.py`
- `backend/app/character_agent/execution/l4_executor.py`
- `scripts/character/CharacterRuntimeState.gd`
- `scripts/character/KnightRoleSkin.gd`
- `scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd`
- `backend/tests/test_character_service.py`
- `backend/tests/test_character_agent_runtime.py`
- `backend/tests/test_ws_protocol.py`
- `python scripts/verification/verify_autonomous_social_contact.py`
