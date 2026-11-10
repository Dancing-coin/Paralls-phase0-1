# G2 visibility budget measurement

Status: two paired runs complete; one exceeds the provisional budget and G2 visibility expansion is paused.

Command, from the repository root:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_visibility_baseline.py --output D:/Temp/paralls-g2-visibility-baseline/results.json
```

Environment: Windows 11 `10.0.26200`, Python 3.12.2, 30 samples after 5
warmups per row. The fixture contains 256, 1,024 and 4,096 events across four
streams and four provisional principals. The script measures the current
`read_events()` deep-copy cost and a separate metadata scan; it does not change
the runtime or claim that the provisional scan is the G2 contract.

The first grouped rerun's largest observed p95 values were:

| Events | Raw read p95 | Provisional principal scan p95 | Max ratio |
|---:|---:|---:|---:|
| 256 | 1.90 ms | 1.90 ms | 1.001x |
| 1,024 | 10.17 ms | 8.42 ms | 0.828x |
| 4,096 | 36.41 ms | 37.87 ms | 1.040x |

The 4,096-event public-observer row produced the maximum ratio in that
grouped run. Because raw and filtered calls were sampled in separate groups,
the result was repeated with alternating paired calls. The paired rerun is
stored in `paired-results.json` and was run with 60 samples after 5 warmups.
Its largest rows were:

| Events | Principal | Raw p95 | Paired filtered p95 | p95 ratio |
|---:|---|---:|---:|---:|
| 256 | `principal:town-authority` | 2.11 ms | 2.08 ms | 0.99x |
| 1,024 | `principal:debug-probe` | 11.23 ms | 12.40 ms | 1.104x |
| 4,096 | `principal:debug-probe` | 45.68 ms | 46.70 ms | 1.022x |

The paired 4,096-event row exceeds the provisional 40 ms absolute budget, and
the 1,024-event debug row exceeds the 10% relative budget. The provisional
budget is therefore not met in that run. A second paired run, preserved as
`paired-results-rerun.json`, met both provisional limits for all fixture rows;
its highest 4,096-event filtered p95 was 37.79 ms and its highest p95 ratio was
1.03x. The difference between runs makes the tail estimate unstable; a passing
rerun does not erase the exceedance. Expansion of G2 visibility coverage is
paused while the variance is investigated; no runtime visibility code has
been installed. These are local synthetic measurements, not production SLOs.
The final contract still needs real visibility classes, delay/time semantics
and unauthorized-read behavior.

Paired measurement command:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_paired.py --output docs/verification/g2-visibility-budget/paired-results.json
```

## Tail diagnostic

Two further 4,096-event debug-principal runs recorded 120 alternating pairs
after 10 warmups; raw samples are retained in `tail-diagnostic.json` and
`tail-diagnostic-no-gc.json`. With normal garbage collection, raw/filtered
wall p95 were 37.01/36.83 ms. Every measured call triggered collections.
With cyclic GC disabled for the diagnostic process, raw/filtered p95 were
30.61/31.22 ms. The normal-GC recording predates the `gc_enabled` output
field; GC was enabled for that invocation.

This comparison indicates a substantial GC contribution in these runs, but
the runs were sequential and have no controlled system-load record. It does
not establish the cause of the earlier 46.70 ms result. Process CPU samples
are quantized in approximately 15.625 ms increments in this environment and
cannot reliably separate scheduling from execution for individual reads.
Disabling GC is solely an experiment, not a production recommendation. The
earlier exceedance and the pause on expanding visibility coverage remain.

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/diagnose_tail.py --output docs/verification/g2-visibility-budget/tail-diagnostic.json
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/diagnose_tail.py --disable-gc --output docs/verification/g2-visibility-budget/tail-diagnostic-no-gc.json
```

The output is `results.json` in this directory. The source script records the
fixture, principals, policies, environment and median/p95/p99 aggregates.
The grouped run sampled raw and filtered reads separately. The paired runs
alternate order but remain sensitive to scheduling noise; repeat against the
real implementation and production-shaped workload before making a production
budget decision.
