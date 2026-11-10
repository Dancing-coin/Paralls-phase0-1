# In-memory event read copy

The in-memory store now copies a plain `GameplayEvent` with only immutable
scalar fields and a plain scalar-valued payload using a shallow model copy and
an independent payload dictionary. Any nested value, subclass, extra model
state or nonstandard metadata uses the original deep-copy path. The field-set
metadata is preserved. Both stream and global reads retain their lock and
return independent objects; the durable store is unchanged.

On Windows 11, Python 3.12.2, the event store contract, persistence,
connection, JSON cache and codec tests reported 70 passed, 2 warnings. The
contract suite was rerun after adding a scalar field-set and mutation check:
16 passed, 2 warnings. A nested alias and attached-cache regression also checks
that fallback preserves aliasing and isolation.

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' -m pytest backend/tests/test_gameplay_event_store_contract.py backend/tests/test_gameplay_event_store_persistence.py backend/tests/test_gameplay_event_store_connection.py backend/tests/test_gameplay_event_store_json_cache.py backend/tests/test_gameplay_event_store_codec_compatibility.py -q
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' -m pytest backend/tests/test_gameplay_event_store_contract.py -q
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/g2-event-copy-baseline-20261110 --freeze
```

The full G0-range run collected 10,033 nodes: 9,990 passed, 39 failed, two
skipped and two xfailed. All G0 and previous 10,032 nodes retained their
setup/call/teardown outcomes. Failure node, phase and type signatures and
stacks match after normalizing pytest temporary directory numbers and AnyIO
cancel-scope IDs. Environment, source and HEAD were stable during the run.
The later scalar regression was run separately, after the full run; no runtime
code changed between them. Raw results and environment are in the
[evidence archive](g2-event-copy-evidence.zip).

Two synthetic paired visibility measurements used the existing fixture and
60 samples per row. The 4,096-event filtered p95 ranges were 18.96–19.40 ms
and 27.86–30.61 ms. The second run exceeded the provisional 10% ratio at
1,024 private-owner (1.73) and 4,096 public-observer (1.22); prior budget
exceedances also remain. This fixture uses simple payloads and a count-only
scan, not real authorization, durable reads or a production workload. The
G2 visibility performance gate remains open.

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_paired.py --output D:/Temp/g2-event-copy-paired-20261110.json
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_paired.py --output D:/Temp/g2-event-copy-paired-repeat-20261110.json
```

Rollback: revert this unit's commit; no persisted data or schema changes. This
does not implement principal authorization, three-time replay or epoch fencing.
D2–D10 and B3 client acceptance remain open.
