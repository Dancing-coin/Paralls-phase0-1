from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import time

from common import ensure_backend, repo_root, resolve_godot_exe, resolve_python_exe, stop_backend, verification_dir, run_command_until_markers


ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "docs" / "character" / "character-action-foundation-current-state.md"
EVIDENCE_PATH = ROOT / ".harness" / "verification" / "unified-character-action-foundation-baseline.json"
RUNTIME_EVIDENCE_PATH = ROOT / ".harness" / "verification" / "unified-character-action-foundation-runtime.json"
ACTIVE_SCENES = (
    ROOT / "scenes" / "phase0" / "PlayerShell.tscn",
    ROOT / "scenes" / "phase0" / "CharacterReplica.tscn",
)


def _scene_control_paths() -> list[dict[str, object]]:
    paths: list[dict[str, object]] = []
    for scene_path in ACTIVE_SCENES:
        scene = scene_path.read_text(encoding="utf-8")
        paths.append(
            {
                "scene_reference": scene_path.relative_to(ROOT).as_posix(),
                "character_body_count": scene.count('type="CharacterBody3D"'),
                "motor_count": scene.count('name="CharacterMotor" type="Node" parent="."'),
            }
        )
    return paths


def verify_baseline() -> dict[str, object]:
    ledger = LEDGER.read_text(encoding="utf-8")
    control_paths = _scene_control_paths()
    return {
        "stage": "baseline",
        "ledger_present": "## Migration Ledger" in ledger,
        "ledger_rows": [line for line in ledger.splitlines() if line.startswith("| `")],
        "control_paths": control_paths,
        "valid": "## Migration Ledger" in ledger
        and all(path["character_body_count"] == 1 and path["motor_count"] == 1 for path in control_paths),
    }


def verify_release() -> dict[str, object]:
    ledger = LEDGER.read_text(encoding="utf-8")
    profile = ROOT / ".harness" / "profiles" / "unified-character-action-foundation.json"
    return {
        "stage": "release",
        "mode": "B",
        "mode_c_enabled": False,
        "dynamic_rigidbody_bitwise_determinism": False,
        "profile_present": profile.exists(),
        "ownership_boundary_recorded": "CharacterMotor" in ledger and "ESM/Gameplay" in ledger,
        "valid": profile.exists() and "CharacterMotor" in ledger and "ESM/Gameplay" in ledger,
    }


def _read_runtime_report() -> dict[str, object]:
    try:
        payload = json.loads(RUNTIME_EVIDENCE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def verify_runtime(*, godot_exe: str | None, python_exe: str | None) -> dict[str, object]:
    root = repo_root()
    godot = resolve_godot_exe(godot_exe)
    python = resolve_python_exe(python_exe)
    log_dir = verification_dir(root)
    if RUNTIME_EVIDENCE_PATH.exists():
        RUNTIME_EVIDENCE_PATH.unlink()
    env = {"PARALLS_HEAVENLY_GRAPH_PATH": ":memory:", "PARALLS_BACKEND_WS_URL": "ws://127.0.0.1:8000/ws", "PHASE0_DEBUG_LOGGING": "1"}
    backend = None
    godot_result = None
    error = ""
    try:
        _, backend = ensure_backend(root, python, prefer_fresh_backend=True, env=env)
        child_env = os.environ.copy()
        child_env.update(env)
        godot_result = run_command_until_markers(
            [str(godot), "--headless", "--path", str(root), "--scene", "res://scenes/integration/UnifiedCharacterActionFoundation.tscn", "--quit-after", "900", "--render-thread", "safe", "--rendering-method", "gl_compatibility"],
            root,
            log_dir / "unified-character-action-foundation-godot.log",
            success_markers=["unified_character_action_foundation_probe:verified=true"],
            timeout_seconds=45,
            env=child_env,
        )
    except Exception as exc:
        error = f"{type(exc).__name__}:{exc}"
    finally:
        stop_backend(backend)
    report = _read_runtime_report()
    required = ("backend_connected", "shared_motor_owner", "agent_inf_intent_seen", "melee_authority_committed", "hitscan_authority_seen", "duplicate_replayed", "stale_rejected", "rejection_recovered")
    valid = bool(godot_result and godot_result.marker_found and all(bool(report.get(key)) for key in required) and report.get("mode") == "B" and report.get("body_stream_seen") is False)
    result = {"stage": "runtime", "valid": valid, "godot_exit_code": getattr(godot_result, "returncode", None), "godot_marker_found": bool(godot_result and godot_result.marker_found), "runtime_report": report, "error": error}
    (log_dir / "unified-character-action-foundation-runtime-verifier.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("baseline", "runtime", "release"), default="runtime")
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    evidence = verify_runtime(godot_exe=args.godot_exe, python_exe=args.python_exe) if args.stage == "runtime" else (verify_release() if args.stage == "release" else verify_baseline())
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, sort_keys=True))
    return 0 if bool(evidence["valid"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
