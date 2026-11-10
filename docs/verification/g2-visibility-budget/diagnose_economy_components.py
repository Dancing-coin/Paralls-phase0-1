"""Decompose an existing principal view on a synthetic in-memory fixture."""
import argparse
import gc
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

from measure_visibility_baseline import build_store
from measure_paired import percentiles
from app.gameplay.economy_privacy_views import EconomyPrivacyQueryService
from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyProjector


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=120)
    parser.add_argument("--warmups", type=int, default=10)
    args = parser.parse_args()
    if args.output.exists() or args.repeats < 1 or args.warmups < 1:
        parser.error("output must be new and counts positive")
    store = build_store(4095)
    result = EconomyAuthorityService(store=store).open_account(
        command_id="cmd:benchmark", account_id="account:benchmark", owner_ref="actor:owner",
        currency_ref="coin", initial_balance=20, idempotency_key="benchmark",
        causation_id="benchmark", correlation_id="benchmark")
    assert result.committed
    events = store.read_events()
    assert len(events) == 4096
    projector = EconomyProjector()
    query = EconomyPrivacyQueryService(store=store, authority_principals={"authority:economy"})
    def read():
        assert len(store.read_events()) == 4096
    def project():
        assert projector.rebuild(events).accounts["account:benchmark"].balance == 20
    def view():
        assert query.account_redacted_payload(account_id="account:benchmark", principal_ref="actor:owner")["balance"] == 20
    calls = {"read": read, "project": project, "view": view}
    samples = {key: [] for key in calls}
    for _ in range(args.warmups):
        for call in calls.values():
            call()
    names = tuple(calls)
    for index in range(args.repeats):
        order = names[index % 3:] + names[:index % 3]
        if index % 2:
            order = order[::-1]
        for name in order:
            start = time.perf_counter_ns()
            calls[name]()
            samples[name].append((time.perf_counter_ns() - start) / 1_000_000)
    args.output.write_text(json.dumps({"python": sys.version, "platform": platform.platform(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "gc_thresholds": gc.get_threshold(), "repeats": args.repeats, "warmups": args.warmups,
        "fixture_events": len(events), "ordering": "rotated and reversed", "samples_ms": samples,
        "summary_ms": {name: percentiles(values) for name, values in samples.items()}}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
