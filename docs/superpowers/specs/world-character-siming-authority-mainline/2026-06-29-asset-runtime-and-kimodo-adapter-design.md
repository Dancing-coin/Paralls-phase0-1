# Asset Runtime And Kimodo Adapter Design

Status: `execution-active`

Date: `2026-06-29`

Parent:

- [2026-06-29-world-character-siming-authority-mainline-master-design.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-world-character-siming-authority-mainline-master-design.md>)

## Scope

Define the final-target realization backend:

- embodiment asset runtime
- preload/cache/fallback behavior
- Kimodo real-time action generation adapter
- local skeletal or bone-space presentation

## Required Outcomes

1. explicit asset indexing and capability binding model
2. on-demand preload policy
3. Kimodo adapter contract
4. generated-motion plus local-asset fallback composition rules

## Execution Truth

This design now has direct implementation evidence in the repository.

Current implementation/proof anchors include:

- `scripts/character/CharacterEmbodimentAssetRuntime.gd`
- `backend/app/character_agent/execution/kimodo_adapter_contract.py`
- `backend/tests/test_character_asset_runtime_static.py`
- `backend/tests/test_kimodo_adapter_contract.py`
- `.harness/verification/mainline-unified-runtime-report.json`
