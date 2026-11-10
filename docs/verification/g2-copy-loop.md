# In-memory event copy guard loop

The scalar-copy guard now checks payload and event fields with explicit loops.
The accepted types, model-state checks, independent scalar payload copy and
deep-copy fallback are unchanged. Both stream and global reads use the same
guard; the durable store and persisted formats are unchanged.

On Windows 11 with the G0 Python 3.12.2 environment, the contract,
persistence, connection, JSON cache and codec suites reported 71 passed and
2 warnings both before and after the change. They include scalar payload and
field-set isolation, nested aliases and attached state, as well as durable
cache and codec behavior.

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' -m pytest backend/tests/test_gameplay_event_store_contract.py backend/tests/test_gameplay_event_store_persistence.py backend/tests/test_gameplay_event_store_connection.py backend/tests/test_gameplay_event_store_json_cache.py backend/tests/test_gameplay_event_store_codec_compatibility.py -q
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/g2-copy-loop-baseline-20261110 --freeze
```

The full serial G0-range comparison collected 10,034 nodes: 9,991 passed,
39 failed, 2 skipped and 2 xfailed. All G0 nodes and the 10,033 nodes in the
previous full run retained setup, call and teardown outcomes. Failure node,
phase and type signatures and stacks match after normalizing pytest temporary
directory numbers and AnyIO cancel-scope IDs. There was one added node since
the previous run, from the scalar isolation test already run separately after
that run. Python, executable, OS, dependency hashes and pytest environment
matched; source, HEAD and status were stable during the run. Results and
environment are in the [evidence archive](g2-copy-loop-evidence.zip).

Two independent runs of the existing synthetic paired fixture used 60 samples
per row after five warmups. Their maximum 4,096-event filtered p95 values were
28.60 and 29.19 ms; the maximum p95 ratios across all rows were 1.054 and
1.079. Samples are in the archive. A preliminary same-process alternating
copy-only experiment gave 16.01/13.59 ms median and 29.58/24.34 ms p95 for
the previous/current guards; that experiment is exploratory, not a budget
test. The fixture scans counts over scalar events and does not implement real
authorization, time, durable reads or production traffic. These two runs do
not erase prior exceedances or close the G2 visibility gate; D6 remains open.

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_paired.py --output D:/Temp/g2-copy-loop-paired-a.json
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_paired.py --output D:/Temp/g2-copy-loop-paired-b.json
```

Rollback: revert this unit's commit. There are no stored-data or schema
changes. This does not implement principal authorization, three-time replay or
authority epoch fencing; D2–D10 and B3 client acceptance remain open.
