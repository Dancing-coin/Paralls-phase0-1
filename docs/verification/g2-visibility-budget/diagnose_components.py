"""Capture individual synthetic read, scan and GC timing samples."""

from __future__ import annotations

import argparse
import gc
import json
import platform
import sys
import time
from pathlib import Path

from measure_visibility_baseline import build_store, provisional_read_as


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=200)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")

    store = build_store(4096)
    principal = "principal:debug-probe"
    events = store.read_events()
    active_gc: list[tuple[int, int]] = []
    collections: list[dict[str, int]] = []

    def on_gc(phase: str, info: dict[str, int]) -> None:
        if phase == "start":
            active_gc.append((info["generation"], time.perf_counter_ns()))
        elif active_gc:
            generation, start = active_gc.pop()
            collections.append({"generation": generation, "duration_ns": time.perf_counter_ns() - start})

    def measure(call) -> dict[str, object]:
        collections.clear()
        cpu_start = time.thread_time_ns()
        start = time.perf_counter_ns()
        call()
        elapsed = time.perf_counter_ns() - start
        cpu = time.thread_time_ns() - cpu_start
        return {"wall_ns": elapsed, "thread_cpu_ns": cpu, "collections": list(collections)}

    def read_and_scan() -> int:
        return provisional_read_as(store.read_events(), principal)

    for _ in range(10):
        store.read_events()
        read_and_scan()
        provisional_read_as(events, principal)

    samples = []
    gc.callbacks.append(on_gc)
    try:
        for index in range(args.repeats):
            operations = [("raw", store.read_events), ("filtered", read_and_scan)]
            if index % 2:
                operations.reverse()
            pair = {name: measure(call) for name, call in operations}
            pair["scan_only"] = measure(lambda: provisional_read_as(events, principal))
            samples.append(pair)
    finally:
        gc.callbacks.remove(on_gc)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        "measurement": "g2-visibility-component-diagnostic",
        "contract_status": "synthetic_fixture_not_production_enforcement",
        "python": sys.version,
        "platform": platform.platform(),
        "clock_info": {name: str(time.get_clock_info(name)) for name in ("perf_counter", "thread_time")},
        "event_count": 4096,
        "principal": principal,
        "warmups": 10,
        "samples": samples,
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
