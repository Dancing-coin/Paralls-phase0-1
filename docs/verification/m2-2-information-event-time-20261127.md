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

## Remaining M2-2 work

M2-2 remains blocked and U7 is unmet. There is no shared principal qualification source or selector interpreter, no production event-type-to-FactType visibility mapping, and no identified subject-facing Ownership/Credential reader to wire. Other event types still have unknown `event_time` unless their authoritative producer is explicitly connected.
