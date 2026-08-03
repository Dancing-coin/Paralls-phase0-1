from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.request import Request, urlopen

from common import ensure_backend, repo_root, resolve_godot_exe, resolve_python_exe, stop_backend, verification_dir


def _post_commit(secret: str) -> dict[str, object]:
    request = Request(
        "http://127.0.0.1:8000/internal/trusted-local-gameplay-mirror-live-probe-commit",
        data=b"{}",
        headers={"Content-Type": "application/json", "X-Gameplay-Mirror-Launcher-Secret": secret},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_reconnect_commit(secret: str) -> dict[str, object]:
    request = Request(
        "http://127.0.0.1:8000/internal/trusted-local-gameplay-mirror-live-probe-reconnect-commit",
        data=b"{}",
        headers={"Content-Type": "application/json", "X-Gameplay-Mirror-Launcher-Secret": secret},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _request_enrollment(secret: str, profile_ref: str) -> dict[str, object]:
    request = Request(
        "http://127.0.0.1:8000/internal/trusted-local-gameplay-mirror-enrollment",
        data=json.dumps({"launch_profile_ref": profile_ref}).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Gameplay-Mirror-Launcher-Secret": secret},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    parser.add_argument("--scenario", choices=("reconnect", "gap", "backpressure"), default="reconnect")
    args = parser.parse_args()
    root = repo_root()
    log_dir = verification_dir(root)
    ready_path = log_dir / "live-gameplay-mirror-ready.json"
    first_delivery_path = log_dir / "live-gameplay-mirror-first-delivery.json"
    reconnect_enrollment_path = log_dir / "live-gameplay-mirror-reconnect-enrollment.json"
    stage_path = log_dir / "live-gameplay-mirror-stage.json"
    runtime_path = log_dir / "live-gameplay-mirror-runtime.json"
    for path in (ready_path, first_delivery_path, reconnect_enrollment_path, stage_path, runtime_path):
        if path.exists():
            path.unlink()
    secret = "live-gameplay-mirror-verifier-secret"
    actor_config = {
        "actor_ref": "actor:live-probe",
        "state_group_definitions": [{"group_id": "core.resources", "definition_version": "1", "projection_schema_version": 1}],
        "godot_view_policies": [{"group_id": "core.resources", "godot_allowed_fields": ["entries"]}],
        "godot_allowed_group_ids": ["core.resources"],
        "registry_revision": "registry:live:v1",
        "world_config_revision": "world:live:v1",
        "active_patch_set_revision": "patch:live:v1",
    }
    reconnect_actor_config = {
        **actor_config,
        "actor_ref": "actor:live-reconnect",
    }
    environment = {
        "GAMEPLAY_MIRROR_LAUNCHER_BOOTSTRAP_SECRET": secret,
        "GAMEPLAY_MIRROR_TRUSTED_LOCAL_LAUNCH_PROFILES_JSON": json.dumps([
            {"profile_ref": "mirror-live-probe", "principal_ref": "principal:live-probe", "allowed_actor_refs": ["actor:live-probe"], "credential_ttl_seconds": 30},
            {"profile_ref": "mirror-live-reconnect", "principal_ref": "principal:live-reconnect", "allowed_actor_refs": ["actor:live-reconnect"], "credential_ttl_seconds": 30},
        ]),
        "GAMEPLAY_MIRROR_PHASE3_ACTORS_JSON": json.dumps([actor_config, reconnect_actor_config]),
    }
    if args.scenario == "gap":
        environment["GAMEPLAY_MIRROR_LIVE_PROBE_DROP_FIRST_DELIVERY"] = "true"
    if args.scenario == "backpressure":
        environment.update({
            "GAMEPLAY_MIRROR_PROJECTION_QUEUE_CAPACITY": "1",
            "GAMEPLAY_MIRROR_CONTROL_QUEUE_CAPACITY": "1",
            "GAMEPLAY_MIRROR_DIRTY_ACTOR_LIMIT": "1",
            "GAMEPLAY_MIRROR_LIVE_PROBE_DELIVERY_DELAY_SECONDS": "0.25",
        })
    backend = None
    process = None
    try:
        _, backend = ensure_backend(root, resolve_python_exe(args.python_exe), prefer_fresh_backend=True, env=environment)
        child_env = os.environ.copy()
        child_env.update(environment)
        child_env["PARALLS_LIVE_GAMEPLAY_MIRROR_PROBE_SCENARIO"] = args.scenario
        child_env["PARALLS_GAMEPLAY_MIRROR_RECONNECT_ENROLLMENT_PATH"] = str(reconnect_enrollment_path)
        process = subprocess.Popen(
            [
                resolve_python_exe(args.python_exe), "scripts/launch_trusted_local_gameplay_mirror.py",
                "--launch-profile-ref", "mirror-live-probe", "--godot-exe", str(resolve_godot_exe(args.godot_exe)),
                "--scene", "res://scenes/phase0/LiveGameplayMirrorDeliveryProbe.tscn", "--headless", "--quit-after", "900", "--render-thread", "safe",
            ],
            cwd=root,
            env=child_env,
            stdout=(log_dir / "live-gameplay-mirror-launcher.stdout.log").open("w", encoding="utf-8"),
            stderr=subprocess.STDOUT,
            text=True,
        )
        deadline = time.time() + 15
        while time.time() < deadline and not ready_path.exists() and process.poll() is None:
            time.sleep(0.1)
        if not ready_path.exists():
            return 1
        _post_commit(secret)
        if args.scenario == "gap":
            _post_commit(secret)
        if args.scenario == "backpressure":
            _post_commit(secret)
            _post_commit(secret)
        if args.scenario in {"gap", "backpressure"}:
            deadline = time.time() + 15
            while time.time() < deadline and not runtime_path.exists() and process.poll() is None:
                time.sleep(0.1)
            process.wait(timeout=30)
            expected = "live_gap_resync_verified" if args.scenario == "gap" else "live_backpressure_isolation_verified"
            return 0 if json.loads(runtime_path.read_text(encoding="utf-8")).get("status") == expected else 1
        deadline = time.time() + 15
        while time.time() < deadline and not first_delivery_path.exists() and process.poll() is None:
            time.sleep(0.1)
        if not first_delivery_path.exists():
            return 1
        if args.scenario == "reconnect":
            _post_reconnect_commit(secret)
            reconnect_enrollment_path.write_text(json.dumps(_request_enrollment(secret, "mirror-live-reconnect")), encoding="utf-8")
        process.wait(timeout=30)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
        stop_backend(backend)
    try:
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        runtime = {}
    expected_status = "live_gap_resync_verified" if args.scenario == "gap" else "live-gameplay-mirror-delivery-verified"
    return 0 if runtime.get("status") == expected_status else 1


if __name__ == "__main__":
    raise SystemExit(main())
