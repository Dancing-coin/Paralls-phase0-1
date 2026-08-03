from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from common import repo_root, resolve_python_exe, verification_dir, write_json, write_markdown


PHASE_PROFILES = [
    "embodied-interaction-contracts",
    "embodied-affordance-registry",
    "embodied-bridge-attestation",
    "embodied-action-controller",
    "embodied-authority-settlement",
    "embodied-interaction-replay",
]
PHASE_6_GATE_PROFILE = "gameplay-foundation-event-spine"
PHASE_6_SESSION_PROFILE = "embodied-interaction-session"
PHASE_7_HANDOFF_PROFILE = "embodied-handoff-authority"
PHASE_7_CARRY_PLACE_PROFILE = "embodied-grab-carry-place-authority"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    profile_results: list[dict[str, object]] = []
    profiles_to_run = [
        *PHASE_PROFILES,
        PHASE_6_GATE_PROFILE,
        PHASE_6_SESSION_PROFILE,
        PHASE_7_HANDOFF_PROFILE,
        PHASE_7_CARRY_PLACE_PROFILE,
    ]
    for profile in profiles_to_run:
        command = [
            python_exe,
            str(project_root / "scripts" / "verification" / "harness.py"),
            "--profile",
            profile,
            "--python-exe",
            python_exe,
        ]
        if args.godot_exe:
            command.extend(["--godot-exe", args.godot_exe])
        log_path = log_dir / f"embodied-interaction-foundation-all-{profile}.log"
        with log_path.open("w", encoding="utf-8") as log_handle:
            result = subprocess.run(
                command,
                cwd=str(project_root),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        profile_results.append(
            {
                "id": profile,
                "title": f"{profile} dependency profile passes",
                "status": "proved" if result.returncode == 0 else "missing",
                "evidence": [str(log_path)] if result.returncode == 0 else [],
                "notes": "" if result.returncode == 0 else f"exit_code={result.returncode}",
            }
        )
        if result.returncode != 0:
            break

    overall = len(profile_results) == len(profiles_to_run) and all(entry["status"] == "proved" for entry in profile_results)
    phase_6_gate_satisfied = any(
        entry["id"] == PHASE_6_GATE_PROFILE and entry["status"] == "proved" for entry in profile_results
    )
    phase_6_session_verified = any(
        entry["id"] == PHASE_6_SESSION_PROFILE and entry["status"] == "proved" for entry in profile_results
    )
    phase_7_handoff_verified = any(
        entry["id"] == PHASE_7_HANDOFF_PROFILE and entry["status"] == "proved" for entry in profile_results
    )
    phase_7_carry_place_verified = any(
        entry["id"] == PHASE_7_CARRY_PLACE_PROFILE and entry["status"] == "proved" for entry in profile_results
    )
    report = {
        "overall_embodied_interaction_foundation_all_passed": overall,
        "phase_profiles": PHASE_PROFILES,
        "phase_6_gate_profile": PHASE_6_GATE_PROFILE,
        "phase_6_session_profile": PHASE_6_SESSION_PROFILE,
        "phase_7_handoff_profile": PHASE_7_HANDOFF_PROFILE,
        "phase_7_carry_place_profile": PHASE_7_CARRY_PLACE_PROFILE,
        "phase_6_status": "gate_satisfied" if phase_6_gate_satisfied else "blocked_until_gameplay_event_spine_verified",
        "phase_6_interaction_session_status": "backend_websocket_and_godot_live_runtime_verified" if phase_6_session_verified else "not_verified",
        "phase_7_handoff_status": "backend_websocket_and_godot_live_runtime_verified" if phase_7_handoff_verified else "not_verified",
        "phase_7_carry_place_status": "backend_websocket_and_godot_live_runtime_verified" if phase_7_carry_place_verified else "not_verified",
        "results": profile_results,
    }
    json_path = log_dir / "embodied-interaction-foundation-all-report.json"
    md_path = log_dir / "embodied-interaction-foundation-all-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Embodied Interaction Foundation Aggregate Report", report, "overall_embodied_interaction_foundation_all_passed")
    print(f"embodied_interaction_foundation_all_report_json={json_path}")
    print(f"embodied_interaction_foundation_all_report_md={md_path}")
    print(f"overall_embodied_interaction_foundation_all_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
