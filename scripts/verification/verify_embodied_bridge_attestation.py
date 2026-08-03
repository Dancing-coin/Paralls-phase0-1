from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from common import read_text, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = ["backend/tests/test_embodied_controller_auth_ingress.py"]


def _result(check_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": check_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    pytest_log = log_dir / "embodied-bridge-attestation-pytest.log"
    pytest_result = run_command([python_exe, "-m", "pytest", "-q", *TEST_FILES], project_root, pytest_log)

    godot_log = log_dir / "embodied-bridge-attestation-godot.log"
    godot_artifact = log_dir / "embodied-bridge-attestation-godot-runtime.json"
    godot_ok = False
    if args.godot_exe:
        godot_result = run_command(
            [
                args.godot_exe,
                "--headless",
                "--path",
                str(project_root),
                "--scene",
                "res://scenes/phase0/EmbodiedBridgeAttestationProbe.tscn",
                "--quit-after",
                "300",
                "--render-thread",
                "safe",
            ],
            project_root,
            godot_log,
        )
        godot_text = read_text(godot_log)
        godot_ok = (
            godot_result.returncode == 0
            and "embodied_bridge_attestation_probe:verified=true" in godot_text
            and godot_artifact.exists()
        )
    try:
        godot_payload = json.loads(godot_artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        godot_payload = {}

    results = [
        _result(
            "focused-pytest-pass",
            "Embodied controller auth and ingress focused pytest suite passes",
            pytest_result.returncode == 0,
            [str(pytest_log)],
        ),
        _result(
            "trusted-local-loopback-one-time",
            "trusted_local_launch is loopback-only and one-time, while authenticated_session fails closed without adapter",
            pytest_result.returncode == 0,
            [str(pytest_log)],
        ),
        _result(
            "grant-attestation-idempotency",
            "controller binding, epoch, grant, nonce, sequence, revocation, and idempotency checks pass",
            pytest_result.returncode == 0,
            [str(pytest_log)],
        ),
        _result(
            "godot-bridge-dedicated-routes",
            "Godot BackendBridge loads dedicated embodied routes without character_actor_status reuse",
            godot_ok and godot_payload.get("legacy_character_actor_status_reused") is False,
            [str(godot_log), str(godot_artifact)],
        ),
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_embodied_bridge_attestation_passed": overall,
        "results": results,
        "artifacts": {
            "pytest_log": str(pytest_log),
            "godot_log": str(godot_log),
            "godot_runtime": str(godot_artifact),
        },
    }
    json_path = log_dir / "embodied-bridge-attestation-report.json"
    md_path = log_dir / "embodied-bridge-attestation-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Embodied Bridge Attestation Verification Report", report, "overall_embodied_bridge_attestation_passed")
    print(f"embodied_bridge_attestation_report_json={json_path}")
    print(f"embodied_bridge_attestation_report_md={md_path}")
    print(f"overall_embodied_bridge_attestation_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
