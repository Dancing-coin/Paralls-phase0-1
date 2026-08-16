from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    adoption = root / "backend" / "tests" / "test_infra_ecology_c4_economy_survival_adoption.py"
    economy = root / "backend" / "tests" / "test_infra_ecology_weather_front_economy_quote_edge.py"
    cold = root / "backend" / "tests" / "test_infra_weather_front_survival_cold.py"
    cases = {
        "economy_quote_c4_admission": (adoption, "test_c4_adoption_economy_quote_invokes_closed_check"),
        "economy_quote_fanout_c4_admission": (adoption, "test_c4_adoption_economy_quote_fanout_invokes_closed_check"),
        "survival_cold_c4_admission": (adoption, "test_c4_adoption_survival_cold_invokes_closed_check"),
        "survival_heat_c4_admission": (adoption, "test_c4_adoption_survival_heat_invokes_closed_check"),
        "economy_c4_rejection_zero_write": (adoption, "test_c4_adoption_economy_rejection_is_zero_write"),
        "survival_c4_rejection_zero_write": (adoption, "test_c4_adoption_survival_rejection_is_zero_write"),
        "economy_duplicate_idempotency": (economy, "test_weather_quote_duplicate_is_idempotent_and_replayable"),
        "economy_source_revision_zero_write": (economy, "test_weather_front_quote_stale_ecology_head_is_zero_write"),
        "economy_privacy_zero_write": (economy, "test_authority_only_weather_front_cannot_admit_a_project_quote_update"),
        "economy_full_checkpoint_tail_replay": (adoption, "test_c4_adoption_economy_full_and_checkpoint_tail_replay_match"),
        "survival_duplicate_idempotency": (cold, "test_weather_front_cold_duplicate_is_idempotent"),
        "survival_source_revision_zero_write": (cold, "test_weather_front_cold_rejects_stale_ecology_revision_without_write"),
        "survival_privacy_zero_write": (cold, "test_weather_front_cold_rejects_private_ecology_source_without_write"),
        "survival_full_checkpoint_tail_replay": (cold, "test_weather_front_cold_full_and_checkpoint_tail_replay_match"),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for name, (test_file, selector) in cases.items():
        log = verification_dir(root) / f"infra-ecology-c4-economy-survival-adoption-{name}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_file), "-k", selector], root, log)
        checks[name] = result.returncode == 0
        evidence.append(str(log.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-ecology-c4-economy-survival-adoption",
        "canonical_package": "INF-3P (INF-3)",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(adoption.relative_to(root)).replace("\\", "/"), str(economy.relative_to(root)).replace("\\", "/"), str(cold.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-ecology-c4-economy-survival-adoption-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "write_path": "Ecology opaque evidence plus read-only C4 check -> existing Economy or Survival owner -> GameplayCommandEnvelope/SettlementPlan -> GameplayEventStore.append_batch -> scoped outbox/replay",
        "limitations": [
            "C4 remains a finite read-only admission check and cannot register consumers, choose targets, build fragments, append, or issue policy.",
            "Only the four pre-registered Economy quote / quote fanout / Survival cold / Survival heat rows are exercised.",
            "This does not admit generic consumer expansion, fanout, retry, compensation, scheduler, population truth, branch promotion, SOC, GAME, P6, or P7.",
        ],
    }
    path = verification_dir(root) / "infra-ecology-c4-economy-survival-adoption-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-3P C4 Economy and Survival Consumer Adoption Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()]}, "overall_passed")
    print(f"infra_ecology_c4_economy_survival_adoption_report_json={path}")
    print(f"overall_infra_ecology_c4_economy_survival_adoption_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
