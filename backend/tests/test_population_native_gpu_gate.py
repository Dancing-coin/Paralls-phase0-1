from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _load_gate():
    path = Path(__file__).parents[2] / "scripts" / "verification" / "verify_population_native_gpu_gate.py"
    spec = importlib.util.spec_from_file_location("population_native_gpu_gate", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _complete_scale_report(gate) -> dict[str, object]:
    scale = gate.sys.modules[gate.scenario_passed.__module__]
    profiles = {}
    for name, profile in scale.PRESSURE_PROFILES.items():
        scenarios = []
        for population in scale.POPULATION_SIZES:
            scenario = scale.empty_scenario(
                population=population,
                window_count=scale.WINDOW_COUNT,
                wall_budget_seconds=profile["wall_budget_seconds"],
            )
            scenario.update(
                status="completed",
                windows_completed=scale.WINDOW_COUNT,
                p95_wall_ms=profile["wall_budget_seconds"] * 100,
                backlog_non_growing=True,
                max_lag_windows=0,
                persistent_gameplay_verified=True,
                recovery_verified=True,
                serial_parallel_equivalent=True,
                character_registration_verified=True,
                full_profile_loaded=False,
                b0_cursor_verified=True,
                window_evidence_verified=True,
                pipeline_verified=True,
                authority_graph_verified=True,
                behavior_turn_verified=True,
                owner_scenario_verified=True,
            )
            scenario["passed"] = scale.scenario_passed(scenario)
            scenarios.append(scenario)
        profiles[name] = {
            **profile,
            "scenarios": scenarios,
            "ran_complete": True,
            "passed": True,
        }
    return {
        "measurement_schema_version": 1,
        "stage": 5,
        "git_head": gate._git_head(),
        "implementation_digest": gate.implementation_digest(gate.ROOT),
        "provider_mode": "disabled_default",
        "profiles": profiles,
        "cpu_kernel_share": 0.1,
        "all_required_evidence": True,
    }


def test_native_gpu_gate_keeps_python_when_end_to_end_admission_evidence_is_missing() -> None:
    gate = _load_gate()
    scale_report = {
        "profiles": {
            "one_x": {"ran_complete": True, "passed": False},
            "ten_x": {"ran_complete": True, "passed": False},
        },
        "cpu_kernel_share": 0.42,
        "protocol_persistence_share": 0.58,
        "all_required_evidence": False,
    }

    report = gate.build_report(scale_report=scale_report)

    assert report["decision"] == "continue_python"
    assert report["one_x_thirty_window_evidence"] is True
    assert report["ten_x_pressure_evidence"] is True
    assert report["native_gpu_admission_passed"] is False
    assert report["optimization_target"] == "protocol_or_persistence"


def test_native_gpu_gate_cannot_treat_none_as_positive_evidence() -> None:
    gate = _load_gate()
    report = gate.build_report(
        scale_report={
            "profiles": {
                "one_x": {"ran_complete": True, "passed": False},
                "ten_x": {"ran_complete": True, "passed": False},
            },
            "cpu_kernel_share": None,
            "protocol_persistence_share": None,
            "all_required_evidence": None,
        }
    )

    assert report["native_gpu_admission_passed"] is False
    assert report["decision"] == "continue_python"


def test_native_gpu_gate_keeps_python_when_one_x_passes() -> None:
    gate = _load_gate()
    report = gate.build_report(
        scale_report={
            "profiles": {
                "one_x": {"ran_complete": True, "passed": True},
                "ten_x": {"ran_complete": True, "passed": False},
            },
            "cpu_kernel_share": 0.75,
            "protocol_persistence_share": 0.25,
            "all_required_evidence": True,
        }
    )

    assert report["native_gpu_admission_passed"] is False
    assert report["decision"] == "continue_python"
    assert report["optimization_target"] == "none_required"
    assert report["scale_performance_gate_passed"] is True
    assert report["ten_x_performance_passed"] is False
    assert report["overall_passed"] is True


def test_native_gpu_gate_allows_adapter_only_after_one_x_kernel_failure() -> None:
    gate = _load_gate()
    report = gate.build_report(
        scale_report={
            "profiles": {
                "one_x": {"ran_complete": True, "passed": False},
                "ten_x": {"ran_complete": True, "passed": False},
            },
            "cpu_kernel_share": 0.60,
            "protocol_persistence_share": 0.40,
            "all_required_evidence": True,
        }
    )

    assert report["native_gpu_admission_passed"] is True
    assert report["decision"] == "native_cpu_adapter_allowed"
    assert report["overall_passed"] is False


def test_scale_report_loader_accepts_different_git_head_for_identical_sources(tmp_path) -> None:
    gate = _load_gate()
    report = _complete_scale_report(gate)
    report["git_head"] = "stale"
    path = tmp_path / "scale.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    assert gate.load_scale_report(path)["git_head"] == "stale"


def test_scale_report_loader_rejects_stale_implementation_digest(tmp_path) -> None:
    gate = _load_gate()
    report = _complete_scale_report(gate)
    report["implementation_digest"] = "sha256:stale"
    path = tmp_path / "scale.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ValueError, match="population_scale_report_implementation_stale"):
        gate.load_scale_report(path)
