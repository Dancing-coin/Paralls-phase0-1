# Durable event scan cache admission

When a durable event query returns more rows than the decoded-text cache can
hold, new decoded event bodies from that query no longer enter the cache.
Existing cached bodies can still be used, and every row is decoded as needed
and validated into a fresh model. The admission scope uses a per-store context
variable, reset even on failure, so concurrent point reads retain their normal
cache behavior. Small queries, writes, other model types, stored data and
snapshot formats retain their existing paths.

The focused regression first reproduced eviction of a hot point-read entry.
Tests cover caller mutation isolation, corruption rejection and recovery,
cache behavior after failure, and an overlapping point read while a scan is
paused. The existing codec, persistence, idempotency and connection tests also
ran. Windows 11, Python 3.12.2: 69 passed, 2 warnings.

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' -m pytest backend/tests/test_gameplay_event_store_json_cache.py backend/tests/test_gameplay_event_store_codec_compatibility.py backend/tests/test_gameplay_event_store_persistence.py backend/tests/test_gameplay_event_store_contract.py backend/tests/test_gameplay_event_store_connection.py -q
```

The same synthetic durable-read diagnostic described in
`g2-visibility-budget/report.md` was run twice with the modified runtime.
For 4,096 events, read-plus-fixture-scan p95 ranged 36.84–41.23 ms in the
first run and 36.97–38.12 ms in the second. The first run's debug row exceeds
40 ms; the later run does not erase that result or prior exceedances. The
fixture is not the real `read_as` authorization contract, and the G2 performance
gate remains open. Full per-sample data and fixture paths are in the archive.

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_durable_read.py --output D:/Temp/paralls-g2-scan-cache-perf-20261110.json
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_durable_read.py --output D:/Temp/paralls-g2-scan-cache-perf-repeat-20261110.json
```

Full G0-range run:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g2-scan-cache-baseline-20261110 --freeze
```

10,015 nodes: 9,972 passed, 39 failed, 2 skipped, 2 xfailed, no collection
errors. All 10,012 preceding nodes retained their setup/call/teardown outcomes;
the three new nodes passed. The 39 failure node/phase/type signatures and
stacks after normalization of dynamic AnyIO cancel-scope IDs match the prior
run. Python, OS, dependency and package hashes and pytest environment match;
source and HEAD were unchanged during the run. The [evidence archive](g2-scan-cache-evidence.zip)
contains both performance runs and the full test environment, frozen manifest,
node list, JUnit, results, failure details and invocation.

Rollback: revert this unit's commit. No data migration is required; reverting
restores cache insertion and possible eviction of hot entries during large
scans. Cached content is not authoritative. This change does not implement
principal visibility, complete three-time semantics or authority epoch fencing.
D2-D10 and B3 client acceptance remain open.
