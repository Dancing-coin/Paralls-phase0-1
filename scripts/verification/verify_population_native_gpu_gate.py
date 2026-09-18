from __future__ import annotations

try:
    from .common import verification_dir
except ImportError:
    from common import verification_dir

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.verification.population_benchmark_metrics import implementation_digest
from scripts.verification.verify_population_runtime_scale import (
    POPULATION_SIZES,
    PRESSURE_PROFILES,
    WINDOW_COUNT,
    build_report as build_scale_report,
    scenario_evidence_complete,
    scenario_passed,
)


def _git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout.strip()


def load_scale_report(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("measurement_schema_version") != 1 or report.get("stage") != 5:
        raise ValueError("population_scale_report_schema_invalid")
    if report.get("implementation_digest") != implementation_digest(ROOT):
        raise ValueError("population_scale_report_implementation_stale")
    if report.get("provider_mode") != "disabled_default":
        raise ValueError("population_scale_report_provider_mode_invalid")
    profiles = report.get("profiles")
    if not isinstance(profiles, dict) or set(profiles) != set(PRESSURE_PROFILES):
        raise ValueError("population_scale_report_matrix_incomplete")
    all_scenarios: list[dict[str, Any]] = []
    for profile_name, expected in PRESSURE_PROFILES.items():
        profile = profiles[profile_name]
        if profile.get("wall_budget_seconds") != expected["wall_budget_seconds"]:
            raise ValueError("population_scale_report_budget_invalid")
        scenarios = profile.get("scenarios")
        if not isinstance(scenarios, list) or [item.get("population") for item in scenarios] != list(POPULATION_SIZES):
            raise ValueError("population_scale_report_matrix_incomplete")
        if any(
            item.get("window_count") != WINDOW_COUNT
            or item.get("windows_completed") != WINDOW_COUNT
            or item.get("wall_budget_seconds") != expected["wall_budget_seconds"]
            for item in scenarios
        ):
            raise ValueError("population_scale_report_window_invalid")
        recomputed_complete = all(scenario_evidence_complete(item) for item in scenarios)
        recomputed_passed = all(scenario_passed(item) for item in scenarios)
        if profile.get("ran_complete") is not recomputed_complete or profile.get("passed") is not recomputed_passed:
            raise ValueError("population_scale_report_result_inconsistent")
        all_scenarios.extend(scenarios)
    if report.get("all_required_evidence") is not all(
        scenario_evidence_complete(item) for item in all_scenarios
    ):
        raise ValueError("population_scale_report_evidence_inconsistent")
    if not isinstance(report.get("cpu_kernel_share"), (int, float)):
        raise ValueError("population_scale_report_kernel_share_missing")
    return report


def build_report(*, scale_report: dict[str, Any] | None = None) -> dict[str, Any]:
    scale = build_scale_report() if scale_report is None else scale_report
    profiles = scale.get("profiles") or {}
    one_x = profiles.get("one_x") or {}
    ten_x = profiles.get("ten_x") or {}
    one_x_evidence = one_x.get("ran_complete") is True
    ten_x_evidence = ten_x.get("ran_complete") is True
    one_x_passed = one_x.get("passed") is True
    ten_x_passed = ten_x.get("passed") is True
    all_evidence = scale.get("all_required_evidence") is True
    kernel_share = scale.get("cpu_kernel_share")
    kernel_dominates = isinstance(kernel_share, (int, float)) and kernel_share >= 0.60
    admission = (
        all_evidence
        and one_x_evidence
        and ten_x_evidence
        and not one_x_passed
        and kernel_dominates
    )

    if admission:
        decision = "native_cpu_adapter_allowed"
        target = "pure_population_kernel"
        reason = "1x/10x真实30窗口证据完整且纯积分CPU占比达到60%，允许评估可回退原生CPU适配器"
    elif one_x_evidence and one_x_passed:
        decision = "continue_python"
        target = "none_required"
        reason = "1x真实30窗口门槛已通过，继续使用Python运行时"
    elif one_x_evidence and isinstance(kernel_share, (int, float)) and kernel_share < 0.60:
        decision = "continue_python"
        target = "protocol_or_persistence"
        reason = "1x门槛失败且纯积分CPU占比低于60%，应先优化协议、Owner或持久化路径"
    else:
        decision = "continue_python"
        target = "collect_missing_evidence"
        reason = "原生/GPU准入所需的真实30窗口、恢复、Owner或CPU占比证据不完整"

    return {
        "stage": 5,
        "python": platform.python_version(),
        "git_head": _git_head(),
        "implementation_digest": implementation_digest(ROOT),
        "scale_report": scale,
        "cpu_kernel_share": kernel_share,
        "protocol_persistence_share": scale.get("protocol_persistence_share"),
        "one_x_thirty_window_evidence": one_x_evidence,
        "one_x_performance_passed": one_x_passed,
        "ten_x_pressure_evidence": ten_x_evidence,
        "ten_x_performance_passed": ten_x_passed,
        "native_gpu_admission_passed": admission,
        "scale_performance_gate_passed": one_x_passed,
        "decision": decision,
        "optimization_target": target,
        "decision_reason": reason,
        "overall_passed": all_evidence and one_x_passed,
        "implementation_status": "benchmark_evidence_evaluated",
        "godot_status": "godot_unverified",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale-report", type=Path)
    args = parser.parse_args()
    scale = load_scale_report(args.scale_report) if args.scale_report else None
    report = build_report(scale_report=scale)
    report["scale_report_source"] = str(args.scale_report.resolve()) if args.scale_report else "fresh_run"
    directory = verification_dir(ROOT)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "population-native-gpu-gate-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"overall_population_native_gpu_gate_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    from pathlib import Path
    from run_context import run_scope

    with run_scope(Path(__file__).resolve().parents[2]):
        raise SystemExit(main())
