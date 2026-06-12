# mixabridge Character Pipeline

Purpose:

- keep an optional offline asset-preparation path for `A/B/C` skeleton normalization and animation library setup

Status:

- `mixabridge` is available as a repository-local editor/offline tool
- it is not part of the current Phase 0 runtime dependency chain
- runtime scenes should continue to consume prepared assets from `assets/characters/...`

Use `mixabridge` for:

- skeleton discovery
- bone map generation
- animation scene extraction
- preparing a shared minimal action set

Required first action set:

- idle
- locomotion
- turn/look
- speak
- inspect/guard
- alert/recoil
- hold-ground/observe

Mount rule:

- keep `CharacterReplica` as the outer shell
- mount imported role assets under `VisualRoot/AssetMount/.../ImportedModel`
