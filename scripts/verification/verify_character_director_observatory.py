from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from common import (
    ensure_godot_import,
    ensure_backend,
    read_text,
    repo_root,
    resolve_godot_exe,
    resolve_python_exe,
    run_command,
    run_command_until_markers,
    stop_backend,
    verification_dir,
    write_json,
    write_markdown,
)

OBSERVATORY_PROBE_QUIT_AFTER = "300"
OBSERVATORY_PROBE_MARKER_TIMEOUT_SECONDS = 120.0


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
        health, backend_process = ensure_backend(project_root, python_exe, prefer_fresh_backend=True)
        ensure_godot_import(project_root, godot_exe, "character-director-observatory-godot-import.log")
        main_log = log_dir / "character-director-observatory-main.log"
        main_screenshot = log_dir / "character-director-observatory-main.png"
        result = run_command_until_markers(
            [
                str(godot_exe),
                "--path",
                str(project_root),
                "--scene",
                "res://scenes/phase0/CharacterDirectorObservatoryProbe.tscn",
                "--quit-after",
                OBSERVATORY_PROBE_QUIT_AFTER,
                "--verbose",
                "--render-thread",
                "safe",
            ],
            project_root,
            main_log,
            success_markers=[
                "character_director_observatory_probe:state_payloads_ok=true",
                "character_director_observatory_probe:panels_populated=true",
                "character_director_observatory_probe:freeze_roundtrip_ok=true",
            ],
            timeout_seconds=OBSERVATORY_PROBE_MARKER_TIMEOUT_SECONDS,
            env={
                "PHASE0_AUTOTEST_SCREENSHOT": str(main_screenshot),
                "PHASE0_DEBUG_LOGGING": "1",
            },
        )
        log_text = read_text(main_log)
        payload = {
            "results": [
                {
                    "id": "observatory_state_payloads",
                    "title": "Observatory state center receives actor/siming/world/script payloads",
                    "status": "proved" if "character_director_observatory_probe:state_payloads_ok=true" in log_text else "missing",
                    "evidence": ["state_payloads_ok"] if "character_director_observatory_probe:state_payloads_ok=true" in log_text else [],
                    "notes": "",
                },
                {
                    "id": "observatory_panels_populated",
                    "title": "Observatory panels populate with dramatic workstation content",
                    "status": "proved" if "character_director_observatory_probe:panels_populated=true" in log_text else "missing",
                    "evidence": ["panels_populated"] if "character_director_observatory_probe:panels_populated=true" in log_text else [],
                    "notes": "",
                },
                {
                    "id": "observatory_actor_panel_populated",
                    "title": "At least one actor panel contains real dramatic inspection content",
                    "status": "proved" if "character_director_observatory_probe:actor_panel_populated=true" in log_text else "missing",
                    "evidence": ["actor_panel_populated"] if "character_director_observatory_probe:actor_panel_populated=true" in log_text else [],
                    "notes": "",
                },
                {
                    "id": "observatory_director_workstation_populated",
                    "title": "Director monitor contains cast, world, and Siming workstation detail",
                    "status": "proved" if "character_director_observatory_probe:director_cast_world_siming_populated=true" in log_text else "missing",
                    "evidence": ["director_cast_world_siming_populated"] if "character_director_observatory_probe:director_cast_world_siming_populated=true" in log_text else [],
                    "notes": "",
                },
                {
                    "id": "observatory_timeline_multi_role",
                    "title": "Script timeline contains multi-role beat content",
                    "status": "proved" if "character_director_observatory_probe:timeline_multi_role_populated=true" in log_text else "missing",
                    "evidence": ["timeline_multi_role_populated"] if "character_director_observatory_probe:timeline_multi_role_populated=true" in log_text else [],
                    "notes": "",
                },
                {
                    "id": "observatory_ledger_pairwise",
                    "title": "Dialogue ledger contains pairwise cross-role accounting content",
                    "status": "proved" if "character_director_observatory_probe:ledger_pairwise_populated=true" in log_text else "missing",
                    "evidence": ["ledger_pairwise_populated"] if "character_director_observatory_probe:ledger_pairwise_populated=true" in log_text else [],
                    "notes": "",
                },
                {
                    "id": "observatory_freeze_roundtrip",
                    "title": "Freeze mode can be entered and exited while preserving inspectable state",
                    "status": "proved" if "character_director_observatory_probe:freeze_roundtrip_ok=true" in log_text else "missing",
                    "evidence": ["freeze_roundtrip_ok"] if "character_director_observatory_probe:freeze_roundtrip_ok=true" in log_text else [],
                    "notes": "",
                },
            ],
            "overall_character_director_observatory_passed": (
                result.returncode == 0
                and "character_director_observatory_probe:state_payloads_ok=true" in log_text
                and "character_director_observatory_probe:panels_populated=true" in log_text
                and "character_director_observatory_probe:actor_panel_populated=true" in log_text
                and "character_director_observatory_probe:director_cast_world_siming_populated=true" in log_text
                and "character_director_observatory_probe:timeline_multi_role_populated=true" in log_text
                and "character_director_observatory_probe:ledger_pairwise_populated=true" in log_text
                and "character_director_observatory_probe:freeze_roundtrip_ok=true" in log_text
            ),
            "backend_health": health,
            "artifacts": {
                "main_log": str(main_log),
                "main_screenshot": str(main_screenshot),
            },
        }
        json_path = log_dir / "character-director-observatory-report.json"
        md_path = log_dir / "character-director-observatory-report.md"
        write_json(json_path, payload)
        write_markdown(
            md_path,
            "Character Director Observatory Verification Report",
            payload,
            "overall_character_director_observatory_passed",
        )
        print(f"character_director_observatory_report_json={json_path}")
        print(f"character_director_observatory_report_md={md_path}")
        print(f"overall_character_director_observatory_passed={payload['overall_character_director_observatory_passed']}")
        return 0 if payload["overall_character_director_observatory_passed"] else 1
    finally:
        stop_backend(backend_process)


if __name__ == "__main__":
    exit_code = main()
    try:
        import sys

        sys.stdout.flush()
        sys.stderr.flush()
    finally:
        os._exit(exit_code)
