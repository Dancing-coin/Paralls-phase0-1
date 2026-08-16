from __future__ import annotations

from datetime import datetime, timezone
import json

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_continuation_gate.py"
    cases = {
        "ecology_owner": "test_inf3_continuation_gate_exposes_ecology_owner",
        "ecology_stream": "test_inf3_continuation_gate_exposes_one_canonical_ecology_stream",
        "record_kinds": "test_inf3_continuation_gate_exposes_canonical_record_kinds",
        "event_family": "test_inf3_continuation_gate_exposes_canonical_event_family",
        "weather_front_internal_boundary": "test_inf3_continuation_gate_keeps_weather_front_internal_to_ecology",
        "closed_wave_fanout": "test_inf3_continuation_gate_exposes_closed_wave_fanout",
        "exact_registered_consumer_edges": "test_inf3_continuation_gate_exposes_exact_registered_consumer_edges",
        "registered_hazard_admission_identity": "test_inf3_continuation_gate_requires_registered_hazard_admission_identity",
        "inf4r_next_package": "test_inf3_continuation_gate_advances_only_to_inf4r",
        "canonical_write_path": "test_inf3_continuation_gate_exposes_canonical_write_path",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-continuation-gate-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    predecessor_reports = {
        "obligation_lifecycle": root / ".harness" / "verification" / "infra-obligation-lifecycle-report.json",
        "frost_regional_edge": root / ".harness" / "verification" / "infra-regional-ecology-report.json",
        "regional_ecology_truth": root / ".harness" / "verification" / "infra-regional-ecology-truth-report.json",
        "hazard_propagation": root / ".harness" / "verification" / "infra-hazard-propagation-report.json",
        "seasonal_construction_maintenance": root / ".harness" / "verification" / "infra-seasonal-construction-maintenance-report.json",
        "weather_front_propagation": root / ".harness" / "verification" / "infra-ecology-weather-front-propagation-report.json",
    }
    predecessor_checks: dict[str, bool] = {}
    for name, report_path in predecessor_reports.items():
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            predecessor_checks[name] = bool(
                payload.get("overall_passed") is True
                and payload.get("focused_test_files")
                and payload.get("evidence")
            )
            if name == "hazard_propagation":
                predecessor_checks["hazard_admission_identity"] = bool(
                    payload.get("checks", {}).get("forged_real_class_admission_zero_write") is True
                    and payload.get("checks", {}).get("module_api_issuance_fence") is True
                )
        except (OSError, ValueError, TypeError):
            predecessor_checks[name] = False
            if name == "hazard_propagation":
                predecessor_checks["hazard_admission_identity"] = False
    report = {
        "profile": "infra-continuation-gate",
        "overall_passed": all(checks.values()) and all(predecessor_checks.values()),
        "checks": {**checks, **{f"predecessor_{name}": value for name, value in predecessor_checks.items()}},
        "predecessor_checks": predecessor_checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-continuation-gate-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "predecessor_reports": [str(path.relative_to(root)).replace("\\", "/") for path in predecessor_reports.values()],
        "next_package": "INF-4R",
        "next_package_status": "INF-4R must consume only SocialFactAuthority.view_for; family/organization/civilization inputs remain blocked until their own packages",
        "limitations": [
            "The gate records only the eight explicitly registered canonical ecology consumer edges; bounded weather-front path, fanout and wave-fanout are internal to ecology and authorize no additional edge.",
            "It does not create a runtime, event store, bus, clock, scheduler, population owner, NPC truth store, or social truth store.",
        ],
    }
    path = verification_dir(root) / "infra-continuation-gate-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF Continuation Admission Gate Report", {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in report["checks"].items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_continuation_gate_report_json={path}")
    print(f"overall_infra_continuation_gate_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
