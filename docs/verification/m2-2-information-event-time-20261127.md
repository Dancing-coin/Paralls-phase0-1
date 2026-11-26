# M2-2 Information report event-time producer

- Base: `207dd8d7317095b8c85c05d64656a0858294f690`.
- Code commit: `583cf8df` (`feat(information):persist-report-event-time`).
- Python: `D:\Temp\paralls-g0-py312\Scripts\python.exe`, Python 3.12.2; SQLite 3.43.1.
- Import check: with `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`, `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.

## Change

`InformationAuthority.publish_siege_report` validates `world_now` against its configured world-tick provider and writes it as `published_at_world_tick`. Production assembly supplies `_session_world_clock_tick`, which returns `SimulationDriver.current_tick` only while a driver is available and not migrating. The committed report event now also stores that same authoritative tick in top-level `GameplayEvent.event_time`. Existing payload fields, event type, schema version, visibility, and idempotency key are unchanged. An exact retry replays the originally committed event. Historical report events without `event_time` remain unknown.

This establishes an event-time producer for Information report publication only. It does not establish a generic producer for other Owners, a principal qualification source, a selector interpreter, an event-type-to-FactType/visibility mapping, or `read_as`.

## Verification

The failing-first assertion was run against the implementation before the change:

```text
set PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend
python -m pytest -q backend/tests/test_siege_information_runtime.py::test_information_owner_publishes_signed_report_and_replays_after_window
1 failed: expected report.event_time == 15, received None
```

After implementation, with the same `PYTHONPATH` and interpreter:

| Check | Result |
|---|---|
| `backend/tests/test_siege_information_runtime.py` | 12 passed, 2 warnings |
| `backend/tests/test_gameplay_event_store_persistence.py` | 26 passed, 2 warnings |
| `m6-5-information-report-source.json` | selected=25, problems=0, improvements=0 |
| Frozen `ownership.json` | selected=24, problems=0, improvements=0 |
| Frozen `shared-replay.json` | selected=990, problems=0, improvements=0 |

Raw command output is under `F:\paralls-verification\thread-a\m2-2-information-event-time-20261127-02\`. The full backend suite was not run for this increment.

## Full backend verification

The required full backend run was then executed with `PYTHONPATH` set to the A worktree, `GIT_CONFIG_COUNT=0`, and `TEMP`, `TMP`, `TMPDIR`, and pytest `--basetemp` all rooted under `F:\paralls-verification\thread-a\m2-2-information-event-time-full-20261127-01\`. Python 3.12.2 and the A worktree `app.__file__` were verified before the run.

```text
pytest -v backend/tests
10,744 passed, 22 failed, 2 skipped, 2 xfailed, 227 warnings in 1377.68s (0:22:57)
exit code 1
```

The 21 failures in the calibration, Godot or external-engine, cold-ready, population harness/capacity/recovery, and role-presentation files reproduced at parent `207dd8d7` in a focused parent run. The remaining full-run `runtime_process_transport` failure passed when isolated on both parent and current tip, so it is an order/environment-sensitive full-run failure rather than an Information regression. No Information report test failed. This is a full-run result with failures, not a full-suite pass. The first interrupted attempt wrote a D-drive pytest directory before its process was stopped. Its owned 546.70 MB of regular files were moved to the F-drive evidence directory. The rerun and all retained pytest basetemp data used F drive only.

## Remaining M2-2 work

M2-2 remains blocked and U7 is unmet. There is no shared principal qualification source or selector interpreter, no production event-type-to-FactType visibility mapping, and no identified subject-facing Ownership/Credential reader to wire. Other event types still have unknown `event_time` unless their authoritative producer is explicitly connected.
