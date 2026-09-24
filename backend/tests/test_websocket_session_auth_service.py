from app.services.websocket_session_auth_service import WebSocketSessionAuthService, WebSocketSessionEnrollment


def _enrollment(credential: str, *, credential_kind: str = "trusted_local_launch") -> WebSocketSessionEnrollment:
    return WebSocketSessionEnrollment(
        credential_kind=credential_kind,
        credential=credential,
        protocol_version=1,
    )


def test_trusted_local_session_binding_is_opaque_server_owned_and_multi_actor() -> None:
    service = WebSocketSessionAuthService()
    credential = service.create_trusted_local_launch_credential(
        principal_ref="principal:player:1",
        allowed_actor_refs=("actor:a", "actor:b", "actor:a"),
        issued_at=10,
        expires_at=20,
    )

    result = service.bind_session(_enrollment(credential), remote_host="127.0.0.1", now=20)

    assert result.accepted is True
    assert result.binding is not None
    assert result.binding.principal_ref == "principal:player:1"
    assert result.binding.allowed_actor_refs == ("actor:a", "actor:b")
    assert result.binding.session_ref.startswith("ws_session:")
    assert service.resolve_binding(result.binding.session_ref) == result.binding


def test_trusted_local_binding_preserves_only_server_issued_drought_advisory_jurisdiction_scope() -> None:
    service = WebSocketSessionAuthService()
    credential = service.create_trusted_local_launch_credential(
        principal_ref="principal:player:1",
        allowed_actor_refs=("actor:a",),
        allowed_government_drought_advisory_jurisdiction_refs=("jurisdiction:one", "jurisdiction:one"),
        issued_at=10,
        expires_at=20,
    )

    result = service.bind_session(_enrollment(credential), remote_host="127.0.0.1", now=11)

    assert result.accepted and result.binding is not None
    assert result.binding.allowed_government_drought_advisory_jurisdiction_refs == ("jurisdiction:one",)


def test_trusted_local_session_binding_rejects_remote_peer_expiry_and_replay() -> None:
    service = WebSocketSessionAuthService()
    credential = service.create_trusted_local_launch_credential(
        principal_ref="principal:player:1",
        allowed_actor_refs=("actor:a",),
        issued_at=10,
        expires_at=20,
    )

    assert service.bind_session(_enrollment(credential), remote_host="203.0.113.7", now=11).error_code == "trusted_local_launch_requires_loopback"
    assert service.bind_session(_enrollment(credential), remote_host="127.0.0.1", now=21).error_code == "trusted_local_launch_expired"

    fresh = service.create_trusted_local_launch_credential(
        principal_ref="principal:player:1",
        allowed_actor_refs=("actor:a",),
        issued_at=10,
        expires_at=20,
    )
    assert service.bind_session(_enrollment(fresh), remote_host="::1", now=11).accepted is True
    assert service.bind_session(_enrollment(fresh), remote_host="::1", now=11).error_code == "trusted_local_launch_already_used"


def test_authenticated_session_stays_fail_closed_without_adapter() -> None:
    result = WebSocketSessionAuthService().bind_session(
        _enrollment("unconfigured", credential_kind="authenticated_session"),
        remote_host="127.0.0.1",
        now=10,
    )

    assert result.accepted is False
    assert result.error_code == "authenticated_session_adapter_unavailable"


def test_expired_launch_credentials_are_pruned_without_revoking_active_bindings() -> None:
    service = WebSocketSessionAuthService()
    old = service.create_trusted_local_launch_credential(
        principal_ref="principal:player:1", allowed_actor_refs=("actor:a",),
        issued_at=10, expires_at=20,
    )
    bound = service.bind_session(_enrollment(old), remote_host="127.0.0.1", now=11).binding
    assert bound is not None

    current = service.create_trusted_local_launch_credential(
        principal_ref="principal:player:1", allowed_actor_refs=("actor:b",),
        issued_at=21, expires_at=30,
    )

    assert old not in service._trusted_credentials
    assert service.resolve_binding(bound.session_ref) == bound
    assert service.bind_session(_enrollment(current), remote_host="127.0.0.1", now=21).accepted


def test_used_launch_credentials_release_large_scope_and_keep_bounded_replay_tombstones() -> None:
    service = WebSocketSessionAuthService()
    actor_scope = tuple(f"actor:{index}" for index in range(1000))
    credentials = []

    for timestamp in range(300):
        credential = service.create_trusted_local_launch_credential(
            principal_ref="principal:population-probe",
            allowed_actor_refs=actor_scope,
            issued_at=timestamp,
            expires_at=timestamp + 300,
        )
        assert service._trusted_credentials[credential].allowed_actor_refs is actor_scope
        result = service.bind_session(
            _enrollment(credential),
            remote_host="127.0.0.1",
            now=timestamp,
        )
        assert result.accepted
        credentials.append(credential)

    assert service._trusted_credentials == {}
    assert len(service._closed_trusted_credentials) == 256
    assert service.bind_session(
        _enrollment(credentials[-1]), remote_host="127.0.0.1", now=300,
    ).error_code == "trusted_local_launch_already_used"
    assert service.bind_session(
        _enrollment(credentials[0]), remote_host="127.0.0.1", now=300,
    ).error_code == "trusted_local_launch_unknown"


def test_closed_binding_diagnostics_are_bounded_to_recent_sessions() -> None:
    service = WebSocketSessionAuthService()
    session_refs = []
    for timestamp in range(260):
        credential = service.create_trusted_local_launch_credential(
            principal_ref="principal:player:1", allowed_actor_refs=("actor:a",),
            issued_at=timestamp, expires_at=timestamp + 10,
        )
        binding = service.bind_session(_enrollment(credential), remote_host="127.0.0.1", now=timestamp).binding
        assert binding is not None
        session_refs.append(binding.session_ref)
        assert service.disconnect_session(binding.session_ref, now=timestamp)

    assert len(service._closed_bindings) == 256
    assert service.lifecycle_record(session_refs[0]) is None
    assert service.lifecycle_record(session_refs[-1]).binding_state == "disconnected"
    assert not service._bindings
