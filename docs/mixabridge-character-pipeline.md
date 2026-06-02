# mixabridge Character Pipeline

Purpose:

- connect `A/B/C` to one shared skeleton and animation preparation path

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
