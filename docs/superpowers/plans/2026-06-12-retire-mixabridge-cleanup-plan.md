# Retire Mixabridge Cleanup Plan

Goal: remove `mixabridge` as a repository dependency so the Phase 0 demo and its documentation only describe the current project-owned character asset pipeline.

## Cleanup Sequence

1. Remove `res://addons/mixabridge/` from the repository if it is no longer referenced by runtime or editor configuration.
2. Remove `docs/mixabridge-character-pipeline.md` and any docs-index links that present it as an active pipeline document.
3. Update remaining asset and character docs to describe the current project-owned `assets/characters/...` pipeline without `mixabridge` language.
4. Update verification tests that currently assert `mixabridge` documentation exists so they instead assert the current character asset staging guidance.
5. Run static harness profiles that cover docs, drift, and Godot project integrity.

## Behavior To Preserve

- `MainDemo.tscn` remains the project main scene.
- Character assets continue to mount from the project-owned `assets/characters/...` pipeline.
- Harness docs and verification tests continue to describe the current repo truth rather than historical plugin plans.
