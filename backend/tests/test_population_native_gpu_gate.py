from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_gate():
    path = Path(__file__).parents[2] / "scripts" / "verification" / "verify_population_native_gpu_gate.py"
    spec = importlib.util.spec_from_file_location("population_native_gpu_gate", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_native_gpu_gate_keeps_python_when_end_to_end_admission_evidence_is_missing() -> None:
    report = _load_gate().build_report()

    assert report["decision"] == "continue_python"
    assert report["one_x_thirty_window_evidence"] is False
    assert report["ten_x_pressure_evidence"] is False
    assert all(item["result_equivalent"] for item in report["scenarios"])
