"""Compare synthetic in-memory filtering orders; not an authorization API."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

from measure_paired import percentiles
from measure_visibility_baseline import build_store


def allowed(event, principal: str) -> bool:
    # Fixture-only rule. Real secret/debug refusal, delay, distortion and
    # authenticated principal resolution are intentionally not modeled.
    return principal == "principal:fixture-all" or event.visibility_policy == "project" or (
        event.visibility_policy == "private"
        and event.payload["owner_principal_ref"] == principal
    )


def copy_then_filter(store, principal: str):
    return [event for event in store.read_events() if allowed(event, principal)]


def filter_then_copy(store, principal: str):
    # This reaches private implementation details for measurement only. A
    # production implementation needs its own trusted policy boundary.
    with store._lock:
        return [event.model_copy(deep=True) for event in store._events if allowed(event, principal)]


def timed(call):
    start = time.perf_counter_ns()
    result = call()
    elapsed = (time.perf_counter_ns() - start) / 1_000_000
    return elapsed, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=60)
    parser.add_argument("--warmups", type=int, default=6)
    parser.add_argument("--all-visible", action="store_true")
    args = parser.parse_args()
    if args.repeats < 1 or args.warmups < 1:
        parser.error("repeats and warmups must be positive")

    principal = "principal:fixture-all" if args.all_visible else "principal:public-observer"
    rows = []
    for count in (256, 1024, 4096):
        store = build_store(count)
        # Decouple owner from policy and stream and include nested mutable data.
        # This is a controlled synthetic fixture, not a production data sample.
        with store._lock:
            for index, event in enumerate(store._events):
                event.payload["owner_principal_ref"] = (
                    "principal:public-observer" if (index // 4) % 3 == 0 else "principal:other"
                )
                event.payload["detail"] = {"values": [index, {"revision": index % 7}]}
        reference = copy_then_filter(store, principal)
        candidate = filter_then_copy(store, principal)
        assert [item.model_dump() for item in reference] == [item.model_dump() for item in candidate]
        assert reference and candidate
        candidate[0].payload["detail"]["values"][1]["revision"] = -1
        assert filter_then_copy(store, principal)[0].payload["detail"]["values"][1]["revision"] != -1
        del reference, candidate

        calls = {
            "raw": store.read_events,
            "copy_then_filter": lambda: copy_then_filter(store, principal),
            "filter_then_copy": lambda: filter_then_copy(store, principal),
        }
        names = tuple(calls)
        for _ in range(args.warmups):
            for call in calls.values():
                call()
        samples = {name: [] for name in names}
        visible_count = None
        for iteration in range(args.repeats):
            offset = iteration % len(names)
            for name in names[offset:] + names[:offset]:
                elapsed, result = timed(calls[name])
                samples[name].append(elapsed)
                if name != "raw":
                    visible_count = len(result)
                del result
        rows.append({
            "event_count": count,
            "visible_count": visible_count,
            "samples_ms": samples,
            "summary_ms": {name: percentiles(values) for name, values in samples.items()},
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        "measurement": "synthetic-filter-order-diagnostic-not-authorization",
        "python": sys.version,
        "platform": platform.platform(),
        "gc_thresholds": gc.get_threshold(),
        "repeats": args.repeats,
        "warmups": args.warmups,
        "principal_fixture": principal,
        "ordering": "rotating_three_operations",
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "rows": rows,
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
