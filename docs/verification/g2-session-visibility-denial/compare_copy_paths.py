"""Isolated copy-cost diagnostic; never installs a runtime authorization path."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "docs/verification/g2-visibility-budget"))

from measure_visibility_baseline import build_store
from measure_paired import percentiles
from app.gameplay import event_store
from app.gameplay.economy_privacy_views import EconomyPrivacyQueryService, EconomyPrivacyViewError
from app.gameplay.economy_runtime import EconomyAuthorityService


def deep_copy(event):
    return event.model_copy(deep=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output must be new")

    original_copy = event_store._copy_event_for_read
    store = build_store(4095)
    opened = EconomyAuthorityService(store=store).open_account(
        command_id="cmd:benchmark", account_id="account:benchmark", owner_ref="actor:owner",
        currency_ref="coin", initial_balance=20, idempotency_key="benchmark",
        causation_id="benchmark", correlation_id="benchmark",
    )
    assert opened.committed and len(store.read_events()) == 4096
    query = EconomyPrivacyQueryService(store=store, authority_principals={"authority:economy"})

    def fixture_digest():
        body = [event.model_dump(mode="json") for event in store.read_events()]
        return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()

    rows = []
    try:
        current_digest = fixture_digest()
        event_store._copy_event_for_read = deep_copy
        assert fixture_digest() == current_digest
        for principal in ("actor:owner", "authority:economy", "actor:other"):
            def view():
                try:
                    result = query.account_redacted_payload(
                        account_id="account:benchmark", principal_ref=principal,
                    )
                except EconomyPrivacyViewError as exc:
                    assert principal == "actor:other" and str(exc) == "economy_account_visibility_denied"
                    return {"denied": str(exc)}
                assert principal != "actor:other" and result["balance"] == 20
                assert ("owner_ref" in result) == (principal == "authority:economy")
                return result

            event_store._copy_event_for_read = deep_copy
            expected = view()
            event_store._copy_event_for_read = original_copy
            assert view() == expected

            for _ in range(5):
                event_store._copy_event_for_read = deep_copy
                view()
                event_store._copy_event_for_read = original_copy
                view()
            samples = {"deep_copy": [], "current_copy": []}
            for index in range(60):
                order = [("deep_copy", deep_copy), ("current_copy", original_copy)]
                if index % 2:
                    order.reverse()
                for label, copy_fn in order:
                    event_store._copy_event_for_read = copy_fn
                    start = time.perf_counter_ns()
                    actual = view()
                    elapsed = (time.perf_counter_ns() - start) / 1_000_000
                    assert actual == expected
                    samples[label].append(elapsed)
            stats = {label: percentiles(values) for label, values in samples.items()}
            rows.append({
                "principal": principal, "events": 4096, "stats_ms": stats,
                "deep_to_current_median_ratio": stats["deep_copy"]["median"] / stats["current_copy"]["median"],
                "samples_ms": samples,
            })
        event_store._copy_event_for_read = original_copy
        assert fixture_digest() == current_digest
    finally:
        event_store._copy_event_for_read = original_copy

    source_paths = [
        Path(__file__), REPO / "backend/app/gameplay/event_store.py",
        REPO / "backend/app/gameplay/economy_privacy_views.py",
        REPO / "backend/app/gameplay/economy_runtime.py",
        REPO / "docs/verification/g2-visibility-budget/measure_visibility_baseline.py",
        REPO / "docs/verification/g2-visibility-budget/measure_economy_principals.py",
    ]
    result = {
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "python": sys.version, "executable": sys.executable, "platform": platform.platform(),
        "gc_enabled": gc.isenabled(), "gc_thresholds": gc.get_threshold(),
        "warmups": 5, "paired_samples": 60, "ordering": "alternating copy paths per principal",
        "fixture_sha256": current_digest, "equivalent_events_and_view_results": True,
        "source_sha256": {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},
        "scope": "Same current code and scalar fixture, replacing only read-copy helper with the former deep-copy expression inside this isolated process. Not a historical-version rerun, session authorization benchmark or production SLO.",
        "rows": rows,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for row in rows:
        print(row["principal"], json.dumps(row["stats_ms"]), "median_ratio", round(row["deep_to_current_median_ratio"], 3))


if __name__ == "__main__":
    main()
