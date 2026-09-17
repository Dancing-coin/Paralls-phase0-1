# Archived Art And Legacy Scenes

This directory contains art resources and legacy presentation scenes that are
preserved for restoration and comparison, but are not part of the default
Godot runtime.

- `assets/legacy/` contains previously active project art.
- `assets/candidates/` contains art packs that are not yet promoted.
- `assets/fixtures/` contains import and pipeline fixtures.
- `assets/source/` contains DCC and source-tool files.
- `scenes/legacy/` is reserved for retired art-bound scenes.

The `.gdignore` files keep archived assets out of Godot's default scan/import
path. Do not edit archived binaries in place. Restore or activate a pack
through a future asset activation script and its manifest.

List or restore a preserved pack with:

```powershell
python tools/asset_activation.py list
python tools/asset_activation.py restore crusader_knight
```

Restore copies the pack and never changes the archive or the default
`Unified3DIntegrationValidation` scene.
