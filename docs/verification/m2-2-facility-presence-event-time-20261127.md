# M2-2 Facility and Presence event-time producer

- Code commit: `35cf812a88ae970ac899e43bae734a507c0de87f`.
- Parent: `357cbdea0b2b09ff57ce2b9490312807e62c4a8b`.
- Scope: persist the trusted M6-5 world tick on newly accepted signed physical inputs and propagate that exact input time to derived Facility and Presence events. Exact retries reuse the durable input time without reading a new tick. Legacy inputs with no `event_time` continue to produce events with no time.
- The change does not map `physics_tick` to world time, use stream/global sequence as time, or implement `read_as`.

## Environment

- Python `3.12.2`; SQLite `3.43.1`.
- `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`; `app.__file__` resolved to that worktree.
- `TEMP`, `TMP`, pytest basetemp, raw output and parent verification worktree were on F:.

## Verification

- TDD red: the retry regression failed because a duplicate signed impact consumed tick `701` after the original tick `700`.
- Focused command: `D:\Temp\paralls-g0-py312\Scripts\python.exe -m pytest backend/tests/test_facility_gate_layered_runtime.py backend/tests/test_facility_integrity_runtime.py backend/tests/test_place_passability_runtime.py backend/tests/test_siege_physical_input_runtime.py backend/tests/test_m6_5_siege_runtime.py -q`. Result: `83 passed, 6 warnings`.
- Frozen comparison command: `docs/verification/absorb-main-3bf3418e/compare_selection.py`, against commit `35cf812a`. Results: new selection `2/0/0`; Ownership `24/0/0`; Modifier `12/0/0`; Equipment `87/0/0`; Inventory `56/0/0`; shared-replay `990/0/0`, in selected/problems/improvements order. Frozen selections total 1,169 nodes.
- Backend full command: `python -m pytest backend/tests -q --basetemp F:\paralls-verification\thread-a\m2-2-event-time-owner-producers-20261127-10\pytest-temp`. Result: `10,797 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings`, exit code 1. This is not a full-suite pass.
- The five failed nodes were calibration tokenizer availability, CharacterTask45 Godot parsing, population `cold_ready`, population recovery fixture generation, and Task8 Godot parsing. The full-run recovery failure reported malformed inherited `GIT_CONFIG_VALUE_0`; the node passed alone with `GIT_CONFIG_COUNT=0` (`1 passed, 2 warnings`).
- The same five node IDs were selected at parent `357cbdea` with `GIT_CONFIG_COUNT=0`; result `4 failed, 1 passed, 2 warnings`. Calibration, both Godot probes, and `cold_ready` failed there. `cold_ready` also failed alone on the current commit because `resource_bounds.passed` was false. In the full current run it instead raised `KeyError: resource_bounds`, so its failure details vary by execution context.

## Raw outputs

- TDD red and focused tests: `F:\paralls-verification\thread-a\m2-2-event-time-owner-producers-20261127-08\`; focused raw output and environment: `...-14\focused.log` and `...-14\environment.log`.
- New selection and frozen groups: `F:\paralls-verification\thread-a\m2-2-facility-presence-event-time-20261127-01\`.
- Current full backend: `F:\paralls-verification\thread-a\m2-2-event-time-owner-producers-20261127-10\full-backend.log`.
- Recovery with clean Git configuration: `F:\paralls-verification\thread-a\m2-2-event-time-owner-producers-20261127-11\`.
- Parent failure comparison: `F:\paralls-verification\thread-a\m2-2-event-time-owner-producers-20261127-12\`.
- Current isolated `cold_ready`: `F:\paralls-verification\thread-a\m2-2-event-time-owner-producers-20261127-13\`.

## Remaining M2-2 work

M2-2 remains blocked. The authoritative event-time producer now covers the M6-5 signed impact and Presence assessment paths, alongside the previously recorded Information and Morale producers. The shared principal qualification and selector evaluator, runtime event-type-to-FactType/visibility consumer, reader classification, and subject-facing `read_as` entry point are still absent. Other migrated-domain time sources also need inventory. U7 is not complete.
