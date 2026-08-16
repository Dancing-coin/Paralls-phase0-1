from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_file = root / "backend" / "tests" / "test_infra_ecology_weather_front_economy_quote_fanout.py"
    cases = {
        "two_quote_one_batch": "test_weather_front_quote_fanout_updates_two_existing_quotes_in_one_owner_batch",
        "opaque_admission_and_arity_zero_write": "test_weather_front_quote_fanout_requires_exact_opaque_two_quote_admission",
        "source_target_catalog_zero_write": "test_weather_front_quote_fanout_rejects_stale_source_missing_target_and_catalog_mismatch",
        "idempotency_and_checkpoint_tail_replay": "test_weather_front_quote_fanout_duplicate_and_canonical_pair_order_are_replayable",
        "project_source_privacy_zero_write": "test_weather_front_quote_fanout_private_source_is_zero_write",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for name, selector in cases.items():
        log = verification_dir(root) / f"infra-ecology-weather-front-economy-quote-fanout-{name}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_file), "-k", selector], root, log)
        checks[name] = result.returncode == 0
        evidence.append(str(log.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-ecology-weather-front-economy-quote-fanout",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_file.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-ecology-weather-front-economy-quote-fanout-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "write_path": "Ecology opaque pair admission -> Economy owner fragment -> GameplayCommandEnvelope/SettlementPlan -> one GameplayEventStore.append_batch -> project outbox/replay",
        "limitations": [
            "Exactly two distinct pre-existing Economy quote refs are admitted; target selection remains closed.",
            "No generic ecology consumer registry, pricing formula, account mutation, payment or scheduler is created.",
        ],
    }
    path = verification_dir(root) / "infra-ecology-weather-front-economy-quote-fanout-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-3N Weather-Front Economy Quote Fanout Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()]},
        "overall_passed",
    )
    print(f"infra_ecology_weather_front_economy_quote_fanout_report_json={path}")
    print(f"overall_infra_ecology_weather_front_economy_quote_fanout_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
