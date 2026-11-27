# M2-2 FactType event-schema index

- Commit: `a7de5080`.
- Change: `FactTypeRegistry` now exposes an immutable `facts_by_event_schema_ref` index derived from the already validated optional `FactType.event_schema_ref` values. Entries preserve compiled FactType objects and are grouped by the exact declared reference.
- Boundary: no alias canonicalization, event-type inference, principal qualification, visibility evaluation, or `read_as` behavior is introduced.
- Python: `D:\Temp\paralls-g0-py312\Scripts\python.exe`, Python 3.12.2. `app.__file__` resolved inside the A worktree. Pytest temporary and cache paths were on F drive.

## Verification

- TDD red: the new index test failed with `AttributeError: 'FactTypeRegistry' object has no attribute 'facts_by_event_schema_ref'`.
- Registry, RulePack, FactType, and EventSchema tests: `169 passed, 2 warnings`.
- Holdings, Information, Credential schema boundary, and package migration tests: `44 passed, 6 warnings`.
- New U11 selection: `selected=1 problems=0 improvements=0` will be recorded under `F:\paralls-verification\thread-a\m2-2-event-schema-index-20261127-selection\`.
- Frozen five selections and full backend suite were not run for this derived metadata increment.

## Remaining M2-2 work

The index is only a read-only mapping input. Principal qualification, selector evaluation, event-type to FactType/visibility mapping, subject-facing `read_as`, and authoritative event-time producers remain incomplete. M2-2 remains blocked.
