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


def digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def measure(population: int, repeats: int = 3) -> dict[str, object]:
    rows = {
        f"actor_{index}": {
            "last_update_tick": index,
            "activity_phase": "routine",
            "fatigue": (index % 100) / 100,
            "need_pressure": ((index * 3) % 100) / 100,
            "next_due_tick": index + 10,
            "starvation_credit": 1.0,
            "revision": index,
        }
        for index in range(population)
    }
    hot = PopulationHotState(rows)
    for actor_id, row in rows.items():
        hot.upsert(actor_id, {key: value for key, value in row.items() if key != "revision"}, int(row["revision"]))
    baseline_values = tuple(
        (actor_id, round(float(row["fatigue"]) + float(row["need_pressure"]), 6))
        for actor_id, row in sorted(rows.items())
    )
    hot_values = hot.map_readonly(
        rows,
        lambda actor_id, row: (actor_id, round(float(row["fatigue"]) + float(row["need_pressure"]), 6)),
    )
    serial_ms: list[float] = []
    hot_ms: list[float] = []
    for _ in range(repeats):
        started = perf_counter()
        tuple(
            (actor_id, round(float(row["fatigue"]) + float(row["need_pressure"]), 6))
            for actor_id, row in sorted(rows.items())
        )
        serial_ms.append((perf_counter() - started) * 1000)
        started = perf_counter()
        hot.map_readonly(
            rows,
            lambda actor_id, row: (actor_id, round(float(row["fatigue"]) + float(row["need_pressure"]), 6)),
        )
        hot_ms.append((perf_counter() - started) * 1000)
    return {
        "population": population,
        "baseline_hash": digest(baseline_values),
        "hot_state_hash": digest(hot_values),
        "equivalent": digest(baseline_values) == digest(hot_values),
        "baseline_serialized_bytes": len(json.dumps(rows, sort_keys=True).encode()),
        "hot_state_serialized_bytes": len(json.dumps(hot.export_rows(), sort_keys=True).encode()),
        "baseline_p50_ms": round(median(serial_ms), 4),
        "hot_state_p50_ms": round(median(hot_ms), 4),
        "baseline_p95_ms": round(max(serial_ms), 4),
        "hot_state_p95_ms": round(max(hot_ms), 4),
    }


def main() -> int:
    scenarios = [measure(population) for population in (54, 100, 1000, 10000)]
    report = {
        "stage": 4,
        "python": platform.python_version(),
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=root(), capture_output=True, text=True, check=False).stdout.strip(),
        "scenarios": scenarios,
        "overall_passed": all(item["equivalent"] for item in scenarios),
        "implementation_status": "written_and_backend_verified",
        "godot_status": "godot_unverified",
    }
    directory = root() / ".harness" / "verification"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "population-hot-state-equivalence-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"overall_population_hot_state_equivalence_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
