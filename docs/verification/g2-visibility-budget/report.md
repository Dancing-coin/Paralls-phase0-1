# G2 visibility budget measurement

Status: measurement complete; provisional budget accepted for implementation.

Command, from the repository root:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_visibility_baseline.py --output D:/Temp/paralls-g2-visibility-baseline/results.json
```

Environment: Windows 11 `10.0.26200`, Python 3.12.2, 30 samples after 5
warmups per row. The fixture contains 256, 1,024 and 4,096 events across four
streams and four provisional principals. The script measures the current
`read_events()` deep-copy cost and a separate metadata scan; it does not change
the runtime or claim that the provisional scan is the G2 contract.

The latest rerun's largest observed p95 values were:

| Events | Raw read p95 | Provisional principal scan p95 | Max ratio |
|---:|---:|---:|---:|
| 256 | 1.90 ms | 1.90 ms | 1.001x |
| 1,024 | 10.17 ms | 8.42 ms | 0.828x |
| 4,096 | 36.41 ms | 37.87 ms | 1.040x |

The 4,096-event public-observer row produced the maximum ratio. These values
are a local baseline, not a production SLO. Proposed budget for review: the
principal visibility step stays within 10% p95 overhead over the same raw
read, and the 4,096-event fixture stays below 40 ms p95. The technical lead
accepted this candidate budget for the next implementation step on 2026-11-10.
It remains a provisional engineering budget until paired production-shaped
sampling and real event-volume evidence are available. The final contract
still needs real visibility classes, delay/time semantics and unauthorized-read
behavior.

The output is `results.json` in this directory. The source script records the
fixture, principals, policies, environment and median/p95/p99 aggregates.
Raw and filtered reads are sampled in separate groups, so scheduling noise can
affect their ratio; repeat the measurement and use paired sampling before
making a production budget decision.
