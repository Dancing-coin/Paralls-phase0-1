# Session projection after durable reopen

After a durable store reopen with an empty authority bus, pulling a committed
session event previously raised `KeyError`: the fallback consulted the new
service's empty in-memory session table. A WebSocket regression reproduced the
handler failure. The pull now reconstructs the public projection from the
validated persisted outbox when the in-memory session is absent. If the outbox
is missing or mismatched, it projects only the committed event's allowlisted
fields instead of requiring an in-memory session. The outbox and event are not
changed. This does not restore the session command state after a restart or
establish principal authorization, propagation timing, or Godot acceptance.

Windows 11 and Python 3.12.2: the restart regression failed before the fix;
the focused session file passed 16 tests (6 deprecation warnings). The new
cases close and reopen a real SQLite store and pull over WebSocket with an empty
bus, both with and without access to the outbox.

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' -m pytest backend/tests/test_embodied_interaction_session.py -q --disable-warnings
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/g2-session-restart-baseline-20261110 --freeze
```

Full G0-range run: 10,032 nodes, 9,989 passed, 39 failed, 2 skipped,
2 xfailed, no collection errors. All 9,937 G0 and 10,030 preceding nodes
retain their phase outcomes; two new nodes pass. Failure signatures and stacks
match both baselines after normalizing pytest temporary directory numbers and
AnyIO cancel-scope identifiers. Python, OS, dependency and pytest environment
match the preceding run; source, HEAD and status stayed stable during the run.
The [archive](g2-session-projection-restart-evidence.zip) includes raw results,
environment, frozen inventory and comparison script. The 39 approved failures
remain unresolved.

Rollback: revert this commit. No data migration is involved; after rollback,
the no-bus pull can again fail after service restart. G2, D2-D10, the synthetic
performance gate and B3 client acceptance remain open.
