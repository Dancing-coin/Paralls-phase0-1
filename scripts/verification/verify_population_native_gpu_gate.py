from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from statistics import median
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.population_continuity.hot_state import PopulationHotState


def root() -> Path:
    return Path(__file__).resolve().parents[2]


def _digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _fixture(population: int) -> PopulationHotState:
    state = PopulationHotState(f"actor_{index}" for index in range(population))
    for index in range(population):
        state.upsert(
            f"actor_{index}",
            {
                "last_update_tick": index,
                "activity_phase": "routine",
                "fatigue": (index % 100) / 100,
                "need_pressure": ((index * 3) % 100) / 100,
                "next_due_tick": index + 10,
                "starvation_credit": 1.0,
            },
            index,
        )
    return state


def _evaluate(state: PopulationHotState, workers: int) -> tuple[str, float]:
    started = perf_counter()
    values = state.map_readonly(
        (f"actor_{index}" for index in range(len(state.export_rows()))),
        lambda actor_id, row: (actor_id, round(float(row["fatigue"]) + float(row["need_pressure"]), 6)),
        workers=workers,
    )
    elapsed_ms = (perf_counter() - started) * 1000
    return _digest(values), elapsed_ms


def measure(population: int, repeats: int = 5) -> dict[str, object]:
    state = _fixture(population)
    serial: list[float] = []
    parallel: list[float] = []
    serial_hash = ""
    parallel_hash = ""
    for _ in range(repeats):
        serial_hash, serial_ms = _evaluate(state, workers=1)
        parallel_hash, parallel_ms = _evaluate(state, workers=4)
        serial.append(serial_ms)
        parallel.append(parallel_ms)
    return {
        "population": population,
        "serial_p50_ms": round(median(serial), 4),
        "serial_p95_ms": round(sorted(serial)[-1], 4),
        "parallel_p50_ms": round(median(parallel), 4),
        "parallel_p95_ms": round(sorted(parallel)[-1], 4),
        "serial_hash": serial_hash,
        "parallel_hash": parallel_hash,
        "result_equivalent": serial_hash == parallel_hash,
    }


def build_report() -> dict[str, object]:
    scenarios = [measure(population) for population in (100, 1000, 10000)]
    # 只有端到端 1x/10x、30 个连续窗口和完整提交成本证据齐全后才准入原生/GPU。
    return {
        "stage": 5,
        "python": platform.python_version(),
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=root(), capture_output=True, text=True, check=False).stdout.strip(),
        "scenarios": scenarios,
        "cpu_kernel_share": None,
        "serialization_share": None,
        "owner_submission_share": None,
        "one_x_thirty_window_evidence": False,
        "ten_x_pressure_evidence": False,
        "decision": "continue_python",
        "decision_reason": "当前仅有热状态纯计算对比，缺少完整窗口与 Owner 提交成本证据，拒绝引入原生/GPU适配器",
        "implementation_status": "written_and_backend_verified",
        "godot_status": "godot_unverified",
    }


def main() -> int:
    report = build_report()
    report["overall_passed"] = all(item["result_equivalent"] for item in report["scenarios"])
    directory = root() / ".harness" / "verification"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "population-native-gpu-gate-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"overall_population_native_gpu_gate_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
