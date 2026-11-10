# Legacy candidate world conflicts

Before candidate-world binding was enforced, separate continuity commands
could write the same candidate ID with different worlds, or add a world to a
candidate that originally had none. On recovery the former materialization
path used only the last world, permitting the wrong clock to authorize a
pending memory. The regression recreates such durable history, restarts, and
shows that both known-to-different and missing-to-known transitions were
previously materialized prematurely.

The existing history scan now treats any change of world for a candidate as
unknown provenance, keeping that candidate deferred. It does not change
stored events, receipts, already materialized memories, or runtimes without a
known-time provider. Exact continuity retries retain their original receipts.
This is a local recovery protection, not origin authentication, a general
principal read boundary, or an authority epoch. As before, scanning long
histories has not been measured against a production budget.

Windows 11, Python 3.12.2: the two new cases failed before the change;
the focused suite reported 224 passed and 8 warnings:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' -m pytest backend/tests/test_character_activation_known_world_time.py backend/tests/test_character_population_integrated_loop.py backend/tests/test_character_agent_seed_continuity.py backend/tests/test_character_session_recovery.py backend/tests/test_character_continuity_four_cursors.py backend/tests/test_population_seed_known_time.py backend/tests/test_character_activation_lease.py backend/tests/test_siming_population_capability.py backend/tests/test_siming_population_production_boundaries.py -q
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g2-legacy-world-conflict-baseline-20261110 --freeze
```

Full G0-range comparison: 10,023 nodes, 9,980 passed, 39 failed, 2 skipped,
2 xfailed, no collection errors. All 9,937 approved G0 nodes and 10,021
preceding nodes retained their setup/call/teardown outcomes; both new nodes
passed. The 39 failure node/phase/type signatures and stacks match the prior
run after normalizing pytest temporary-directory numbers and AnyIO
cancel-scope IDs. Python, OS, dependency and package hashes and pytest
environment match; source, HEAD and status were stable during the run. The
[archive](g2-legacy-candidate-world-evidence.zip) contains the frozen
manifest, environment, invocation, node list, JUnit, results and failures.

Rollback: revert this unit with the runtime stopped. No schema migration is
needed, but old conflicting candidates can again use the last recorded world
and become prematurely visible. Inspect retained candidate history and
receipts before resuming. D2-D10, G2's performance gate and B3 client
acceptance remain open.
