from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from common import read_text, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


REQUIRED_MID_FIELDS = {
    "anchor_refs",
    "facing_vectors",
    "reach_envelope",
    "balance_hints",
    "strain_hints",
    "hand_readiness",
    "contact_candidate_refs",
    "pose_features",
}


def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def _resolve_optional_godot(project_root: Path, explicit: str | None) -> Path | None:
    candidates = [
        explicit,
        str(project_root / "Godot.exe"),
        r"D:\godot\Godot_v4.6.3-stable_win64.exe",
        r"E:\下载\Godot_v4.6.3-stable_win64.exe\Godot_v4.6.3-stable_win64_console.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return Path(candidate)
    return None


def _load_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _runtime_binding_ok(payload: dict[str, object]) -> bool:
    main_payload = payload.get("main_perception_payload", {})
    binding = main_payload.get("runtime_binding", {}) if isinstance(main_payload, dict) else {}
    return (
        isinstance(binding, dict)
        and binding.get("runtime_binding_verified") is True
        and "CharacterReplica" in str(binding.get("character_replica_path", ""))
        and "Skeleton3D" in str(binding.get("skeleton_path", ""))
        and int(binding.get("bone_count", 0)) > 0
    )


def _high_mid_ok(payload: dict[str, object]) -> bool:
    main_payload = payload.get("main_perception_payload", {})
    if not isinstance(main_payload, dict):
        return False
    high = main_payload.get("high_level_state", {})
    mid = main_payload.get("mid_level_parameters", {})
    if not isinstance(high, dict) or not isinstance(mid, dict):
        return False
    return (
        {"posture", "gait", "balance", "strain", "active_behavior", "hand_readiness"}.issubset(set(high))
        and REQUIRED_MID_FIELDS.issubset(set(mid))
        and bool(mid.get("anchor_refs"))
        and bool(mid.get("facing_vectors"))
        and bool(mid.get("contact_candidate_refs"))
    )


def _debug_snapshot_ok(payload: dict[str, object]) -> bool:
    snapshot = payload.get("debug_replay_snapshot", {})
    if not isinstance(snapshot, dict):
        return False
    snapshot_ref = str(snapshot.get("snapshot_ref", ""))
    artifact_path = str(snapshot.get("artifact_path", ""))
    if snapshot.get("retention") != "debug_replay_only" or int(snapshot.get("bone_count", 0)) <= 0:
        return False
    if not artifact_path or not Path(artifact_path).exists():
        return False
    snapshot_payload = _load_json(Path(artifact_path))
    return (
        snapshot_ref.startswith("runtime://artifact/")
        and snapshot_payload.get("retention") == "debug_replay_only"
        and int(snapshot_payload.get("bone_count", 0)) == int(snapshot.get("bone_count", 0))
        and set(snapshot_payload.get("trace_refs", [])) == set(payload.get("trace_refs", []))
    )


def _full_bone_excluded(payload: dict[str, object]) -> bool:
    main_payload = payload.get("main_perception_payload", {})
    return (
        isinstance(main_payload, dict)
        and payload.get("full_bone_main_chain_excluded") is True
        and "low_level_snapshot" not in main_payload
        and "bones" not in main_payload
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)

    pytest_log = log_dir / "embodied-skeletal-debug-replay-pytest.log"
    pytest_result = run_command(
        [python_exe, "-m", "pytest", "-q", "backend/tests/test_embodied_skeletal_debug_replay_pipeline.py"],
        project_root,
        pytest_log,
    )

    godot_exe = _resolve_optional_godot(project_root, args.godot_exe)
    godot_log = log_dir / "embodied-skeletal-debug-replay-godot.log"
    runtime_artifact = log_dir / "embodied-skeletal-debug-replay-runtime.json"
    godot_status = "godot-runtime-binding-unverified"
    godot_ok = False
    if godot_exe is not None:
        godot_result = run_command(
            [
                str(godot_exe),
                "--path",
                str(project_root),
                "--scene",
                "res://scenes/phase0/EmbodiedSkeletalRuntimeProbe.tscn",
                "--quit-after",
                "600",
                "--render-thread",
                "safe",
            ],
            project_root,
            godot_log,
        )
        godot_text = read_text(godot_log)
        godot_ok = (
            godot_result.returncode == 0
            and "embodied_skeletal_runtime_probe:runtime_binding=true" in godot_text
            and runtime_artifact.exists()
        )
        godot_status = "godot-runtime-binding-verified" if godot_ok else "godot-runtime-binding-unverified"

    payload = _load_json(runtime_artifact)
    backend_ok = pytest_result.returncode == 0
    binding_ok = godot_ok and _runtime_binding_ok(payload)
    high_mid_ok = _high_mid_ok(payload)
    debug_ok = _debug_snapshot_ok(payload)
    exclusion_ok = _full_bone_excluded(payload)
    trace_ok = bool(payload.get("trace_refs")) and debug_ok

    results = [
        _result(
            "backend-contract-verified",
            "Backend skeletal debug replay contract tests pass",
            backend_ok,
            [str(pytest_log)],
        ),
        {
            "id": "godot-runtime-binding-verified",
            "title": "Godot probe binds PlayerCharacter, CharacterReplica and Skeleton3D",
            "status": "proved" if binding_ok else godot_status,
            "evidence": [str(godot_log), str(runtime_artifact)] if godot_exe is not None else [],
            "notes": "" if binding_ok else "Godot executable unavailable or runtime binding did not prove Skeleton3D/CharacterReplica.",
        },
        _result(
            "high-mid-level-state-verified",
            "High-level embodied state and mid-level skeletal parameters are present",
            high_mid_ok,
            [str(runtime_artifact)],
        ),
        _result(
            "debug-replay-artifact-verified",
            "Low-level full bone snapshot is written as debug replay artifact",
            debug_ok,
            [str(runtime_artifact)],
        ),
        _result(
            "full-bone-main-chain-exclusion-verified",
            "Main perception payload excludes full bone payload",
            exclusion_ok,
            [str(runtime_artifact)],
        ),
        _result(
            "failure-trace-alignment-verified",
            "Debug snapshot refs align with PQF, bundle and failure trace refs",
            trace_ok,
            [str(runtime_artifact)],
        ),
    ]
    overall = backend_ok and binding_ok and high_mid_ok and debug_ok and exclusion_ok and trace_ok
    report = {
        "overall_embodied_skeletal_debug_replay_passed": overall,
        "godot_runtime_status": godot_status,
        "results": results,
        "artifacts": {
            "pytest_log": str(pytest_log),
            "godot_log": str(godot_log),
            "runtime_artifact": str(runtime_artifact),
        },
    }
    json_path = log_dir / "embodied-skeletal-debug-replay-report.json"
    md_path = log_dir / "embodied-skeletal-debug-replay-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Embodied Skeletal Debug Replay Verification Report", report, "overall_embodied_skeletal_debug_replay_passed")

    print(f"embodied_skeletal_debug_replay_report_json={json_path}")
    print(f"embodied_skeletal_debug_replay_report_md={md_path}")
    print(f"overall_embodied_skeletal_debug_replay_passed={overall}")
    print(f"godot_runtime_status={godot_status}")
    for entry in results:
        print(f"{entry['id']}={entry['status']}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
