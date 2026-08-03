from __future__ import annotations

import inspect
from pathlib import Path
import runpy

import pytest
from fastapi.testclient import TestClient

from app.services.websocket_session_auth_service import WebSocketSessionAuthService


def _issuer():
    from app.services.trusted_local_gameplay_mirror_launcher import (
        TrustedLocalGameplayMirrorEnrollmentIssuer,
        TrustedLocalGameplayMirrorLaunchProfile,
    )

    return TrustedLocalGameplayMirrorEnrollmentIssuer(
        auth_service=WebSocketSessionAuthService(),
        launch_profiles=(
            TrustedLocalGameplayMirrorLaunchProfile(
                profile_ref="mirror-demo",
                principal_ref="principal:demo-player",
                allowed_actor_refs=("actor:visible",),
                credential_ttl_seconds=30,
            ),
        ),
    )


def test_issuer_uses_only_configured_profile_subject_and_scope() -> None:
    issuer = _issuer()

    enrollment = issuer.issue_for_launch_profile("mirror-demo", now=100)

    assert enrollment.credential_kind == "trusted_local_launch"
    assert enrollment.protocol_version == 1
    assert enrollment.credential.startswith("trusted_local_launch:")
    assert not hasattr(enrollment, "principal_ref")
    assert not hasattr(enrollment, "allowed_actor_refs")
    assert set(inspect.signature(issuer.issue_for_launch_profile).parameters) == {"launch_profile_ref", "now"}


def test_issuer_rejects_unknown_profile_without_creating_a_credential() -> None:
    issuer = _issuer()

    with pytest.raises(ValueError, match="trusted_local_gameplay_mirror_launch_profile_unknown"):
        issuer.issue_for_launch_profile("actor:client-chosen", now=100)


def test_issued_enrollment_is_one_time_and_remains_subject_to_existing_loopback_binding() -> None:
    issuer = _issuer()
    enrollment = issuer.issue_for_launch_profile("mirror-demo", now=100)

    accepted = issuer.auth_service.bind_session(enrollment, remote_host="127.0.0.1", now=101)
    replay = issuer.auth_service.bind_session(enrollment, remote_host="127.0.0.1", now=102)
    remote = issuer.auth_service.bind_session(
        issuer.issue_for_launch_profile("mirror-demo", now=100),
        remote_host="203.0.113.8",
        now=101,
    )

    assert accepted.accepted is True
    assert accepted.binding is not None
    assert accepted.binding.principal_ref == "principal:demo-player"
    assert accepted.binding.allowed_actor_refs == ("actor:visible",)
    assert replay.error_code == "trusted_local_launch_already_used"
    assert remote.error_code == "trusted_local_launch_requires_loopback"


def test_godot_child_handoff_exposes_only_opaque_enrollment() -> None:
    from app.services.trusted_local_gameplay_mirror_launcher import GameplayMirrorGodotLaunchHandoff

    enrollment = _issuer().issue_for_launch_profile("mirror-demo", now=100)
    environment = GameplayMirrorGodotLaunchHandoff(enrollment=enrollment).child_environment()

    assert set(environment) == {"PARALLS_GAMEPLAY_MIRROR_ENROLLMENT_JSON"}
    assert "trusted_local_launch:" in environment["PARALLS_GAMEPLAY_MIRROR_ENROLLMENT_JSON"]
    assert "principal:demo-player" not in environment["PARALLS_GAMEPLAY_MIRROR_ENROLLMENT_JSON"]
    assert "allowed_actor_refs" not in environment["PARALLS_GAMEPLAY_MIRROR_ENROLLMENT_JSON"]


def _configured_runtime_issuer():
    import app.main as main
    from app.services.trusted_local_gameplay_mirror_launcher import (
        TrustedLocalGameplayMirrorEnrollmentIssuer,
        TrustedLocalGameplayMirrorLaunchProfile,
    )

    main.reset_runtime_state()
    main.gameplay_mirror_trusted_local_enrollment_issuer = TrustedLocalGameplayMirrorEnrollmentIssuer(
        auth_service=main.websocket_session_auth_service,
        launch_profiles=(
            TrustedLocalGameplayMirrorLaunchProfile(
                profile_ref="mirror-demo",
                principal_ref="principal:demo-player",
                allowed_actor_refs=("actor:visible",),
                credential_ttl_seconds=30,
            ),
        ),
    )
    main.gameplay_mirror_launcher_bootstrap_secret = "launcher-test-secret"
    return main


def test_runtime_issuer_route_requires_loopback_bootstrap_and_profile_only_payload() -> None:
    main = _configured_runtime_issuer()
    client = TestClient(main.app, client=("127.0.0.1", 47003))

    denied = client.post(
        "/internal/trusted-local-gameplay-mirror-enrollment",
        headers={"X-Gameplay-Mirror-Launcher-Secret": "wrong"},
        json={"launch_profile_ref": "mirror-demo"},
    )
    malformed = client.post(
        "/internal/trusted-local-gameplay-mirror-enrollment",
        headers={"X-Gameplay-Mirror-Launcher-Secret": "launcher-test-secret"},
        json={"launch_profile_ref": "mirror-demo", "allowed_actor_refs": ["actor:forbidden"]},
    )
    accepted = client.post(
        "/internal/trusted-local-gameplay-mirror-enrollment",
        headers={"X-Gameplay-Mirror-Launcher-Secret": "launcher-test-secret"},
        json={"launch_profile_ref": "mirror-demo"},
    )

    assert denied.status_code == 403
    assert denied.json()["detail"]["error_code"] == "trusted_local_gameplay_mirror_launcher_unauthorized"
    assert malformed.status_code == 422
    assert accepted.status_code == 200
    assert set(accepted.json()) == {"credential_kind", "credential", "protocol_version"}
    assert "principal_ref" not in accepted.text
    assert "allowed_actor_refs" not in accepted.text


def test_runtime_issuer_route_credential_binds_once_and_remote_call_is_rejected() -> None:
    main = _configured_runtime_issuer()
    loopback = TestClient(main.app, client=("127.0.0.1", 47004))
    remote = TestClient(main.app, client=("203.0.113.9", 47005))

    issued = loopback.post(
        "/internal/trusted-local-gameplay-mirror-enrollment",
        headers={"X-Gameplay-Mirror-Launcher-Secret": "launcher-test-secret"},
        json={"launch_profile_ref": "mirror-demo"},
    )
    remote_attempt = remote.post(
        "/internal/trusted-local-gameplay-mirror-enrollment",
        headers={"X-Gameplay-Mirror-Launcher-Secret": "launcher-test-secret"},
        json={"launch_profile_ref": "mirror-demo"},
    )
    enrollment = issued.json()

    first = main.websocket_session_auth_service.bind_session(
        main.WebSocketSessionEnrollment.model_validate(enrollment),
        remote_host="127.0.0.1",
        now=1_000_000_000,
    )
    replay = main.websocket_session_auth_service.bind_session(
        main.WebSocketSessionEnrollment.model_validate(enrollment),
        remote_host="127.0.0.1",
        now=1_000_000_001,
    )

    assert issued.status_code == 200
    assert remote_attempt.status_code == 403
    assert remote_attempt.json()["detail"]["error_code"] == "trusted_local_gameplay_mirror_launcher_requires_loopback"
    assert first.accepted is True
    assert replay.error_code == "trusted_local_launch_already_used"


def test_live_probe_commit_route_uses_only_configured_actor_and_existing_after_commit_pipeline(monkeypatch) -> None:
    import app.main as main

    configuration = {
        "actor_ref": "actor:live-probe",
        "state_group_definitions": [{"group_id": "core.resources", "definition_version": "1", "projection_schema_version": 1}],
        "godot_view_policies": [{"group_id": "core.resources", "godot_allowed_fields": ["entries"]}],
        "godot_allowed_group_ids": ["core.resources"],
        "registry_revision": "registry:live:v1",
        "world_config_revision": "world:live:v1",
        "active_patch_set_revision": "patch:live:v1",
    }
    monkeypatch.setattr(main.settings, "gameplay_mirror_phase3_actor_configs", [configuration])
    main = _configured_runtime_issuer()
    client = TestClient(main.app, client=("127.0.0.1", 47006))

    denied = client.post("/internal/trusted-local-gameplay-mirror-live-probe-commit")
    accepted = client.post(
        "/internal/trusted-local-gameplay-mirror-live-probe-commit",
        headers={"X-Gameplay-Mirror-Launcher-Secret": "launcher-test-secret"},
        json={"actor_ref": "actor:forbidden"},
    )

    assert denied.status_code == 403
    assert accepted.status_code == 422
    committed = client.post(
        "/internal/trusted-local-gameplay-mirror-live-probe-commit",
        headers={"X-Gameplay-Mirror-Launcher-Secret": "launcher-test-secret"},
        json={},
    )
    assert committed.status_code == 200
    assert committed.json()["actor_ref"] == "actor:live-probe"
    assert main.gameplay_mirror_outbox_refresh_consumer.results


def test_live_reconnect_probe_commit_uses_second_server_configured_actor(monkeypatch) -> None:
    import app.main as main

    configurations = [
        {
            "actor_ref": "actor:live-probe",
            "state_group_definitions": [{"group_id": "core.resources", "definition_version": "1", "projection_schema_version": 1}],
            "godot_view_policies": [{"group_id": "core.resources", "godot_allowed_fields": ["entries"]}],
            "godot_allowed_group_ids": ["core.resources"],
            "registry_revision": "registry:live:v1",
            "world_config_revision": "world:live:v1",
            "active_patch_set_revision": "patch:live:v1",
        },
        {
            "actor_ref": "actor:live-reconnect",
            "state_group_definitions": [{"group_id": "core.resources", "definition_version": "1", "projection_schema_version": 1}],
            "godot_view_policies": [{"group_id": "core.resources", "godot_allowed_fields": ["entries"]}],
            "godot_allowed_group_ids": ["core.resources"],
            "registry_revision": "registry:live:v1",
            "world_config_revision": "world:live:v1",
            "active_patch_set_revision": "patch:live:v1",
        },
    ]
    monkeypatch.setattr(main.settings, "gameplay_mirror_phase3_actor_configs", configurations)
    main = _configured_runtime_issuer()
    client = TestClient(main.app, client=("127.0.0.1", 47007))

    committed = client.post(
        "/internal/trusted-local-gameplay-mirror-live-probe-reconnect-commit",
        headers={"X-Gameplay-Mirror-Launcher-Secret": "launcher-test-secret"},
        json={"actor_ref": "actor:forbidden"},
    )

    assert committed.status_code == 422
    accepted = client.post(
        "/internal/trusted-local-gameplay-mirror-live-probe-reconnect-commit",
        headers={"X-Gameplay-Mirror-Launcher-Secret": "launcher-test-secret"},
        json={},
    )
    assert accepted.status_code == 200
    assert accepted.json()["actor_ref"] == "actor:live-reconnect"
    assert main.gameplay_mirror_outbox_refresh_consumer.results


def test_live_probe_repeat_commit_keeps_existing_phase3_source_available(monkeypatch) -> None:
    import app.main as main

    configuration = {
        "actor_ref": "actor:live-probe",
        "state_group_definitions": [{"group_id": "core.resources", "definition_version": "1", "projection_schema_version": 1}],
        "godot_view_policies": [{"group_id": "core.resources", "godot_allowed_fields": ["entries"]}],
        "godot_allowed_group_ids": ["core.resources"],
        "registry_revision": "registry:live:v1",
        "world_config_revision": "world:live:v1",
        "active_patch_set_revision": "patch:live:v1",
    }
    monkeypatch.setattr(main.settings, "gameplay_mirror_phase3_actor_configs", [configuration])
    main = _configured_runtime_issuer()
    client = TestClient(main.app, client=("127.0.0.1", 47008))
    headers = {"X-Gameplay-Mirror-Launcher-Secret": "launcher-test-secret"}

    assert client.post("/internal/trusted-local-gameplay-mirror-live-probe-commit", headers=headers, json={}).status_code == 200
    assert client.post("/internal/trusted-local-gameplay-mirror-live-probe-commit", headers=headers, json={}).status_code == 200
    assert main.gameplay_godot_projection_publisher.refresh_actor(actor_ref="actor:live-probe").actor_ref == "actor:live-probe"


def test_launcher_child_environment_strips_issuer_secrets_and_profile_configuration() -> None:
    launcher = runpy.run_path(
        str(Path(__file__).resolve().parents[2] / "scripts" / "launch_trusted_local_gameplay_mirror.py")
    )
    enrollment = _issuer().issue_for_launch_profile("mirror-demo", now=100)

    environment = launcher["build_godot_child_environment"](
        parent_environment={
            "GAMEPLAY_MIRROR_LAUNCHER_BOOTSTRAP_SECRET": "launcher-test-secret",
            "GAMEPLAY_MIRROR_TRUSTED_LOCAL_LAUNCH_PROFILES_JSON": "sensitive-server-config",
            "PARALLS_BACKEND_WS_URL": "ws://127.0.0.1:8000/ws",
        },
        enrollment=enrollment,
    )

    assert "GAMEPLAY_MIRROR_LAUNCHER_BOOTSTRAP_SECRET" not in environment
    assert "GAMEPLAY_MIRROR_TRUSTED_LOCAL_LAUNCH_PROFILES_JSON" not in environment
    assert environment["PARALLS_BACKEND_WS_URL"] == "ws://127.0.0.1:8000/ws"
    assert set(key for key in environment if key.startswith("PARALLS_GAMEPLAY_MIRROR")) == {
        "PARALLS_GAMEPLAY_MIRROR_ENROLLMENT_JSON"
    }


def test_gameplay_mirror_bridge_loads_only_opaque_launcher_enrollment() -> None:
    source = (
        Path(__file__).resolve().parents[2] / "scripts" / "interaction" / "GameplayMirrorBridge.gd"
    ).read_text(encoding="utf-8")

    assert "func load_session_enrollment_from_environment() -> int:" in source
    assert 'OS.get_environment("PARALLS_GAMEPLAY_MIRROR_ENROLLMENT_JSON")' in source
    assert "principal_ref" not in source
    assert "allowed_actor_refs" in source  # Server-bound result remains the only scope source.


def test_live_delivery_probe_uses_backend_bridge_and_server_commit_handoff() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "scripts" / "verification" / "LiveGameplayMirrorDeliveryProbe.gd").read_text(encoding="utf-8")
    verifier = (root / "scripts" / "verification" / "verify_live_gameplay_mirror_delivery.py").read_text(encoding="utf-8")

    assert "load_session_enrollment_from_environment" in source
    assert "gameplay_mirror_delivery_received" in source
    assert "trusted-local-gameplay-mirror-live-probe-commit" in verifier
    assert "ensure_backend" in verifier
    assert "PARALLS_GAMEPLAY_MIRROR_RECONNECT_ENROLLMENT_PATH" in source
    assert "mirror-live-reconnect" in verifier
    assert "actor:live-reconnect" in verifier
    assert "trusted-local-gameplay-mirror-live-probe-reconnect-commit" in verifier
    assert "_actor_ref != _first_actor_ref" in source
    assert "GAMEPLAY_MIRROR_LIVE_PROBE_DROP_FIRST_DELIVERY" in verifier
    assert "live_gap_resync" in source


def test_godot_mirror_harness_runs_each_required_live_recovery_scenario() -> None:
    root = Path(__file__).resolve().parents[2]
    verifier = (root / "scripts" / "verification" / "verify_godot_gameplay_mirror.py").read_text(encoding="utf-8")

    assert 'LIVE_SCENARIOS = ("reconnect", "gap", "backpressure")' in verifier
    assert '"--scenario", scenario' in verifier
