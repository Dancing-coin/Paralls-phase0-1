"""Measure an existing domain principal view, not the proposed G2 read_as."""
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
from app.gameplay.economy_privacy_views import EconomyPrivacyQueryService, EconomyPrivacyViewError
from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyProjector


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=60)
    parser.add_argument("--warmups", type=int, default=5)
    args = parser.parse_args()
    if args.output.exists() or args.repeats < 1 or args.warmups < 1:
        parser.error("output must be new and repeat counts positive")
    rows = []
    for count in (256, 1024, 4096):
        store = build_store(count - 1)
        opened = EconomyAuthorityService(store=store).open_account(
            command_id="cmd:benchmark", account_id="account:benchmark", owner_ref="actor:owner",
            currency_ref="coin", initial_balance=20, idempotency_key="benchmark",
            causation_id="benchmark", correlation_id="benchmark")
        assert opened.committed and len(store.read_events()) == count
        query = EconomyPrivacyQueryService(store=store, authority_principals={"authority:economy"})
        projector = EconomyProjector()
        def baseline():
            return projector.rebuild(store.read_events()).accounts["account:benchmark"]
        for principal in ("actor:owner", "authority:economy", "actor:other"):
            def filtered():
                try:
                    result = query.account_redacted_payload(account_id="account:benchmark", principal_ref=principal)
                except EconomyPrivacyViewError as exc:
                    assert principal == "actor:other" and str(exc) == "economy_account_visibility_denied"
                    return None
                assert principal != "actor:other" and result["balance"] == 20
                assert ("owner_ref" in result) == (principal == "authority:economy")
                return result
            for _ in range(args.warmups):
                baseline(); filtered()
            raw, scoped = [], []
            def timed(fn):
                start = time.perf_counter_ns()
                fn()
                return (time.perf_counter_ns() - start) / 1_000_000
            for index in range(args.repeats):
                if index % 2:
                    b, a = timed(filtered), timed(baseline)
                else:
                    a, b = timed(baseline), timed(filtered)
                raw.append(a); scoped.append(b)
            rows.append({"events": count, "principal": principal, "baseline_ms": percentiles(raw),
                         "view_ms": percentiles(scoped), "p95_ratio": percentiles(scoped)["p95"] / percentiles(raw)["p95"],
                         "baseline_samples_ms": raw, "view_samples_ms": scoped})
    args.output.write_text(json.dumps({"python": sys.version, "platform": platform.platform(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "gc_thresholds": gc.get_threshold(), "warmups": args.warmups, "repeats": args.repeats,
        "ordering": "alternating", "rows": rows}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
