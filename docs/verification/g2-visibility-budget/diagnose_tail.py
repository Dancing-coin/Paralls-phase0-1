"""Record paired wall/CPU samples for the synthetic visibility fixture."""

from __future__ import annotations

import argparse
import gc
import json
import platform
import sys
import time
from pathlib import Path

from measure_visibility_baseline import build_store, provisional_read_as


def measure(call):
    before_gc = gc.get_stats()
    cpu = time.process_time_ns()
    wall = time.perf_counter_ns()
    call()
    wall_ns = time.perf_counter_ns() - wall
    cpu_ns = time.process_time_ns() - cpu
    after_gc = gc.get_stats()
    return {
        "wall_ms": wall_ns / 1_000_000,
        "cpu_ms": cpu_ns / 1_000_000,
        "gc_collections": [after["collections"] - before["collections"] for before, after in zip(before_gc, after_gc)],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=120)
    parser.add_argument("--disable-gc", action="store_true")
    parser.add_argument("--compare-gc", action="store_true")
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("repeats must be positive")
    if args.disable_gc and args.compare_gc:
        parser.error("choose one GC mode")
    store = build_store(4096)
    principal = "principal:debug-probe"
    if args.disable_gc:
        gc.collect()
        gc.disable()

    def filtered():
        return provisional_read_as(store.read_events(), principal)

    for _ in range(10):
        store.read_events()
        filtered()
    samples = []
    for index in range(args.repeats):
        if args.compare_gc:
            gc.collect()
            if index % 2:
                gc.disable()
            else:
                gc.enable()
        gc_enabled = gc.isenabled()
        raw_first = (index // 2 if args.compare_gc else index) % 2 == 0
        if not raw_first:
            filtered_sample, raw_sample = measure(filtered), measure(store.read_events)
        else:
            raw_sample, filtered_sample = measure(store.read_events), measure(filtered)
        samples.append({"gc_enabled": gc_enabled, "raw_first": raw_first, "raw": raw_sample, "filtered": filtered_sample})
    if args.compare_gc:
        gc.enable()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        "measurement": "g2-visibility-tail-diagnostic",
        "contract_status": "synthetic_fixture_not_production_enforcement",
        "python": sys.version,
        "platform": platform.platform(),
        "event_count": 4096,
        "principal": principal,
        "gc_enabled": gc.isenabled(),
        "compare_gc": args.compare_gc,
        "warmups": 10,
        "samples": samples,
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
