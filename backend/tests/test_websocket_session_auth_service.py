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
