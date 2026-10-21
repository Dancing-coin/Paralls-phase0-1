from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile

from common import artifact_ref, evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    test_path = root / "backend" / "tests" / "test_population_conflict_cadence.py"
    cases = {
        "legacy_cadence_compatibility": "test_confirmed_cadences_admit_distinct_actors_with_real_budget_and_zero_replay_writes",
        "child_failure_recovery": "test_child_prefix_failure_does_not_stop_b0_and_next_cadence_only_admits_remaining",
        "unconfirmed_source_rejection": "test_unconfirmed_public_and_later_source_change_cannot_admit_children",
        "durable_reopen": "test_dual_database_reopen_keeps_original_child_ttl_and_admits_only_unhandled_source",
        "character_temporal_grant": "test_driver_pinned_cadence_issues_character_temporal_grant",
        "changed_grant_rejection": "test_driver_pinned_cadence_rejects_changed_character_grant",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    python = resolve_python_exe(None)
    for check, test_name in cases.items():
        log = Path(tempfile.gettempdir()) / f"paralls-character-temporal-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log)
        checks[check] = result.returncode == 0 and bool(result.stdout.strip())
        log.unlink(missing_ok=True)
    command_log = verification_dir(root) / "command.log"
    if command_log.is_file():
        evidence.append(artifact_ref(root, command_log).replace("\\", "/"))
    report = {
        "profile": "infra-character-temporal-consumer",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [artifact_ref(root, test_path).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-character-temporal-consumer-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "PopulationConflictPump -> Character cognition admission",
        "temporal_source": "PopulationCadenceDriver time_pins.temporal_authorizations.character",
        "scope": "wake admission only; cognition writeback and world facts remain separately owned",
        "operational_deadline": "admission TTL uses wall-clock recovery only; it does not alter world cutoff",
        "limitations": [
            "Direct legacy publisher fixtures omit the grant carrier for compatibility.",
            "No canonical LifeState, Presence, Soul, or character world deadline is inferred.",
        ],
    }
    path = verification_dir(root) / "infra-character-temporal-consumer-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "Character Temporal Consumer Report",
                   {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
                   "overall_passed")
    print(f"infra_character_temporal_consumer_report_json={path}")
    print(f"overall_infra_character_temporal_consumer_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    from run_context import run_scope

    with run_scope(Path(__file__).resolve().parents[2]):
        raise SystemExit(main())
