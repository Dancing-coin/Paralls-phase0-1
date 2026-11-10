"""Measure existing durable reads and a fixture-only principal scan."""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import platform
import sys
import tempfile
import time
from pathlib import Path

from measure_paired import percentiles
from measure_visibility_baseline import PRINCIPALS, build_store, provisional_read_as
from app.gameplay.event_store import DurableGameplayEventStore


def timed(call):
    started = time.perf_counter_ns()
    value = call()
    elapsed = (time.perf_counter_ns() - started) / 1_000_000
    return elapsed, value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=60)
    parser.add_argument("--warmups", type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 1 or args.warmups < 1:
        parser.error("repeats and warmups must be positive")

    directory = Path(tempfile.mkdtemp(prefix="paralls-g2-durable-visibility-"))
    rows = []
    for count in (256, 1024, 4096):
        source = build_store(count)
        path = directory / f"events-{count}.db"
        store = DurableGameplayEventStore(path)
        for batch in source.read_transactions():
            assert store.append_batch(batch).committed
        store.close()
        store = DurableGameplayEventStore(path)
        try:
            reference = store.read_events()
            assert [e.model_dump() for e in reference] == [e.model_dump() for e in source.read_events()]
            for principal in PRINCIPALS:
                expected = provisional_read_as(reference, principal)
                def filtered():
                    return provisional_read_as(store.read_events(), principal)
                for _ in range(args.warmups):
                    store.read_events()
                    assert filtered() == expected
                raw, scanned = [], []
                for i in range(args.repeats):
                    if i % 2:
                        scan_ms, actual = timed(filtered)
                        raw_ms, events = timed(store.read_events)
                    else:
                        raw_ms, events = timed(store.read_events)
                        scan_ms, actual = timed(filtered)
                    assert len(events) == count and actual == expected
                    raw.append(raw_ms)
                    scanned.append(scan_ms)
                rows.append({"event_count": count, "principal": principal,
                    "visible_count": expected, "raw_samples_ms": raw,
                    "scanned_samples_ms": scanned, "raw_ms": percentiles(raw),
                    "scanned_ms": percentiles(scanned),
                    "p95_ratio": percentiles(scanned)["p95"] / percentiles(raw)["p95"]})
        finally:
            store.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        "measurement": "durable-read-fixture-scan-not-authorization",
        "python": sys.version, "platform": platform.platform(),
        "gc_thresholds": gc.get_threshold(), "repeats": args.repeats,
        "warmups": args.warmups, "ordering": "alternating_raw_and_scanned",
        "fixture_directory": str(directory),
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "rows": rows,
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
