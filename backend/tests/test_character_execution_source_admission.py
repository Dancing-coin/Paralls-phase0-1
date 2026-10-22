"""Frozen session execution is the source, never an ingress assertion."""

import pytest

from app.character_agent.models.character_execution import CharacterExecutionContract
from app.character_agent.storage.session_store import CharacterAgentSessionStore
from app.services.character_agent_runtime import CharacterAgentRuntime


def _contract(**changes):
    return CharacterExecutionContract.model_validate({
        "turn_id": "turn:char_b:1", "actor_ref": "character:char_b",
        "source_ref": "percept:1", "producer_ts": 10,
        "target_refs": ["object:obj_plaque"],
        "semantic_intent_id": "inspect_object", "semantic_action_id": "inspect",
        "expected_revision_vector": {"session:char_b": 1},
        "idempotency_key": "execution:char_b:1", "causation_id": "cause:1",
        "correlation_id": "corr:1", "privacy_scope": "actor_private:char_b",
        "authority_scope": "world:default", **changes,
    })


@pytest.mark.parametrize("nested", [False, True])
def test_original_session_contract_remains_verifiable_after_reopen(tmp_path, nested):
    path = tmp_path / "session.sqlite3"
    store = CharacterAgentSessionStore(database_path=path)
    payload = _contract().model_dump(mode="json")
    if nested:
        payload = {"turn_id": "turn:char_b:1", "execution_contract": payload}
    event = store.append_event("char_b", "character_agent_execution_request", 10, payload)
    store.close()
    runtime = CharacterAgentRuntime(session_store=CharacterAgentSessionStore(database_path=path))
    try:
        assert runtime.verify_recorded_execution_contract(_contract()) == event["event_id"]
    finally:
        runtime.close()


@pytest.mark.parametrize("changes", [
    {"target_refs": ["object:obj_worktable"]}, {"semantic_action_id": "use"},
    {"producer_ts": 11}, {"expected_revision_vector": {"session:char_b": 2}},
    {"expected_observation": {"owner_route": "esm"}},
    {"source_ref": "percept:other"}, {"turn_id": "turn:char_b:other"},
])
def test_changed_contract_is_rejected_without_new_session_event(changes):
    store = CharacterAgentSessionStore()
    store.append_event("char_b", "character_agent_execution_request", 10, _contract().model_dump(mode="json"))
    runtime = CharacterAgentRuntime(session_store=store)
    try:
        with pytest.raises(ValueError, match="execution_source_mismatch"):
            runtime.verify_recorded_execution_contract(_contract(**changes))
        assert store.event_count("char_b") == 1
    finally:
        runtime.close()


def test_other_actor_event_does_not_authorize_execution():
    store = CharacterAgentSessionStore()
    store.append_event("char_a", "character_agent_execution_request", 10, _contract().model_dump(mode="json"))
    runtime = CharacterAgentRuntime(session_store=store)
    try:
        with pytest.raises(ValueError, match="execution_source_missing"):
            runtime.verify_recorded_execution_contract(_contract())
    finally:
        runtime.close()


def test_unrecorded_contract_is_rejected_at_production_ingress():
    import app.main as main

    main.reset_runtime_state()
    before = main.character_agent_runtime.get_session_timeline("char_b")
    messages = main._handle_envelope(main.Envelope(
        message_type="character_agent_execution", payload=_contract().model_dump(mode="json"),
    ))
    assert len(messages) == 1
    assert messages[0]["payload"]["accepted"] is False
    assert messages[0]["payload"]["error_message"] == "execution_source_missing"
    assert main.character_agent_runtime.get_session_timeline("char_b") == before


def test_changed_contract_is_rejected_at_production_ingress():
    import app.main as main

    main.reset_runtime_state()
    main.character_agent_runtime.record_execution_request(
        actor_id="char_b", producer_ts=10, payload=_contract().model_dump(mode="json"),
    )
    before = main.character_agent_runtime.get_session_timeline("char_b")
    messages = main._handle_envelope(main.Envelope(
        message_type="character_agent_execution",
        payload=_contract(semantic_action_id="use").model_dump(mode="json"),
    ))
    assert len(messages) == 1
    assert messages[0]["payload"]["accepted"] is False
    assert messages[0]["payload"]["error_message"] == "execution_source_mismatch"
    assert main.character_agent_runtime.get_session_timeline("char_b") == before


def test_websocket_execution_requires_current_session_actor_scope():
    import app.main as main
    from app.services.websocket_session_auth_service import WebSocketConnectionContext

    main.reset_runtime_state()
    main.character_agent_runtime.record_execution_request(
        actor_id="char_b", producer_ts=10, payload=_contract().model_dump(mode="json"),
    )
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player:1",
        allowed_actor_refs=("character:char_a",),
        issued_at=10,
        expires_at=20,
    )
    context = WebSocketConnectionContext(
        remote_host="127.0.0.1", observed_at=10, connection_ref="ws:actor-scope",
    )
    main._handle_envelope(main.Envelope(
        message_type="websocket_session_bind",
        payload={"credential_kind": "trusted_local_launch", "credential": credential, "protocol_version": 1},
    ), connection_context=context)

    messages = main._handle_envelope(main.Envelope(
        message_type="character_agent_execution", payload=_contract().model_dump(mode="json"),
    ), connection_context=context)

    assert messages[0]["payload"]["accepted"] is False
    assert messages[0]["payload"]["error_message"] == "execution_actor_scope_denied"


def test_unbound_websocket_cannot_submit_recorded_execution():
    import app.main as main
    from app.services.websocket_session_auth_service import WebSocketConnectionContext

    main.reset_runtime_state()
    main.character_agent_runtime.record_execution_request(
        actor_id="char_b", producer_ts=10, payload=_contract().model_dump(mode="json"),
    )
    context = WebSocketConnectionContext(
        remote_host="127.0.0.1", observed_at=10, connection_ref="ws:unbound",
    )

    messages = main._handle_envelope(main.Envelope(
        message_type="character_agent_execution", payload=_contract().model_dump(mode="json"),
    ), connection_context=context)

    assert messages[0]["payload"]["accepted"] is False
    assert messages[0]["payload"]["error_message"] == "execution_session_required"


def test_revoked_websocket_binding_cannot_submit_recorded_execution():
    import app.main as main
    from app.services.websocket_session_auth_service import WebSocketConnectionContext

    main.reset_runtime_state()
    main.character_agent_runtime.record_execution_request(
        actor_id="char_b", producer_ts=10, payload=_contract().model_dump(mode="json"),
    )
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player:1",
        allowed_actor_refs=("character:char_b",),
        issued_at=10,
        expires_at=20,
    )
    context = WebSocketConnectionContext(
        remote_host="127.0.0.1", observed_at=10, connection_ref="ws:revoked",
    )
    main._handle_envelope(main.Envelope(
        message_type="websocket_session_bind",
        payload={"credential_kind": "trusted_local_launch", "credential": credential, "protocol_version": 1},
    ), connection_context=context)
    main.websocket_session_auth_service.revoke_session(
        context.binding.session_ref, reason_code="test_revocation", now=11,
    )
    context.observed_at = 11

    messages = main._handle_envelope(main.Envelope(
        message_type="character_agent_execution", payload=_contract().model_dump(mode="json"),
    ), connection_context=context)

    assert messages[0]["payload"]["accepted"] is False
    assert messages[0]["payload"]["error_message"] == "execution_session_stale"


def test_authorized_websocket_actor_passes_transport_admission():
    import app.main as main
    from app.services.websocket_session_auth_service import WebSocketConnectionContext

    main.reset_runtime_state()
    main.character_agent_runtime.record_execution_request(
        actor_id="char_b", producer_ts=10, payload=_contract().model_dump(mode="json"),
    )
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player:1",
        allowed_actor_refs=("character:char_b",),
        issued_at=10,
        expires_at=20,
    )
    context = WebSocketConnectionContext(
        remote_host="127.0.0.1", observed_at=10, connection_ref="ws:authorized",
    )
    main._handle_envelope(main.Envelope(
        message_type="websocket_session_bind",
        payload={"credential_kind": "trusted_local_launch", "credential": credential, "protocol_version": 1},
    ), connection_context=context)

    messages = main._handle_envelope(main.Envelope(
        message_type="character_agent_execution", payload=_contract().model_dump(mode="json"),
    ), connection_context=context)

    assert messages[0]["payload"].get("error_message") != "execution_actor_scope_denied"
    assert messages[0]["payload"].get("error_message") != "execution_session_required"
    assert messages[0]["payload"].get("error_message") != "execution_session_stale"


def test_conflicting_recorded_duplicate_does_not_authorize_original():
    store = CharacterAgentSessionStore()
    for contract in (_contract(), _contract(semantic_action_id="use")):
        store.append_event("char_b", "character_agent_execution_request", 10, contract.model_dump(mode="json"))
    runtime = CharacterAgentRuntime(session_store=store)
    try:
        with pytest.raises(ValueError, match="execution_source_mismatch"):
            runtime.verify_recorded_execution_contract(_contract())
    finally:
        runtime.close()
