"""Measure current raw reads and a provisional principal visibility scan.

This is a measurement harness only. It does not add or claim the G2 read_as
contract; the fixture policy is intentionally explicit so a later contract can
replace it without mistaking this baseline for production enforcement.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AtomicEventBatch, GameplayEvent, IdempotencyRecord


PRINCIPALS = (
    "principal:public-observer",
    "principal:town-authority",
    "principal:private-owner",
    "principal:debug-probe",
)
POLICIES = ("project", "authority_only", "private", "debug_only")


def build_store(event_count: int) -> GameplayEventStore:
    store = GameplayEventStore()
    stream_count = 4
    heads = {f"gameplay:visibility:{index}": 0 for index in range(stream_count)}
    events: list[GameplayEvent] = []
    for index in range(event_count):
        stream_id = f"gameplay:visibility:{index % stream_count}"
        policy = POLICIES[index % len(POLICIES)]
        owner = PRINCIPALS[index % len(PRINCIPALS)]
        events.append(
            GameplayEvent(
                event_id=f"event:g2-visibility:{index}",
                event_type="g2.visibility.fixture",
                schema_version=1,
                stream_id=stream_id,
                stream_revision=0,
                global_sequence=0,
                transaction_id="transaction:g2-visibility-fixture",
                command_id="command:g2-visibility-fixture",
                causation_id=f"cause:g2-visibility:{index}",
                correlation_id=f"correlation:g2-visibility:{index}",
                visibility_policy=policy,
                payload={"owner_principal_ref": owner, "fixture_index": index},
            )
        )
        heads[stream_id] += 1
    batch = AtomicEventBatch(
        transaction_id="transaction:g2-visibility-fixture",
        command_id="command:g2-visibility-fixture",
        expected_stream_revisions={stream: 0 for stream in heads},
        idempotency_record=IdempotencyRecord(
            principal_ref="principal:g2-baseline",
            idempotency_key=f"g2-visibility-fixture:{event_count}",
            payload_digest=f"sha256:g2-visibility-fixture:{event_count}",
        ),
        events=events,
        result_digest=f"sha256:g2-visibility-fixture:{event_count}",
    )
    result = store.append_batch(batch)
    if not result.committed:
        raise RuntimeError(result.failure or "visibility fixture append failed")
    return store


def provisional_read_as(events: list[GameplayEvent], principal: str) -> int:
    """Count a documented fixture policy; this is not the production contract."""
    visible = 0
    for event in events:
        policy = event.visibility_policy
        owner = event.payload.get("owner_principal_ref")
        if policy == "project":
            visible += 1
        elif policy == "authority_only" and principal in {
            "principal:town-authority",
            "principal:debug-probe",
        }:
            visible += 1
        elif policy == "private" and owner == principal:
            visible += 1
        elif policy == "debug_only" and principal == "principal:debug-probe":
            visible += 1
    return visible


def measure(callable_, *, repeats: int, warmups: int) -> tuple[float, float, float]:
    for _ in range(warmups):
        callable_()
    samples = []
    for _ in range(repeats):
        started = time.perf_counter_ns()
        callable_()
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    ordered = sorted(samples)
    p95_index = math.ceil(len(ordered) * 0.95) - 1
    p99_index = math.ceil(len(ordered) * 0.99) - 1
    return statistics.median(samples), ordered[p95_index], ordered[p99_index]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--events", type=int, nargs="+", default=[256, 1024, 4096])
    parser.add_argument("--repeats", type=int, default=30)
    parser.add_argument("--warmups", type=int, default=5)
    args = parser.parse_args()
    if any(value <= 0 for value in (*args.events, args.repeats, args.warmups)):
        raise SystemExit("events, repeats and warmups must be positive")

    rows = []
    for event_count in args.events:
        store = build_store(event_count)
        all_events = store.read_events()
        raw_median, raw_p95, raw_p99 = measure(
            store.read_events, repeats=args.repeats, warmups=args.warmups
        )
        for principal in PRINCIPALS:
            def read_as() -> int:
                return provisional_read_as(store.read_events(), principal)

            median, p95, p99 = measure(read_as, repeats=args.repeats, warmups=args.warmups)
            rows.append({
                "event_count": event_count,
                "principal": principal,
                "raw_read_events": {"median_ms": raw_median, "p95_ms": raw_p95, "p99_ms": raw_p99},
                "provisional_read_as": {
                    "median_ms": median,
                    "p95_ms": p95,
                    "p99_ms": p99,
                    "visible_count": provisional_read_as(all_events, principal),
                    "overhead_ratio_p95": p95 / raw_p95 if raw_p95 else None,
                },
            })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        "measurement": "g2-visibility-baseline",
        "contract_status": "provisional_fixture_not_production_enforcement",
        "python": sys.version,
        "platform": platform.platform(),
        "repeat_count": args.repeats,
        "warmup_count": args.warmups,
        "event_counts": args.events,
        "principals": PRINCIPALS,
        "policies": POLICIES,
        "rows": rows,
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
