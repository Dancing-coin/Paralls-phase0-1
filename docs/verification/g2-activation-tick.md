# Activation materialization tick admission

The earlier materialization tick validation rejected invalid ticks, but an
activation acquired and released a durable authority lock first. This unit
validates the tick after existing activation admission checks and before the
lock when private memory will be loaded. Direct materialization keeps the
same validation. Busy activation retains its existing rejection precedence.
This is not a trusted world-clock source or general G2 enforcement.

Focused command from the repository root:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' -m pytest backend/tests/test_character_activation_lease.py backend/tests/test_character_agent_activation_handoff.py backend/tests/test_character_agent_seed_continuity.py backend/tests/test_character_session_recovery.py backend/tests/test_character_continuity_four_cursors.py backend/tests/test_population_seed_known_time.py backend/tests/test_character_agent_seed_projection_parse.py -q
```

136 passed, 6 warnings. Six invalid ticks were first verified to raise after
writing lock and release events, and then verified to raise without changing
the authority snapshot or leaving a lease. The activation lease suite was
rerun after adding the busy-admission precedence assertion: 20 passed, 2
warnings.

Full G0-range command:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g2-activation-tick-20261110 --freeze
```

Windows 11, Python 3.12.2. The [evidence archive](g2-activation-tick-evidence.zip)
contains environment, source hashes, manifests, invocation, JUnit, results and
failure details. 10,000 nodes were collected: 9,957 passed, 39 failed, 2
skipped and 2 xfailed. There were no collection errors, source hashes remained
stable, and Python, OS, installed-package hash, dependency file hashes and
pytest environment matched the preceding full run. All G0 and preceding run
nodes retained their per-phase outcomes; all seven newer nodes passed. The 39
failure node, phase and exception-type signatures match both runs.

Rollback: revert the commit containing this record and its code and tests;
this unit creates no new persisted event format. The earlier known-time
correction has a separate archive compatibility constraint and should not be
reverted as part of this unit. D2-D10 remain open and B3 Godot integration is
not accepted by these tests.
