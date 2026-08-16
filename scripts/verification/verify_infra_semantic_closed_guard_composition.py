from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_semantic_effect_lifecycle.py"
    cases = {
        "all_composes_finite_predicates": "test_closed_guard_composes_tag_status_and_numeric_predicates_without_a_write_path",
        "all_rejects_false_term": "test_closed_guard_all_composition_rejects_when_one_finite_term_is_false",
        "any_accepts_one_true_term": "test_closed_guard_any_composition_accepts_one_finite_term",
        "malformed_or_script_guard_rejected": "test_closed_guard_rejects_unbounded_or_malformed_composition_without_mutation",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-semantic-closed-guard-composition-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-semantic-closed-guard-composition",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-semantic-closed-guard-composition-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": ["backend/app/gameplay/semantic_registry.py"],
        "write_path": "frozen SemanticSnapshot -> closed MetaRule guard evaluation -> proposal/trace only; no domain append path",
        "enabled_syntax": ["all(<finite atomic guards>)", "any(<finite atomic guards>)"],
        "limitations": ["Nested groups, arbitrary expressions, scripts, and generic effect/state owner rows remain unsupported.", "MetaRule evaluation remains proposal-only and cannot append domain truth."],
    }
    path = verification_dir(root) / "infra-semantic-closed-guard-composition-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-1C Closed Guard Composition Report", {"results": [{"id": name, "status": "proved" if status else "missing", "title": name} for name, status in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_semantic_closed_guard_composition_report_json={path}")
    print(f"overall_infra_semantic_closed_guard_composition_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
