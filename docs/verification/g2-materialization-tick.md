# Character memory materialization tick validation

This unit validates the existing character-memory materialization input; it
does not establish a trusted world clock or complete G2 visibility and epoch
enforcement. The `producer_ts` input must be a non-negative integer, excluding
booleans. Invalid inputs raise `materialization_tick_invalid` before reading
candidates or writing timeline, memory, cursor or receipts.

Subsequent call-chain inspection found that production player input can supply
Godot `Time.get_ticks_msec()` as `producer_ts`, while seed candidate
`knowledge_available_at` can originate from Population's seconds-based window.
This check validates only the representation, not the clock domain or source.
Comparing those values may materialize delayed memory early. G2 known-time
enforcement remains open until a trusted, explicitly mapped world time is used
and the real entry paths and recovery are tested.

Focused command, from the repository root:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' -m pytest backend/tests/test_character_agent_seed_continuity.py backend/tests/test_character_session_recovery.py backend/tests/test_character_continuity_four_cursors.py backend/tests/test_population_seed_known_time.py backend/tests/test_character_agent_seed_projection_parse.py -q
```

Result: 113 passed, 6 warnings. The seven invalid tick cases were first
verified to fail without the validation and then passed with it.

Full G0-range command:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g2-materialization-tick-20261110 --freeze
```

Windows 11, Python 3.12.2. The [evidence archive](g2-materialization-tick-evidence.zip)
contains environment, frozen source hashes, test manifest, invocation, JUnit,
results and failure details. It collected 9,993 nodes: 9,950 passed, 39
failed, 2 skipped and 2 xfailed; collection had no errors and source hashes
remained stable. All G0 and preceding known-time run nodes retained their
per-phase outcomes; all eight newer nodes passed. The 39 failure node, phase
and exception-type signatures match both runs. Dependency file hashes match
the preceding run.

Rollback: revert the commit containing this record and its code and tests.
This validation introduces no persistent event format. The separate prior
known-time correction has its own archive compatibility constraint and must
not be rolled back merely as part of this unit. D2-D10 remain open, and the
B3 Godot client integration is not accepted by this evidence.
