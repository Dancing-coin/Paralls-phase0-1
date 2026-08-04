from __future__ import annotations

import importlib
import inspect
from pathlib import Path
import runpy

import pytest
from fastapi.testclient import TestClient

import app.config as config_module
from app.services.embodied_controller_auth_service import EmbodiedControllerAuthService


def _issuer():
    from app.services.trusted_local_embodied_controller_launcher import (
        EmbodiedControllerGodotLaunchHandoff,
        TrustedLocalEmbodiedControllerEnrollmentIssuer,
        TrustedLocalEmbodiedControllerLaunchProfile,
    )

    issuer = TrustedLocalEmbodiedControllerEnrollmentIssuer(
        auth_service=EmbodiedControllerAuthService(),
        launch_profiles=(
            TrustedLocalEmbodiedControllerLaunchProfile(
                profile_ref="obj-archive-door-demo",
                actor_id="char_c",
                controller_instance_id="controller:char_c:obj_archive_door:1",
                credential_ttl_seconds=30,
            ),
        ),
    )
    return issuer, EmbodiedControllerGodotLaunchHandoff


def test_issuer_uses_only_configured_actor_and_controller_subjects() -> None:
    issuer, _ = _issuer()

    enrollment = issuer.issue_for_launch_profile("obj-archive-door-demo", now=100)

    assert enrollment.credential_kind == "trusted_local_launch"
    assert enrollment.protocol_version == 1
    assert enrollment.credential.startswith("trusted_local_launch:")
    assert enrollment.actor_id == "char_c"
    assert enrollment.controller_instance_id == "controller:char_c:obj_archive_door:1"
    assert set(inspect.signature(issuer.issue_for_launch_profile).parameters) == {"launch_profile_ref", "now"}


def test_issuer_rejects_unknown_profile_without_creating_a_credential() -> None:
    issuer, _ = _issuer()

    with pytest.raises(ValueError, match="trusted_local_embodied_controller_launch_profile_unknown"):
        issuer.issue_for_launch_profile("controller:client-chosen", now=100)


def test_issued_enrollment_is_one_time_and_remains_subject_to_existing_loopback_binding() -> None:
    issuer, _ = _issuer()
    enrollment = issuer.issue_for_launch_profile("obj-archive-door-demo", now=100)

    accepted = issuer.auth_service.bind_controller(enrollment, remote_host="127.0.0.1", now=101)
    replay = issuer.auth_service.bind_controller(enrollment, remote_host="127.0.0.1", now=102)
    remote = issuer.auth_service.bind_controller(
        issuer.issue_for_launch_profile("obj-archive-door-demo", now=100),
        remote_host="203.0.113.8",
        now=101,
    )

    assert accepted.accepted is True
    assert accepted.binding is not None
    assert accepted.binding.actor_id == "char_c"
    assert accepted.binding.controller_instance_id == "controller:char_c:obj_archive_door:1"
    assert replay.error_code == "trusted_local_launch_already_used"
    assert remote.error_code == "trusted_local_launch_requires_loopback"


def test_godot_child_handoff_exposes_only_opaque_enrollment() -> None:
    issuer, handoff_type = _issuer()
    enrollment = issuer.issue_for_launch_profile("obj-archive-door-demo", now=100)

    environment = handoff_type(enrollment=enrollment).child_environment()

    assert set(environment) == {"PARALLS_EMBODIED_CONTROLLER_ENROLLMENT_JSON"}
    assert "trusted_local_launch:" in environment["PARALLS_EMBODIED_CONTROLLER_ENROLLMENT_JSON"]
    assert '"actor_id":"char_c"' in environment["PARALLS_EMBODIED_CONTROLLER_ENROLLMENT_JSON"]
    assert '"controller_instance_id":"controller:char_c:obj_archive_door:1"' in environment["PARALLS_EMBODIED_CONTROLLER_ENROLLMENT_JSON"]


def _configured_runtime_issuer():
    import app.main as main
    from app.services.trusted_local_embodied_controller_launcher import (
        TrustedLocalEmbodiedControllerEnrollmentIssuer,
        TrustedLocalEmbodiedControllerLaunchProfile,
    )

    main.reset_runtime_state()
    main.embodied_controller_trusted_local_enrollment_issuer = TrustedLocalEmbodiedControllerEnrollmentIssuer(
        auth_service=main.embodied_controller_auth_service,
        launch_profiles=(
            TrustedLocalEmbodiedControllerLaunchProfile(
                profile_ref="obj-archive-door-demo",
                actor_id="char_c",
                controller_instance_id="controller:char_c:obj_archive_door:1",
                credential_ttl_seconds=30,
            ),
        ),
    )
    main.embodied_controller_launcher_bootstrap_secret = "launcher-test-secret"
    return main


def test_runtime_issuer_route_requires_loopback_bootstrap_and_profile_only_payload() -> None:
    main = _configured_runtime_issuer()
    client = TestClient(main.app, client=("127.0.0.1", 47031))

    denied = client.post(
        "/internal/trusted-local-embodied-controller-enrollment",
        headers={"X-Embodied-Controller-Launcher-Secret": "wrong"},
        json={"launch_profile_ref": "obj-archive-door-demo"},
    )
    malformed = client.post(
        "/internal/trusted-local-embodied-controller-enrollment",
        headers={"X-Embodied-Controller-Launcher-Secret": "launcher-test-secret"},
        json={
            "launch_profile_ref": "obj-archive-door-demo",
            "actor_id": "char_a",
            "controller_instance_id": "controller:char_a:forbidden",
        },
    )
    accepted = client.post(
        "/internal/trusted-local-embodied-controller-enrollment",
        headers={"X-Embodied-Controller-Launcher-Secret": "launcher-test-secret"},
        json={"launch_profile_ref": "obj-archive-door-demo"},
    )

    assert denied.status_code == 403
    assert denied.json()["detail"]["error_code"] == "trusted_local_embodied_controller_launcher_unauthorized"
    assert malformed.status_code == 422
    assert accepted.status_code == 200
    assert set(accepted.json()) == {
        "credential_kind",
        "credential",
        "actor_id",
        "controller_instance_id",
        "protocol_version",
    }
    assert '"actor_id":"char_a"' not in accepted.text
    assert '"controller_instance_id":"controller:char_a:forbidden"' not in accepted.text


def test_runtime_issuer_route_credential_binds_once_and_remote_call_is_rejected() -> None:
    main = _configured_runtime_issuer()
    loopback = TestClient(main.app, client=("127.0.0.1", 47032))
    remote = TestClient(main.app, client=("203.0.113.9", 47033))

    issued = loopback.post(
        "/internal/trusted-local-embodied-controller-enrollment",
        headers={"X-Embodied-Controller-Launcher-Secret": "launcher-test-secret"},
        json={"launch_profile_ref": "obj-archive-door-demo"},
    )
    remote_attempt = remote.post(
        "/internal/trusted-local-embodied-controller-enrollment",
        headers={"X-Embodied-Controller-Launcher-Secret": "launcher-test-secret"},
        json={"launch_profile_ref": "obj-archive-door-demo"},
    )
    enrollment = main.EmbodiedControllerEnrollment.model_validate(issued.json())

    first = main.embodied_controller_auth_service.bind_controller(
        enrollment,
        remote_host="127.0.0.1",
        now=1_000_000_000,
    )
    replay = main.embodied_controller_auth_service.bind_controller(
        enrollment,
        remote_host="127.0.0.1",
        now=1_000_000_001,
    )

    assert issued.status_code == 200
    assert remote_attempt.status_code == 403
    assert remote_attempt.json()["detail"]["error_code"] == "trusted_local_embodied_controller_launcher_requires_loopback"
    assert first.accepted is True
    assert replay.error_code == "trusted_local_launch_already_used"


def test_launcher_child_environment_strips_issuer_secrets_and_profile_configuration() -> None:
    launcher = runpy.run_path(
        str(Path(__file__).resolve().parents[2] / "scripts" / "launch_trusted_local_obj_archive_door.py")
    )
    issuer, _ = _issuer()
    enrollment = issuer.issue_for_launch_profile("obj-archive-door-demo", now=100)

    environment = launcher["build_godot_child_environment"](
        parent_environment={
            "EMBODIED_CONTROLLER_LAUNCHER_BOOTSTRAP_SECRET": "launcher-test-secret",
            "EMBODIED_CONTROLLER_TRUSTED_LOCAL_LAUNCH_PROFILES_JSON": "sensitive-server-config",
            "PARALLS_BACKEND_WS_URL": "ws://127.0.0.1:8000/ws",
        },
        enrollment=enrollment,
    )

    assert "EMBODIED_CONTROLLER_LAUNCHER_BOOTSTRAP_SECRET" not in environment
    assert "EMBODIED_CONTROLLER_TRUSTED_LOCAL_LAUNCH_PROFILES_JSON" not in environment
    assert environment["PARALLS_BACKEND_WS_URL"] == "ws://127.0.0.1:8000/ws"
    assert set(key for key in environment if key.startswith("PARALLS_EMBODIED_CONTROLLER")) == {
        "PARALLS_EMBODIED_CONTROLLER_ENROLLMENT_JSON"
    }


def test_settings_read_backend_owned_embodied_controller_launch_configuration(monkeypatch) -> None:
    monkeypatch.setenv(
        "EMBODIED_CONTROLLER_TRUSTED_LOCAL_LAUNCH_PROFILES_JSON",
        '[{"profile_ref":"obj-archive-door-demo","actor_id":"char_c","controller_instance_id":"controller:char_c:obj_archive_door:1","credential_ttl_seconds":45}]',
    )
    monkeypatch.setenv("EMBODIED_CONTROLLER_LAUNCHER_BOOTSTRAP_SECRET", "door-bootstrap-secret")

    try:
        reloaded = importlib.reload(config_module)

        assert reloaded.settings.embodied_controller_launcher_bootstrap_secret == "door-bootstrap-secret"
        assert len(reloaded.settings.embodied_controller_trusted_local_launch_profiles) == 1
        assert reloaded.settings.embodied_controller_trusted_local_launch_profiles[0].actor_id == "char_c"
        assert (
            reloaded.settings.embodied_controller_trusted_local_launch_profiles[0].controller_instance_id
            == "controller:char_c:obj_archive_door:1"
        )
    finally:
        importlib.reload(config_module)


def test_embodied_controller_launch_profile_configuration_requires_json_object_array(monkeypatch) -> None:
    monkeypatch.setenv(
        "EMBODIED_CONTROLLER_TRUSTED_LOCAL_LAUNCH_PROFILES_JSON",
        '{"profile_ref":"obj-archive-door-demo"}',
    )

    try:
        with pytest.raises(ValueError, match="EMBODIED_CONTROLLER_TRUSTED_LOCAL_LAUNCH_PROFILES_JSON"):
            importlib.reload(config_module)
    finally:
        monkeypatch.delenv("EMBODIED_CONTROLLER_TRUSTED_LOCAL_LAUNCH_PROFILES_JSON", raising=False)
        importlib.reload(config_module)
