"""Dialogue cognition must retain existing ESM execution output."""
import json
from threading import Event, get_ident
from time import time

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.character_agent.runtime.cognition_continuation import CognitionAdvance
from app.models.character_agent_runtime import CharacterGoalCommand
from test_dialogue_completion_lifecycle import begin, complete, coordinator, event
from test_character_object_execution import vertical


def command(contract):
    return CharacterGoalCommand(actor_id='char_a', command_type='interact',
        ttl_ms=1500, causation_id=contract.causation_id, correlation_id=contract.correlation_id,
        producer_ts=contract.producer_ts,
        execution_payload={'execution_contract': contract.model_dump(mode='json')})


def test_dialogue_cognition_offers_original_contract_before_next_provider(tmp_path, monkeypatch):
    owner = coordinator()
    with vertical(tmp_path) as (execution, runtime, esm, source, world, sessions, clock, contract):
        monkeypatch.setattr(main, 'character_object_execution', execution)
        monkeypatch.setattr(owner, '_prepare_cognition',
            lambda *_: CognitionAdvance('completed', result=[command(contract)]))
        advance = begin(owner)
        messages = owner.drain_execution_messages(advance.job.ticket_id)
        assert len(messages) == 1 and messages[0]['message_type'] == 'character_agent_execution'
        assert messages[0]['payload']['idempotency_key'] == contract.idempotency_key
        assert messages[0]['payload']['target_refs'] == contract.target_refs
        assert owner.drain_execution_messages(advance.job.ticket_id) == []
        # Egress is not settlement. Only the existing execution owner commits.
        before = world.get_last_global_sequence()
        _, _, result, receipt = execution.execute(contract)
        assert receipt.committed and result.settlement_status == 'committed'
        assert world.get_last_global_sequence() > before
        after = world.get_last_global_sequence()
        assert execution.execute(contract)[3].transaction_id == receipt.transaction_id
        assert world.get_last_global_sequence() == after
        owner.cancel(advance.job.ticket_id, reason='cancelled')


@pytest.mark.parametrize('ending', ['cancel', 'disconnect', 'context_change', 'actor_unauthorized'])
def test_ended_or_stale_dialogue_does_not_drain_execution(tmp_path, monkeypatch, ending):
    owner = coordinator()
    with vertical(tmp_path) as (execution, runtime, esm, source, world, sessions, clock, contract):
        monkeypatch.setattr(main, 'character_object_execution', execution)
        monkeypatch.setattr(owner, '_prepare_cognition',
            lambda *_: CognitionAdvance('completed', result=[command(contract)]))
        if ending == 'actor_unauthorized':
            from app.services.websocket_session_auth_service import WebSocketSessionEnrollment
            now = int(time())
            credential = owner.auth.create_trusted_local_launch_credential(principal_ref='p1',
                allowed_actor_refs=('char_c',), issued_at=now, expires_at=now + 60)
            binding = owner.auth.bind_session(WebSocketSessionEnrollment(credential_kind='trusted_local_launch',
                credential=credential, protocol_version=1), remote_host='127.0.0.1', now=now).binding
            owner.bind('connection:test', binding)
        advance = begin(owner)
        ticket = advance.job.ticket_id
        if ending == 'cancel':
            owner.cancel(ticket, reason='cancelled')
        elif ending == 'disconnect':
            owner.disconnect('connection:test')
        elif ending == 'context_change':
            owner.runtime.set_background_mode('char_a', 'active')
        assert owner.drain_execution_messages(ticket) == []
        assert not owner.runtime.pending_actor_activations()


def test_speech_cognition_is_not_echoed_as_second_execution(monkeypatch):
    owner = coordinator()
    speech = CharacterGoalCommand(actor_id='char_a', command_type='speak', ttl_ms=1500,
        causation_id='speech', correlation_id='speech', producer_ts=90210,
        dialogue_text='direct speech')
    monkeypatch.setattr(owner, '_prepare_cognition',
        lambda *_: CognitionAdvance('completed', result=[speech]))
    advance = begin(owner)
    assert owner.drain_execution_messages(advance.job.ticket_id) == []
    while advance.status == 'pending':
        advance, _ = complete(owner, advance)
    assert json.loads(advance.messages_json)[0]['payload']['content'] == 'direct speech'


def test_websocket_dispatch_before_blocked_dialogue_then_original_owner_receipt(tmp_path, monkeypatch):
    from app.character_agent.execution.object_execution import CharacterObjectExecution

    main.reset_runtime_state()
    with TestClient(main.component_app, client=('127.0.0.1', 47112)) as client:
        with vertical(tmp_path) as (sample_execution, sample_runtime, esm, source, world, sessions, clock, contract):
            runtime = main.character_agent_runtime
            main.runtime_execution.submit(lambda: runtime._l1._snapshots.update(
                char_a=sample_runtime._l1._snapshots['char_a'])).result(2)
            execution = CharacterObjectExecution(runtime=runtime, owner=esm, source=source,
                scopes=sample_execution._scopes.values(), clock_ms=lambda: clock[0])
            main.runtime_execution.submit(lambda: runtime._session_store.append_event('char_a',
                'character_agent_execution_request', 10, contract.model_dump(mode='json'))).result(2)
            monkeypatch.setattr(main, 'character_object_execution', execution)
            owner = main.runtime_execution.submit(main._get_dialogue_coordinator).result(2)
            monkeypatch.setattr(owner, '_prepare_cognition',
                lambda *_: CognitionAdvance('completed', result=[command(contract)]))
            started, release = Event(), Event()
            gateway = main.character_service.dialogue._gateway
            original_stream = gateway.stream_prepared_request
            def stream(request_json, *, cancelled):
                started.set()
                assert release.wait(5)
                yield from original_stream(request_json, cancelled=cancelled)
            monkeypatch.setattr(gateway, 'stream_prepared_request', stream)
            owner_thread = main.runtime_execution.submit(get_ident).result(2)
            mutations = []
            original_execute = execution.execute
            def execute(received):
                mutations.append(get_ident())
                return original_execute(received)
            monkeypatch.setattr(execution, 'execute', execute)
            with client.websocket_connect('/ws') as websocket:
                try:
                    now = int(time())
                    credential = main.runtime_execution.submit(lambda:
                        owner.auth.create_trusted_local_launch_credential(principal_ref='p1',
                            allowed_actor_refs=('char_a', 'char_c'), issued_at=now, expires_at=now + 60)).result(2)
                    websocket.send_json({'message_type': 'websocket_session_bind', 'payload': {
                        'credential_kind': 'trusted_local_launch', 'credential': credential, 'protocol_version': 1}})
                    assert websocket.receive_json()['payload']['accepted']
                    assert websocket.receive_json()['payload']['session_ref']
                    request = event().model_copy(update={'room_id': 'r', 'scene_id': 's', 'zone_id': 'z'})
                    websocket.send_json({'message_type': 'player_input', 'payload': request.model_dump()})
                    acknowledgement = websocket.receive_json()
                    assert acknowledgement['payload']['accepted'], acknowledgement
                    assert websocket.receive_json()['message_type'] == 'dialogue_stream_start'
                    outbound = websocket.receive_json()
                    assert outbound['message_type'] == 'character_agent_execution', outbound
                    assert outbound['payload'] == contract.model_dump(mode='json')
                    assert started.wait(2)
                    before = world.get_last_global_sequence()
                    websocket.send_json(outbound)
                    receipt = websocket.receive_json()
                    assert receipt['message_type'] == 'ack' and receipt['payload']['accepted'], receipt
                    transaction_id = receipt['payload']['owner_receipt']['transaction_id']
                    assert world.get_transaction(transaction_id) is not None
                    assert world.get_last_global_sequence() > before
                    assert mutations == [owner_thread]
                finally:
                    release.set()
