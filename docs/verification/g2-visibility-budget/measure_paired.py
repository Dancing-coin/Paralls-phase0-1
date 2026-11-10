"""Repeat the provisional visibility baseline with alternating paired reads."""

from __future__ import annotations

import argparse
import gc
import json
import math
import platform
import statistics
import sys
import time
from pathlib import Path

from measure_visibility_baseline import PRINCIPALS, build_store, provisional_read_as


def percentiles(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    return {
        "median": statistics.median(ordered),
        "p95": ordered[math.ceil(len(ordered) * 0.95) - 1],
        "p99": ordered[math.ceil(len(ordered) * 0.99) - 1],
    }


def timed(call) -> float:
    start = time.perf_counter_ns()
    call()
    return (time.perf_counter_ns() - start) / 1_000_000


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=60)
    parser.add_argument("--warmups", type=int, default=5)
    parser.add_argument("--gc-threshold0", type=int)
    args = parser.parse_args()
    if args.repeats <= 0 or args.warmups <= 0:
        parser.error("repeats and warmups must be positive")
    if args.gc_threshold0 is not None:
        if args.gc_threshold0 <= 0:
            parser.error("gc-threshold0 must be positive")
        _, generation_one, generation_two = gc.get_threshold()
        gc.set_threshold(args.gc_threshold0, generation_one, generation_two)

    rows = []
    for count in (256, 1024, 4096):
        store = build_store(count)
        for principal in PRINCIPALS:
            def filtered():
                return provisional_read_as(store.read_events(), principal)

            for _ in range(args.warmups):
                store.read_events()
                filtered()
            raw_samples, filtered_samples = [], []
            for iteration in range(args.repeats):
                if iteration % 2:
                    filtered_ms, raw_ms = timed(filtered), timed(store.read_events)
                else:
                    raw_ms, filtered_ms = timed(store.read_events), timed(filtered)
                raw_samples.append(raw_ms)
                filtered_samples.append(filtered_ms)
            rows.append({
                "event_count": count,
                "principal": principal,
                "raw_ms": percentiles(raw_samples),
                "filtered_ms": percentiles(filtered_samples),
                "paired_difference_ms": percentiles([
                    filtered - raw for raw, filtered in zip(raw_samples, filtered_samples)
                ]),
                "p95_ratio": percentiles(filtered_samples)["p95"] / percentiles(raw_samples)["p95"],
            })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        "measurement": "g2-visibility-paired-synthetic-baseline",
        "contract_status": "provisional_fixture_not_production_enforcement",
        "python": sys.version,
        "platform": platform.platform(),
        "repeat_count": args.repeats,
        "warmup_count": args.warmups,
        "ordering": "alternating_raw_first_and_filtered_first",
        "gc_thresholds": gc.get_threshold(),
        "rows": rows,
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
