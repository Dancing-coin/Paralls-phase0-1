from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from common import (
    ensure_backend,
    ensure_godot_import,
    read_text,
    repo_root,
    resolve_godot_exe,
    resolve_python_exe,
    run_command_until_markers,
    stop_backend,
    verification_dir,
    write_json,
    write_markdown,
)

NOTICE_MARKER = "autonomous_contact:notice=true"
APPROACH_STARTED_MARKER = "autonomous_contact:approach_started=true"
ARRIVAL_FACT_MARKER = "autonomous_contact:arrival_fact=true"
GREETING_APPLIED_MARKER = "autonomous_contact:greeting_applied=true"
ALL_CHECKS_COMPLETE_MARKER = "autonomous_social_contact_probe:all_checks_complete=true"
PROBE_SCENE = "res://scenes/phase0/AutonomousSocialContactProbe.tscn"


def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-log", default="")
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    runtime_log_path = Path(args.runtime_log) if args.runtime_log else log_dir / "autonomous-social-contact.log"
    godot_exe = resolve_godot_exe(args.godot_exe)
    python_exe = resolve_python_exe(args.python_exe)

    backend_process = None
    try:
        _health, backend_process = ensure_backend(project_root, python_exe, prefer_fresh_backend=True)
        ensure_godot_import(project_root, godot_exe, "autonomous-social-contact-godot-import.log")
        run_command_until_markers(
            [
                str(godot_exe),
                "--path",
                str(project_root),
                "--scene",
                PROBE_SCENE,
                "--quit-after",
                "1200",
                "--verbose",
                "--render-thread",
                "safe",
            ],
            project_root,
            runtime_log_path,
            success_markers=[ALL_CHECKS_COMPLETE_MARKER],
            timeout_seconds=20.0,
            env={"PHASE0_DEBUG_LOGGING": "1"},
        )
    finally:
        stop_backend(backend_process)

    runtime_log_text = read_text(runtime_log_path)

    replica_source = read_text(project_root / "scripts" / "character" / "CharacterReplica.gd")
    service_source = read_text(project_root / "backend" / "app" / "services" / "character_service.py")
    dialogue_source = read_text(project_root / "backend" / "app" / "services" / "dialogue_service.py")

    runtime_note = "" if runtime_log_text != "" else "Runtime probe did not produce a log."

    results = [
        _result(
            "autonomous_contact_static_wiring",
            "Autonomous contact markers and approach continuity are wired in actor runtime",
            all(
                token in replica_source
                for token in (
                    "autonomous_contact:notice=true",
                    "autonomous_contact:approach_started=true",
                    "autonomous_contact:arrival_fact=true",
                    "autonomous_contact:greeting_applied=true",
                    "_active_contact_target_actor_id",
                    "_update_autonomous_contact_target(",
                    "_emit_arrival_fact(_active_contact_target_actor_id, 0.0)",
                )
            ),
            ["scripts/character/CharacterReplica.gd"],
        ),
        _result(
            "autonomous_contact_notice",
            "Autonomous contact notice marker appears at runtime",
            NOTICE_MARKER in runtime_log_text,
            [str(runtime_log_path)] if NOTICE_MARKER in runtime_log_text else [],
            runtime_note,
        ),
        _result(
            "autonomous_contact_approach_started",
            "Autonomous contact approach-start marker appears at runtime",
            APPROACH_STARTED_MARKER in runtime_log_text,
            [str(runtime_log_path)] if APPROACH_STARTED_MARKER in runtime_log_text else [],
            runtime_note,
        ),
        _result(
            "autonomous_contact_arrival_fact",
            "Autonomous contact arrival fact marker appears at runtime",
            ARRIVAL_FACT_MARKER in runtime_log_text,
            [str(runtime_log_path)] if ARRIVAL_FACT_MARKER in runtime_log_text else [],
            runtime_note,
        ),
        _result(
            "autonomous_contact_greeting_applied",
            "Autonomous contact greeting marker appears at runtime",
            GREETING_APPLIED_MARKER in runtime_log_text,
            [str(runtime_log_path)] if GREETING_APPLIED_MARKER in runtime_log_text else [],
            runtime_note,
        ),
        _result(
            "autonomous_contact_utterance_owned_by_initiator",
            "Agent-initiated utterance path preserves initiator ownership",
            all(
                token in service_source
                for token in (
                    'if event.player_id == "character_agent":',
                    "actor_id=event.actor_id",
                    "target_actor_id=event.target_actor_id",
                    "self.dialogue.generate_utterance(",
                )
            )
            and 'control_mode": "agent_initiated_utterance"' in dialogue_source,
            [
                "backend/app/services/character_service.py",
                "backend/app/services/dialogue_service.py",
            ],
        ),
    ]

    overall_passed = all(str(entry["status"]) == "proved" for entry in results)
    report = {
        "results": results,
        "overall_autonomous_social_contact_passed": overall_passed,
        "artifacts": {
            "runtime_log": str(runtime_log_path),
        },
    }

    json_path = log_dir / "autonomous-social-contact-report.json"
    md_path = log_dir / "autonomous-social-contact-report.md"
    write_json(json_path, report)
    write_markdown(
        md_path,
        "Autonomous Social Contact Verification Report",
        report,
        "overall_autonomous_social_contact_passed",
    )

    print(f"autonomous_social_contact_report_json={json_path}")
    print(f"autonomous_social_contact_report_md={md_path}")
    print(f"overall_autonomous_social_contact_passed={report['overall_autonomous_social_contact_passed']}")
    for entry in results:
        print(f"{entry['id']}={entry['status']}")
    return 0 if overall_passed else 1


if __name__ == "__main__":
    exit_code = main()
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    finally:
        os._exit(exit_code)
