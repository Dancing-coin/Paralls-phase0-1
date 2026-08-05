# Task 3 Recovered Implementation Report

## Status

DONE. This task was recovered from the prior execution session and committed as `3be1342`.

## Scope

- `obj_letter` now has an ESM-authoritative `visible -> removed_from_surface` transition.
- Godot applies only the applied Authority result to hide the visual, label, and collision.
- `siming.staging_request` is projected to Godot and backend Character/ESM staging ACKs are generated idempotently.
- Godot accepts staging after backend reconnect and emits a structured `char_b` tick input.
- `char_b` perceived memory retains target references and destruction lineage.

## Verification

- `python -m pytest backend/tests/test_siming_heavenly_staging_transport.py -q`: 3 passed, 1 warning.
- Focused runtime regression command: 66 passed, 1 warning.
- `python -m pytest backend/tests/test_siming_heavenly_godot_static.py -q`: 4 passed, 1 warning.
- `git diff --check`: passed.
- Godot scene-load verification remains pending for the next checkpoint.

## Fix Round 1

### Status

DONE pending only the pre-existing MainDemo parse error outside Task 3.

### Fixes

- The real default-scene letter bridge now advertises and resolves `destroy`.
- `InteractiveObject.gd` indentation is valid GDScript and still applies only the authoritative `removed_from_surface` result.
- The heavenly probe preserves confirmed destruction through unrelated results, requires exactly one `char_b` reaction correlated or causally tied to the staging request, and validates each capture with the existing sampled-pixel check.
- Character execution envelopes retain command causation/correlation; duplicate Godot staging ACKs are suppressed before publishing another Authority event/tick.

### Verification

- `python -m pytest backend/tests/test_siming_heavenly_staging_transport.py backend/tests/test_siming_heavenly_godot_static.py backend/tests/test_default_scene_letter_affordance_static.py backend/tests/test_esm_service.py backend/tests/test_siming_heavenly_runtime_tick.py -q`: 62 passed, 1 existing deprecation warning.
- `D:\godot\Godot_v4.6.3-stable_win64_console.exe --headless --path . --scene res://scenes/phase0/DefaultSceneLetterAffordanceProbe.tscn --quit-after 300 --render-thread safe`: exit 0; `default_scene_letter_affordance_probe:verified=true`.
- MainDemo scene load exited 0 but emitted the pre-existing `scripts/player/PlayerIntentMapper.gd:51` mixed-indentation parse error. That file was not changed by this Task 3 fix.
- `git diff --check`: passed.
