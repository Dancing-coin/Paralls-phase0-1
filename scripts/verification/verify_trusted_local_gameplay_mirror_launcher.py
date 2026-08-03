from __future__ import annotations

import argparse
import json

from common import (
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
    root = repo_root()
    log_dir = verification_dir(root)
    secret = "trusted-local-gameplay-mirror-verifier-secret"
    backend_environment = {
        "GAMEPLAY_MIRROR_LAUNCHER_BOOTSTRAP_SECRET": secret,
        "GAMEPLAY_MIRROR_TRUSTED_LOCAL_LAUNCH_PROFILES_JSON": json.dumps(
            [
                {
                    "profile_ref": "mirror-live-probe",
                    "principal_ref": "principal:mirror-live-probe",
                    "allowed_actor_refs": ["actor:visible"],
                    "credential_ttl_seconds": 30,
                }
            ]
        ),
    }
    backend = None
    result = None
    launcher_log = log_dir / "trusted-local-gameplay-mirror-launcher.log"
    runtime_artifact = log_dir / "trusted-local-gameplay-mirror-launch-runtime.json"
    try:
        _, backend = ensure_backend(
            root,
            resolve_python_exe(args.python_exe),
            prefer_fresh_backend=True,
            env=backend_environment,
        )
        result = run_command(
            [
                resolve_python_exe(args.python_exe),
                "scripts/launch_trusted_local_gameplay_mirror.py",
                "--launch-profile-ref",
                "mirror-live-probe",
                "--godot-exe",
                str(resolve_godot_exe(args.godot_exe)),
                "--scene",
                "res://scenes/phase0/TrustedLocalGameplayMirrorLaunchProbe.tscn",
                "--headless",
                "--quit-after",
                "300",
                "--render-thread",
                "safe",
            ],
            root,
            launcher_log,
            env=backend_environment,
            timeout_seconds=45,
        )
    finally:
        stop_backend(backend)
    try:
        runtime_payload = json.loads(runtime_artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        runtime_payload = {}
    passed = result is not None and result.returncode == 0 and runtime_payload.get("status") == "trusted-local-gameplay-mirror-live-bind-verified"
    report = {
        "overall_trusted_local_gameplay_mirror_launcher_passed": passed,
        "results": [
            {
                "id": "live-launcher-to-godot-bind",
                "title": "Backend-issued opaque enrollment reaches a real Godot BackendBridge bind",
                "status": "proved" if passed else "missing",
                "evidence": [str(launcher_log), str(runtime_artifact)] if passed else [],
                "notes": "Credential and launcher bootstrap secret are excluded from artifacts.",
            }
        ],
    }
    write_json(log_dir / "trusted-local-gameplay-mirror-launcher-report.json", report)
    write_markdown(
        log_dir / "trusted-local-gameplay-mirror-launcher-report.md",
        "Trusted-Local Gameplay Mirror Launcher Verification Report",
        report,
        "overall_trusted_local_gameplay_mirror_launcher_passed",
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
