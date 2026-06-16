from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.verification_audit import evaluate_phase1_slice_audit

from common import (
    ensure_backend,
    read_text,
    repo_root,
    resolve_godot_exe,
    resolve_python_exe,
    run_command,
    scan_direct_visual_fact_bypass,
    stop_backend,
    verification_dir,
    write_json,
    write_markdown,
)
from runtime_trace import write_runtime_trace


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

        pytest_log = log_dir / "phase1-slice-pytest.log"
        run_command(
            [
                python_exe,
                "-m",
                "pytest",
                "-v",
                "tests/test_visual_fact_pipeline.py",
                "tests/test_siming_service.py",
                "tests/test_siming_event_pipeline.py",
                "tests/test_siming_llm_models.py",
                "tests/test_siming_llm_provider.py",
                "tests/test_siming_llm_policy.py",
                "tests/test_siming_llm_feasibility.py",
                "tests/test_siming_llm_runtime.py",
                "tests/test_siming_llm_boundary_static.py",
            ],
            project_root / "backend",
            pytest_log,
        )

        main_screenshot = log_dir / "phase1-slice-main.png"
        main_log = log_dir / "phase1-slice-main.log"
        run_command(
            [
                str(godot_exe),
                "--path",
                str(project_root),
                "--scene",
                "res://scenes/phase0/MainDemo.tscn",
                "--quit-after",
                "400",
                "--verbose",
                "--render-thread",
                "safe",
            ],
            project_root,
            main_log,
            env={
                "PHASE0_AUTOTEST": "1",
                "PHASE0_FOCUS_AUTOTEST": "",
                "PHASE0_AUTOTEST_SCREENSHOT": str(main_screenshot),
            },
        )

        focus_screenshot = log_dir / "phase1-slice-focus.png"
        focus_log = log_dir / "phase1-slice-focus.log"
        run_command(
            [
                str(godot_exe),
                "--path",
                str(project_root),
                "--scene",
                "res://scenes/phase0/MainDemo.tscn",
                "--quit-after",
                "400",
                "--verbose",
                "--render-thread",
                "safe",
            ],
            project_root,
            focus_log,
            env={
                "PHASE0_AUTOTEST": "",
                "PHASE0_FOCUS_AUTOTEST": "1",
                "PHASE0_AUTOTEST_SCREENSHOT": str(focus_screenshot),
            },
        )

        main_log_text = read_text(main_log)
        focus_log_text = read_text(focus_log)
        runtime_trace = log_dir / "phase1-slice-runtime-trace.ndjson"
        trace_logs = {"main": main_log_text, "focus": focus_log_text}
        write_runtime_trace(runtime_trace, trace_logs)

        report = evaluate_phase1_slice_audit(
            main_log=main_log_text,
            focus_log=focus_log_text,
            direct_send_scan=scan_direct_visual_fact_bypass(project_root),
            scene_text=read_text(project_root / "scenes" / "phase0" / "MainDemo.tscn"),
            candidate_policy_source=read_text(project_root / "backend" / "app" / "services" / "candidate_percept_service.py"),
        )
        report["backend_health"] = health
        report["artifacts"] = {
            "pytest_log": str(pytest_log),
            "main_log": str(main_log),
            "focus_log": str(focus_log),
            "main_screenshot": str(main_screenshot),
            "focus_screenshot": str(focus_screenshot),
            "runtime_trace": str(runtime_trace),
        }

        json_path = log_dir / "phase1-slice-report.json"
        md_path = log_dir / "phase1-slice-report.md"
        write_json(json_path, report)
        write_markdown(md_path, "Phase1-Shaped Slice Verification Report", report, "overall_phase1_slice_passed")

        print(f"phase1_slice_report_json={json_path}")
        print(f"phase1_slice_report_md={md_path}")
        print(f"overall_phase1_slice_passed={report['overall_phase1_slice_passed']}")
        for entry in report["results"]:
            print(f"{entry['id']}={entry['status']}")
        return 0 if report["overall_phase1_slice_passed"] else 1
    finally:
        stop_backend(backend_process)


if __name__ == "__main__":
    raise SystemExit(main())
