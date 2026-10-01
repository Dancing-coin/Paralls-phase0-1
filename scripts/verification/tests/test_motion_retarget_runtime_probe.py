import subprocess
import argparse
import json
import os
from pathlib import Path


def test_retarget_runtime_probe_requires_all_gates() -> None:
    result = subprocess.run(_probe_command(), check=True, capture_output=True, text=True)
    probe_output = result.stdout
    for field in REQUIRED_FIELDS:
        assert f"{field}=true" in probe_output


REQUIRED_FIELDS = (
        "cache_key_stable",
        "target_tracks_valid",
        "six_states_valid",
        "foot_contact_valid",
        "hand_socket_valid",
        "root_motion_single_consume",
        "rejected_output_blocked",
)


def _probe_command(godot_exe: str | None = None) -> list[str]:
    return [
        godot_exe or r"D:\godot\Godot_v4.6.3-stable_win64_console.exe",
        "--headless",
        "--path",
        ".",
        "--script",
        "res://scripts/verification/motion_retarget_runtime_probe.gd",
    ]


def _harness_evidence_root() -> Path:
    root = os.environ.get("HARNESS_ATTEMPT_ROOT")
    if root:
        return Path(root)
    return Path(__file__).resolve().parents[3] / ".harness" / "verification"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    result = subprocess.run(_probe_command(args.godot_exe), check=False, capture_output=True, text=True)
    fields = {field: f"{field}=true" in result.stdout for field in REQUIRED_FIELDS}
    evidence = {
        "profile": "motion-library-qualification",
        "valid": result.returncode == 0 and all(fields.values()),
        "godot_exit_code": result.returncode,
        "fields": fields,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }
    output = _harness_evidence_root() / "motion-library-qualification.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, sort_keys=True))
    return 0 if evidence["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
