from __future__ import annotations

from datetime import datetime, timezone

from common import (
    evidence_revision,
    repo_root,
    resolve_python_exe,
    run_command,
    verification_dir,
    write_json,
    write_markdown,
)


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    c4_tests = root / "backend" / "tests" / "test_infra_ecology_consumer_admission_contract.py"
    construction_tests = root / "backend" / "tests" / "test_infra_ecology_weather_front_construction_edge.py"
    organization_tests = root / "backend" / "tests" / "test_infra_ecology_weather_front_organization_supply_edge.py"
    cases = {
        "two_owner_contract_reuse": (c4_tests, "test_c4_reuses_finite_weather_front_contract_for_two_existing_target_owners"),
        "forged_owner_stream_scope_source_zero_write": (c4_tests, "test_c4_rejects_bad_admission_inputs_without_target_write"),
        "target_revision_zero_write": (c4_tests, "test_c4_rejects_stale_target_revision_without_writes"),
        "construction_duplicate_idempotency": (construction_tests, "test_weather_front_construction_edge_exact_duplicate_replays_without_second_write"),
        "organization_privacy_zero_write": (organization_tests, "test_weather_front_organization_supply_edge_rejects_forged_privacy_and_stale_source_without_writes"),
        "construction_full_checkpoint_tail_replay": (construction_tests, "test_weather_front_construction_edge_full_and_checkpoint_tail_replay_match"),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for name, (test_path, selector) in cases.items():
        log_path = verification_dir(root) / f"infra-ecology-consumer-admission-contract-{name}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{test_path}::{selector}"], root, log_path)
        checks[name] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))

    report = {
        "profile": "infra-ecology-consumer-admission-contract",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [
            str(c4_tests.relative_to(root)).replace("\\", "/"),
            str(construction_tests.relative_to(root)).replace("\\", "/"),
            str(organization_tests.relative_to(root)).replace("\\", "/"),
        ],
        "evidence": evidence,
        "run_id": f"infra-ecology-consumer-admission-contract-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "source_owner": "EcologyHazardAuthority",
        "target_owners": [
            "actor_gameplay.construction_production_domain",
            "actor_gameplay.organization_domain",
        ],
        "write_path": "read-only ecology consumer contract check -> target owner fragment -> GameplayCommandEnvelope/SettlementPlan -> one GameplayEventStore.append_batch -> outbox/replay/scoped projection",
        "limitations": [
            "Only pre-registered weather-front consumer contracts can be checked.",
            "The adapter cannot issue admissions, select an owner, build fragments, append, or register consumer rows.",
        ],
    }
    report_path = verification_dir(root) / "infra-ecology-consumer-admission-contract-report.json"
    write_json(report_path, report)
    write_markdown(
        report_path.with_suffix(".md"),
        "INF-C4 Ecology Consumer Admission Contract Report",
        {
            "results": [
                {"id": key, "status": "proved" if value else "missing", "title": key}
                for key, value in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"infra_ecology_consumer_admission_contract_report_json={report_path}")
    print(f"overall_infra_ecology_consumer_admission_contract_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
