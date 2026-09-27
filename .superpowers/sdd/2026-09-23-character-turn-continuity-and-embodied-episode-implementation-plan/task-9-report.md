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

## Review retry follow-up

- Archive-door intents now carry optional turn/execution-contract/episode/pre-capture pins; the live route passes validated correlation into embodied preflight while legacy intents remain uncorrelated.
- The dedicated verifier requires the legacy overall pass flag, backend/replay/runtime/screenshot artifacts, and verifies referenced paths when running the profile.
- The Godot probe rejects success when request, settlement, world-result, and replay correlation refs disagree, and no longer invents `episode::` for uncorrelated failures.

Targeted verifier/ESM tests pass (`41 passed`). Focused backend authority collection remains blocked by the existing persisted-state rehydration error (`vigilance_level` and `distraction_level` missing).

## Re-review 1 follow-up

Embodied action requests and world results now preserve execution-contract and episode refs (plus pre-capture on the request); settlement payloads expose an observed replay join, and the Godot probe validates that join rather than synthesizing one. The verifier requires named screenshots for success and each typed failure scenario. Targeted tests and backend compile checks pass; the persisted-state runtime blocker remains unchanged.

## Re-review 2 follow-up

The archive-door probe now uses explicit `Variant` typing at the reported inference site and the probe script/root scene are both `Node3D`, eliminating the script attachment type mismatch. Static Godot/verifier tests pass (`30 passed`). A Godot executable was not available in this environment, so headless runtime parsing remains unverified.
