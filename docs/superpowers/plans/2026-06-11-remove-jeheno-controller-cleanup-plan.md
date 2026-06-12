# Remove JehenoThirdPersonController Cleanup Plan

Goal: remove `res://addons/JehenoThirdPersonController/` completely and keep the Phase 0 demo runnable through project-owned player shell, camera, and input code.

## Cleanup Sequence

1. Replace the plugin `PlayerCharacter` scene with `scenes/phase0/PlayerShell.tscn`.
2. Implement `scripts/player/PlayerShell.gd` with the minimum interface currently consumed by `Phase0PlayerBridge.gd` and `MainDemoController.gd`.
3. Keep `CharacterC` as the visible role shell and keep `KnightRoleSkin.gd` as the only role animation/root-motion source.
4. Rewire `MainDemo.tscn` and preview scenes away from `addons/JehenoThirdPersonController`.
5. Remove plugin-only scripts, scenes, assets, docs references that are not historical design docs, and helper scripts that preload plugin assets.
6. Run `python scripts/verification/harness.py --profile godot-project`, then broader runtime verification if static checks pass.

## Behavior To Preserve

- `Player` remains a `CharacterBody3D` collision/camera shell.
- `Phase0PlayerBridge` can still read movement actions, trigger jump variants, and write shell velocity from `CharacterC` root motion.
- `MainDemoController` can still orient the player, find `CameraHolder/SpringArm3D/Camera3D`, and run locomotion probes.
- `CharacterA`, `CharacterB`, and `CharacterC` remain visible through `KnightRoleSkin`.
