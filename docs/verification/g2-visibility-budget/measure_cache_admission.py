"""Measure cache admission cost on an existing isolated fixture database."""
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
from measure_visibility_baseline import PRINCIPALS, provisional_read_as
from app.gameplay.event_store import DurableGameplayEventStore


def timed(call):
    start = time.perf_counter_ns()
    result = call()
    return (time.perf_counter_ns() - start) / 1_000_000, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=60)
    args = parser.parse_args()
    if args.repeats < 1 or not args.database.is_file():
        parser.error("existing fixture database and positive repeats required")
    ordinary = DurableGameplayEventStore(args.database)
    uncached = DurableGameplayEventStore(args.database)
    # Instance-only experiment: no cache insertions, but existing decode,
    # validation, SQL and result-isolation paths are left in place.
    uncached._remember_json_text = lambda body, text: None
    try:
        reference = ordinary.read_events()
        assert [e.model_dump() for e in reference] == [e.model_dump() for e in uncached.read_events()]
        samples = []
        for principal in PRINCIPALS:
            expected = provisional_read_as(reference, principal)
            def read(store):
                events = store.read_events()
                return len(events), provisional_read_as(events, principal)
            for _ in range(5):
                assert read(ordinary) == read(uncached) == (len(reference), expected)
            normal, skip = [], []
            for index in range(args.repeats):
                operations = ((ordinary, normal), (uncached, skip))
                if index % 2:
                    operations = operations[::-1]
                for store, sample in operations:
                    elapsed, result = timed(lambda: read(store))
                    assert result == (len(reference), expected)
                    sample.append(elapsed)
            samples.append({"principal": principal, "visible_count": expected,
                "normal_samples_ms": normal, "skip_samples_ms": skip,
                "normal_ms": percentiles(normal), "skip_ms": percentiles(skip)})
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"measurement": "cache-admission-diagnostic-not-authorization",
            "fixture_database": str(args.database.resolve()), "event_count": len(reference),
            "python": sys.version, "platform": platform.platform(),
            "gc_thresholds": gc.get_threshold(), "repeats": args.repeats,
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "rows": samples}, indent=2) + "\n", encoding="utf-8")
    finally:
        ordinary.close()
        uncached.close()


if __name__ == "__main__":
    main()
