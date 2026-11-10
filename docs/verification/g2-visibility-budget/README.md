# G2 visibility budget baseline

This directory contains the first G2 measurement only. It measures the
current `GameplayEventStore.read_events()` deep-copy cost and a provisional
principal-aware metadata scan over a deterministic fixture. The scan is not a
production `read_as` implementation and does not decide the final visibility
model.

Run from the repository root with the G0 interpreter:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' `
  docs/verification/g2-visibility-budget/measure_visibility_baseline.py `
  --output D:/Temp/paralls-g2-visibility-baseline/results.json
```

The output records median, p95 and p99 milliseconds for 256, 1024 and 4096
events across public, authority, private-owner and debug principals. It also
records the p95 ratio against the current raw read. The harness does not enforce
a threshold; the provisional implementation budget and its limitations are
recorded in [report.md](report.md).
