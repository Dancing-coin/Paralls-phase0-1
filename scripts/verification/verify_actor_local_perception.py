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

NOTICE_MARKER = "actor_local_perception:notice_emitted=true"
FACT_ROUTED_MARKER = "actor_local_perception:fact_routed=true"
CHARACTER_RUNTIME_MARKER = "actor_local_perception:character_runtime_seen=true"
ALL_CHECKS_COMPLETE_MARKER = "actor_local_perception_probe:all_checks_complete=true"
PROBE_SCENE = "res://scenes/phase0/ActorLocalPerceptionProbe.tscn"


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
    runtime_log_path = Path(args.runtime_log) if args.runtime_log else log_dir / "actor-local-perception.log"
    godot_exe = resolve_godot_exe(args.godot_exe)
    python_exe = resolve_python_exe(args.python_exe)

    backend_process = None
    try:
        _health, backend_process = ensure_backend(project_root, python_exe, prefer_fresh_backend=True)
        ensure_godot_import(project_root, godot_exe, "actor-local-perception-godot-import.log")
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
    sampler_source = read_text(project_root / "scripts" / "character" / "ActorPerceptionSampler.gd")
    scene_source = read_text(project_root / "scenes" / "phase0" / "CharacterReplica.tscn")

    runtime_log_note = "" if runtime_log_text != "" else "Runtime probe did not produce a log."

    results = [
        _result(
            "actor_local_perception_static_wiring",
            "CharacterReplica owns actor-local perception sampler and emitter seam",
            all(
                token in replica_source
                for token in (
                    "ActorPerceptionSampler",
                    "ActorPerceptionTargetResolver",
                    "_sample_actor_local_perception",
                    "_emit_actor_notice_fact",
                    "_emit_arrival_fact",
                )
            )
            and "CharacterVisualFactEmitter" in scene_source
            and "SpatialAccessFactEmitter" in scene_source
            and "sample_visible_targets" in sampler_source,
            [
                "scripts/character/CharacterReplica.gd",
                "scripts/character/ActorPerceptionSampler.gd",
                "scenes/phase0/CharacterReplica.tscn",
            ],
        ),
        _result(
            "actor_local_perception_notice_emitted",
            "Actor-local perception emits a notice marker at runtime",
            NOTICE_MARKER in runtime_log_text,
            [str(runtime_log_path)] if runtime_log_path is not None and NOTICE_MARKER in runtime_log_text else [],
            runtime_log_note,
        ),
        _result(
            "actor_local_perception_fact_routed",
            "Actor-local perception routes through the standard fact fabric at runtime",
            FACT_ROUTED_MARKER in runtime_log_text,
            [str(runtime_log_path)] if runtime_log_path is not None and FACT_ROUTED_MARKER in runtime_log_text else [],
            runtime_log_note,
        ),
        _result(
            "actor_local_perception_character_runtime_seen",
            "Character runtime reports the actor-local perception hook firing",
            CHARACTER_RUNTIME_MARKER in runtime_log_text,
            [str(runtime_log_path)] if runtime_log_path is not None and CHARACTER_RUNTIME_MARKER in runtime_log_text else [],
            runtime_log_note,
        ),
    ]
    overall_passed = all(str(entry["status"]) == "proved" for entry in results)
    report = {
        "results": results,
        "overall_actor_local_perception_passed": overall_passed,
        "artifacts": {
            "runtime_log": str(runtime_log_path),
        },
    }

    json_path = log_dir / "actor-local-perception-report.json"
    md_path = log_dir / "actor-local-perception-report.md"
    write_json(json_path, report)
    write_markdown(
        md_path,
        "Actor Local Perception Verification Report",
        report,
        "overall_actor_local_perception_passed",
    )

    print(f"actor_local_perception_report_json={json_path}")
    print(f"actor_local_perception_report_md={md_path}")
    print(f"overall_actor_local_perception_passed={report['overall_actor_local_perception_passed']}")
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
