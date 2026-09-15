from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.population_continuity.hot_state import PopulationHotState


def root() -> Path:
    return Path(__file__).resolve().parents[2]


def measure(population: int) -> dict[str, int | float]:
    state = PopulationHotState(f"actor_{index}" for index in range(population))
    for index in range(population):
        state.upsert(f"actor_{index}", {"last_update_tick": index, "next_due_tick": index + 10}, index)
    started = perf_counter()
    full = state.export_rows()
    full_ms = (perf_counter() - started) * 1000
    started = perf_counter()
    tail = tuple(row for _, row in full if int(row["next_due_tick"]) >= population)
    tail_ms = (perf_counter() - started) * 1000
    return {
        "population": population,
        "full_rows": len(full),
        "tail_rows": len(tail),
        "full_ms": round(full_ms, 4),
        "tail_ms": round(tail_ms, 4),
    }


def main() -> int:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "backend/tests/test_population_incremental_benchmark.py",
        "backend/tests/test_population_parallel_determinism.py",
    ]
    result = subprocess.run(command, cwd=root(), capture_output=True, text=True, check=False)
    report = {
        "overall_passed": result.returncode == 0,
        "implementation_status": "written_and_backend_verified" if result.returncode == 0 else "backend_verification_failed",
        "godot_status": "godot_unverified",
        "python": platform.python_version(),
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=root(), capture_output=True, text=True, check=False).stdout.strip(),
        "measurements": [measure(size) for size in (54, 100, 1000, 10000)],
        "test_command": command,
        "test_output": result.stdout + result.stderr,
    }
    directory = root() / ".harness" / "verification"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "population-data-oriented-incremental-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"overall_population_data_oriented_incremental_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
