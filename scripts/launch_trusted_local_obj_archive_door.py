"""Launch a Godot door verifier with one backend-issued trusted-local embodied-controller enrollment."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.embodied_controller_auth_service import EmbodiedControllerEnrollment
from app.services.trusted_local_embodied_controller_launcher import EmbodiedControllerGodotLaunchHandoff


def request_enrollment(*, backend_http_url: str, launch_profile_ref: str, launcher_secret: str) -> EmbodiedControllerEnrollment:
    request = Request(
        f"{backend_http_url.rstrip('/')}/internal/trusted-local-embodied-controller-enrollment",
        data=json.dumps({"launch_profile_ref": launch_profile_ref}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Embodied-Controller-Launcher-Secret": launcher_secret,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError("trusted_local_embodied_controller_enrollment_request_failed") from exc
    return EmbodiedControllerEnrollment.model_validate(payload)


def build_godot_child_environment(
    *,
    parent_environment: Mapping[str, str],
    enrollment: EmbodiedControllerEnrollment,
) -> dict[str, str]:
    child_environment = dict(parent_environment)
    child_environment.pop("EMBODIED_CONTROLLER_LAUNCHER_BOOTSTRAP_SECRET", None)
    child_environment.pop("EMBODIED_CONTROLLER_TRUSTED_LOCAL_LAUNCH_PROFILES_JSON", None)
    child_environment.update(EmbodiedControllerGodotLaunchHandoff(enrollment=enrollment).child_environment())
    return child_environment


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--launch-profile-ref", required=True)
    parser.add_argument("--godot-exe", required=True)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--backend-http-url", default="http://127.0.0.1:8000")
    parser.add_argument("--backend-ws-url", default="ws://127.0.0.1:8000/ws")
    args, remaining = parser.parse_known_args()

    launcher_secret = os.getenv("EMBODIED_CONTROLLER_LAUNCHER_BOOTSTRAP_SECRET", "")
    if not launcher_secret:
        raise SystemExit("trusted_local_embodied_controller_launcher_secret_missing")
    enrollment = request_enrollment(
        backend_http_url=args.backend_http_url,
        launch_profile_ref=args.launch_profile_ref,
        launcher_secret=launcher_secret,
    )
    child_environment = build_godot_child_environment(parent_environment=os.environ, enrollment=enrollment)
    child_environment["PARALLS_BACKEND_WS_URL"] = args.backend_ws_url
    result = subprocess.run(
        [args.godot_exe, "--path", str(ROOT), "--scene", args.scene, *remaining],
        cwd=ROOT,
        env=child_environment,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
