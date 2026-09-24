# Task 9 Report — Archive-door embodied episode proof

## Status

Partial green: focused backend/probe/verifier tests pass with an isolated runtime database. The real Harness/Godot profile is runtime-unverified and correctly fails closed because backend startup cannot rehydrate the configured character runtime state.

## Implemented

- Added optional `TurnExecutionCorrelation` validation for `turn_id`, execution-contract identity, episode reference, and pre-capture reference.
- Threaded correlation metadata through the existing archive-door attempt and settlement path only; legacy requests without a turn remain unchanged.
- Settlement/object-result evidence preserves turn and contract/episode references; rejected settlement paths do not emit object mutation.
- Godot host/probe now records pre/post capture refs, authority result ref, expected/observed state, local terminal state, and typed recovery evidence. Success requires committed authority plus matching post observation.
- Added dedicated verifier and Harness profile requiring the complete scenario matrix, backend settlement trace, replay trace, and Godot artifacts.

## Focused verification

Command:

```text
$env:PARALLS_HEAVENLY_GRAPH_PATH=$temp_db; python -m pytest backend/tests/test_character_turn_embodied_episode.py backend/tests/test_obj_archive_door_embodied_authority.py scripts/verification/tests/test_verify_character_turn_embodied_episode.py -q
```

Result: `17 passed, 4 warnings`.

## Runtime verification

Command:

```text
$env:PARALLS_HEAVENLY_GRAPH_PATH=$temp_db; python scripts/verification/harness.py --profile character-turn-embodied-episode
```

Result: exit code `1`; `overall_passed=False`.

Blocker: the existing backend runtime reset fails before the live server starts while rehydrating persisted character state: `CharacterDynamicState` reports missing `vigilance_level` and `distraction_level`. Godot runtime artifacts therefore cannot be claimed. The dedicated verifier rejects the non-zero live verifier exit and stale/incomplete evidence rather than reporting success.

## Scope

Changed only the Task 9 implementation, test, verifier, profile, and report files. Existing unrelated worktree changes were preserved. No new authority, transport, cognition, or raw-pose path was introduced.
