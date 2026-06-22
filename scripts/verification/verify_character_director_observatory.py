from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import (
    ensure_godot_import,
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
        health, backend_process = ensure_backend(project_root, python_exe, prefer_fresh_backend=True)
        ensure_godot_import(project_root, godot_exe, "character-director-observatory-godot-import.log")
        main_log = log_dir / "character-director-observatory-main.log"
        main_screenshot = log_dir / "character-director-observatory-main.png"
        result = run_command(
            [
                str(godot_exe),
                "--path",
                str(project_root),
                "--scene",
                "res://scenes/phase0/CharacterDirectorObservatoryProbe.tscn",
                "--quit-after",
                "900",
                "--verbose",
                "--render-thread",
                "safe",
            ],
            project_root,
            main_log,
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
    raise SystemExit(main())
