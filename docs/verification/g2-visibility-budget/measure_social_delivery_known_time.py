"""Measure the committed recipient delivery projection over a fixed ledger cut."""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))

from app.gameplay.p5.social_delivery import SocialDeliveryAuthority, SocialDeliveryWindow
from app.gameplay.settlement_plan import build_atomic_event_batch
from measure_paired import percentiles
from measure_visibility_baseline import build_store


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=60)
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("repeats must be positive")

    store = build_store(4094)
    source_batch = build_atomic_event_batch(
        command_id="g2-known-time-source", principal_ref="authority:fixture",
        stream_id="gameplay:g2-known-time-source", expected_revision=0,
        event_specs=(("gameplay.social.knowledge_observed", {"fact_ref": "fact:g2-known-time"}),),
        idempotency_key="g2-known-time-source", causation_id="g2-known-time",
        correlation_id="g2-known-time",
    )
    source_batch.events[0].visibility_policy = "public"
    source_result = store.append_batch(source_batch)
    if not source_result.committed:
        raise RuntimeError("known-time benchmark source append failed")
    source = store.get_event(source_result.committed_event_ids[0])
    authority = SocialDeliveryAuthority(store=store)
    delivery = authority.record_delivery(
        delivery_ref="delivery:g2-known-time", source_stream_id=source.stream_id,
        source_revision=source.stream_revision, source_event_id=source.event_id,
        recipient_ref="character:g2-known-time-recipient",
        window=SocialDeliveryWindow(100, 200, None), world_now=150,
        command_id="g2-known-time-delivery", idempotency_key="g2-known-time-delivery",
        causation_id=source.event_id, correlation_id="g2-known-time",
    )
    if not delivery.committed:
        raise RuntimeError(delivery.error_code or "known-time benchmark delivery failed")

    raw_events = store.read_events()
    if len(raw_events) != 4096:
        raise RuntimeError(f"known-time fixture size invalid: {len(raw_events)}")
    view = authority.view_for(recipient_ref="character:g2-known-time-recipient", world_now=150)
    before_delivery = authority.view_for(recipient_ref="character:g2-known-time-recipient", world_now=149)
    if len(view.deliveries) != 1 or view.deliveries[0]["known_at_world_tick"] != 150 or before_delivery.deliveries:
        raise RuntimeError("known-time projection contract invalid")

    def timed(call) -> float:
        started = time.perf_counter_ns()
        call()
        return (time.perf_counter_ns() - started) / 1_000_000

    def read_view():
        return authority.view_for(recipient_ref="character:g2-known-time-recipient", world_now=150)

    for _ in range(5):
        store.read_events()
        read_view()
    raw_samples, view_samples = [], []
    for index in range(args.repeats):
        operations = ((store.read_events, raw_samples), (read_view, view_samples))
        if index % 2:
            operations = operations[::-1]
        for call, samples in operations:
            samples.append(timed(call))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        "measurement": "social-delivery-known-time-owner-view",
        "contract_status": "bounded-domain-projection-not-authenticated-socket-egress",
        "python": sys.version,
        "platform": platform.platform(),
        "event_count": len(raw_events),
        "recipient": "character:g2-known-time-recipient",
        "repeat_count": args.repeats,
        "warmup_count": 5,
        "ordering": "alternating_raw_first_and_view_first",
        "raw_samples_ms": raw_samples,
        "view_samples_ms": view_samples,
        "raw_ms": percentiles(raw_samples),
        "view_ms": percentiles(view_samples),
        "p95_ratio": percentiles(view_samples)["p95"] / percentiles(raw_samples)["p95"],
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
