# M2-2 compiled FactType event-schema reference retention

- Commit: `c373a7e3`.
- Change: retain the already validated `event_schema_ref` on the compiled immutable `FactType` object. The field is optional and defaults to `None`, so direct declarations and legacy packs without a reference keep their prior shape.
- Purpose: provide a read-only source for a future event-type to FactType/visibility mapping. This increment does not add a mapping table, principal qualification, or `read_as`.
- Python: `D:\Temp\paralls-g0-py312\Scripts\python.exe`, Python 3.12.2. `app.__file__` resolved inside the A worktree. Pytest temporary and cache paths were placed under F drive.

## Verification

- TDD red: the new retention test failed with `AttributeError: 'FactType' object has no attribute 'event_schema_ref'`.
- Registry, validator, and event-schema tests: `168 passed, 2 warnings`.
- Holdings, Information production, Credential schema boundary, and package migration tests: `44 passed, 6 warnings`.
- New U11 selection: `selected=1 problems=0 improvements=0`, raw output under `F:\paralls-verification\thread-a\m2-2-event-schema-ref-20261127-selection\`.
- Focused raw outputs: `F:\paralls-verification\thread-a\m2-2-event-schema-ref-20261127-green\` and `F:\paralls-verification\thread-a\m2-2-event-schema-ref-20261127-focused\`.
- Frozen five selections were not rerun for this metadata-only increment. Full backend suite was not run.

## Remaining M2-2 work

The retained reference is a read-only input for future mapping. Principal qualification, runtime selector evaluation, event-to-FactType/visibility mapping, subject-facing `read_as`, and authoritative event-time producers remain incomplete. M2-2 remains blocked and this increment does not claim U7 or Architecture v2 completion.
