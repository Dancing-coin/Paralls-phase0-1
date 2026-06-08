from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def _result(
    result_id: str,
    title: str,
    status: str,
    evidence: list[str],
    notes: str = "",
) -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": status,
        "evidence": evidence,
        "notes": notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)

    preflight_log = log_dir / "stage2-start-gate-preflight.log"
    backend_log = log_dir / "stage2-start-gate-backend.log"
    phase0_log = log_dir / "stage2-start-gate-phase0.log"
    phase1_log = log_dir / "stage2-start-gate-phase1.log"
    l1_edges_log = log_dir / "stage2-start-gate-l1-edges.log"

    preflight_result = run_command(
        [python_exe, "scripts/verification/verify_enhanced_merge_preflight.py"],
        project_root,
        preflight_log,
    )
    backend_result = run_command(
        [python_exe, "-m", "pytest", "-v"],
        project_root / "backend",
        backend_log,
    )
    phase0_result = run_command(
        [python_exe, "scripts/verification/verify_phase0.py"],
        project_root,
        phase0_log,
    )
    phase1_result = run_command(
        [python_exe, "scripts/verification/verify_phase1_slice.py"],
        project_root,
        phase1_log,
    )
    l1_edges_result = run_command(
        [python_exe, "scripts/verification/verify_l1_runtime_edges.py"],
        project_root,
        l1_edges_log,
    )

    preflight_ok = preflight_result.returncode == 0
    backend_ok = backend_result.returncode == 0
    phase0_ok = phase0_result.returncode == 0
    phase1_ok = phase1_result.returncode == 0
    l1_edges_ok = l1_edges_result.returncode == 0

    report = {
        "results": [
            _result(
                "enhanced_merge_preflight",
                "Enhanced merge preflight is green",
                "proved" if preflight_ok else "missing",
                ["verify_enhanced_merge_preflight.py"] if preflight_ok else [],
                "" if preflight_ok else f"Inspect {preflight_log}",
            ),
            _result(
                "backend_suite_green",
                "Full backend test suite is green",
                "proved" if backend_ok else "missing",
                ["python -m pytest -v"] if backend_ok else [],
                "" if backend_ok else f"Inspect {backend_log}",
            ),
            _result(
                "phase0_verification_green",
                "Phase 0 verification is green",
                "proved" if phase0_ok else "missing",
                ["verify_phase0.py"] if phase0_ok else [],
                "" if phase0_ok else f"Inspect {phase0_log}",
            ),
            _result(
                "phase1_slice_verification_green",
                "Phase 1 slice verification is green",
                "proved" if phase1_ok else "missing",
                ["verify_phase1_slice.py"] if phase1_ok else [],
                "" if phase1_ok else f"Inspect {phase1_log}",
            ),
            _result(
                "l1_runtime_edges_green",
                "L1 runtime edge verification is green",
                "proved" if l1_edges_ok else "missing",
                ["verify_l1_runtime_edges.py"] if l1_edges_ok else [],
                "" if l1_edges_ok else f"Inspect {l1_edges_log}",
            ),
        ],
        "overall_stage2_start_gate_passed": (
            preflight_ok and backend_ok and phase0_ok and phase1_ok and l1_edges_ok
        ),
        "artifacts": {
            "preflight_log": str(preflight_log),
            "backend_log": str(backend_log),
            "phase0_log": str(phase0_log),
            "phase1_log": str(phase1_log),
            "l1_edges_log": str(l1_edges_log),
        },
    }

    json_path = log_dir / "stage2-start-gate-report.json"
    md_path = log_dir / "stage2-start-gate-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Stage 2 Start Gate Report", report, "overall_stage2_start_gate_passed")

    print(f"stage2_start_gate_report_json={json_path}")
    print(f"stage2_start_gate_report_md={md_path}")
    print(f"overall_stage2_start_gate_passed={report['overall_stage2_start_gate_passed']}")
    for entry in report["results"]:
        print(f"{entry['id']}={entry['status']}")
    return 0 if report["overall_stage2_start_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
