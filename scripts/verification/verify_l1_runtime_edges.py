from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from common import (
    ensure_backend,
    read_text,
    repo_root,
    resolve_godot_exe,
    resolve_python_exe,
    run_command,
    stop_backend,
    verification_dir,
    write_json,
    write_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    godot_exe = resolve_godot_exe(args.godot_exe)
    python_exe = resolve_python_exe(args.python_exe)

    backend_process = None
    try:
        health, backend_process = ensure_backend(project_root, python_exe)

        probe_log = log_dir / "l1-runtime-probe.log"
        probe_result = run_command(
            [
                str(godot_exe),
                "--path",
                str(project_root),
                "--scene",
                "res://scenes/phase0/L1RuntimeProbe.tscn",
                "--quit-after",
                "600",
                "--verbose",
                "--render-thread",
                "safe",
            ],
            project_root,
            probe_log,
        )
        probe_text = read_text(probe_log)

        disconnect_ok = "l1_runtime_probe:disconnect_count=1" in probe_text
        reseed_ok = "l1_runtime_probe:zone_entry_count=2" in probe_text
        environment_cycle_ok = "l1_runtime_probe:environment_alert_count=2" in probe_text

        report = {
            "results": [
                {
                    "id": "disconnect_signal_observed",
                    "title": "Backend disconnect signal is observed in Godot runtime",
                    "status": "proved" if disconnect_ok else "missing",
                    "evidence": ["l1_runtime_probe:disconnect_count=1"] if disconnect_ok else [],
                    "notes": "",
                },
                {
                    "id": "zone_reseed_observed",
                    "title": "L1 zone bootstrap re-emits after reconnect in the same runtime session",
                    "status": "proved" if reseed_ok else "missing",
                    "evidence": ["l1_runtime_probe:zone_entry_count=2"] if reseed_ok else [],
                    "notes": "",
                },
                {
                    "id": "environment_cycle_observed",
                    "title": "Environment light-drop fact re-emits across alerted/stable/alerted cycle",
                    "status": "proved" if environment_cycle_ok else "missing",
                    "evidence": ["l1_runtime_probe:environment_alert_count=2"] if environment_cycle_ok else [],
                    "notes": "",
                },
            ],
            "overall_l1_runtime_edges_passed": (
                probe_result.returncode == 0 and disconnect_ok and reseed_ok and environment_cycle_ok
            ),
            "backend_health": health,
            "artifacts": {
                "probe_log": str(probe_log),
            },
        }

        json_path = log_dir / "l1-runtime-edges-report.json"
        md_path = log_dir / "l1-runtime-edges-report.md"
        write_json(json_path, report)
        write_markdown(md_path, "L1 Runtime Edge Verification Report", report, "overall_l1_runtime_edges_passed")

        print(f"l1_runtime_edges_report_json={json_path}")
        print(f"l1_runtime_edges_report_md={md_path}")
        print(f"overall_l1_runtime_edges_passed={report['overall_l1_runtime_edges_passed']}")
        for entry in report["results"]:
            print(f"{entry['id']}={entry['status']}")
        return 0 if report["overall_l1_runtime_edges_passed"] else 1
    finally:
        stop_backend(backend_process)


if __name__ == "__main__":
    raise SystemExit(main())
