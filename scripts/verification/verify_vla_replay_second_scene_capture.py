from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import read_text, repo_root, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a second-scene Godot replay capture.")
    parser.add_argument("--godot-exe", required=True)
    args = parser.parse_args()
    root = repo_root()
    evidence_dir = verification_dir(root)
    log_path = evidence_dir / "vla-replay-second-scene-capture-godot.log"
    result = run_command(
        [
            args.godot_exe,
            "--path",
            str(root),
            "--scene",
            "res://scenes/phase0/VLAReplaySecondSceneCaptureProbe.tscn",
            "--quit-after",
            "300",
            "--render-thread",
            "safe",
        ],
        root,
        log_path,
    )
    runtime_report = root / ".harness/verification/vla-replay-thronehall-walk-preview.json"
    capture_path = root / ".harness/verification/vla-replay-thronehall-walk-preview.png"
    payload = _load_json(runtime_report)
    capture_ok = capture_path.is_file() and capture_path.stat().st_size > 1024
    proved = (
        result.returncode == 0
        and "vla_replay_second_scene_capture:artifact=runtime://artifact/" in read_text(log_path)
        and payload.get("status") == "godot-runtime-replay-capture-verified"
        and payload.get("scene_asset") == "res://scenes/phase0/ThroneHallWalkPreview.tscn"
        and payload.get("render_status") == "meaningful"
        and capture_ok
    )
    report = {
        "overall_vla_replay_second_scene_capture_passed": proved,
        "runtime_report": str(runtime_report),
        "capture_path": str(capture_path),
        "capture_bytes": capture_path.stat().st_size if capture_path.is_file() else 0,
        "godot_log": str(log_path),
        "runtime_payload": payload,
    }
    json_path = evidence_dir / "vla-replay-second-scene-capture-report.json"
    markdown_path = evidence_dir / "vla-replay-second-scene-capture-report.md"
    write_json(json_path, report)
    write_markdown(markdown_path, "VLA Replay Second Scene Capture", report, "overall_vla_replay_second_scene_capture_passed")
    print(f"vla_replay_second_scene_capture_json={json_path}")
    print(f"vla_replay_second_scene_capture_md={markdown_path}")
    print(f"overall_vla_replay_second_scene_capture_passed={proved}")
    return 0 if proved else 1


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
