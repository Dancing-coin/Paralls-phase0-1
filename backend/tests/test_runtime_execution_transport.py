import asyncio
from threading import get_ident
from unittest.mock import patch

import pytest

from app.gameplay.godot_mirror_delivery import GameplayMirrorConnectionError, GameplayMirrorTransportSink
from app.services.runtime_execution import RuntimeExecution


def test_owner_posts_frozen_initial_snapshot_then_update_on_original_loop():
    async def check():
        execution = RuntimeExecution()
        loop_thread = get_ident()
        delivered = []

        def receive(kind, payload):
            assert get_ident() == loop_thread
            delivered.append((kind, payload))

        sink = GameplayMirrorTransportSink(deliver=receive, capacity=4)
        source = {"actor_ref": "actor:a", "groups": {"state": [1]}}

        def owner():
            assert get_ident() != loop_thread
            sink.post_initial_snapshot({"message_type": "ack", "payload": {"accepted": True}}, source)
            source["groups"]["state"].append(2)
            sink.post_snapshot(source)

        try:
            # owner 不依赖 loop 消费，不会因它此刻未调度而阻塞。
            execution.submit(owner).result(timeout=1)
            assert delivered == []
            assert sink.pending_count == 2
            await asyncio.sleep(0)
            assert [kind for kind, _ in delivered] == ["initial_snapshot", "snapshot"]
            assert delivered[0][1]["projection"]["groups"]["state"] == [1]
            assert delivered[1][1]["groups"]["state"] == [1, 2]
            assert sink.pending_count == 0
        finally:
            await asyncio.to_thread(execution.stop)

    asyncio.run(check(), debug=True)


def test_sink_overflow_is_bounded_terminal_and_does_not_block_another_connection():
    async def check():
        execution = RuntimeExecution()
        loop = asyncio.get_running_loop()
        slow, fast = [], []
        blocked = GameplayMirrorTransportSink(deliver=lambda kind, data: slow.append((kind, data)), capacity=2)
        healthy = GameplayMirrorTransportSink(deliver=lambda kind, data: fast.append((kind, data)), capacity=2)

        def owner():
            for i in range(2):
                blocked.post_snapshot({"actor_ref": "actor:a", "index": i})
            with pytest.raises(GameplayMirrorConnectionError, match="mirror_backpressure"):
                blocked.post_snapshot({"actor_ref": "actor:a", "index": 3})
            for _ in range(100):
                blocked.close("revoked")
            healthy.post_snapshot({"actor_ref": "actor:b"})

        try:
            with patch.object(loop, "call_soon_threadsafe", wraps=loop.call_soon_threadsafe) as schedule:
                execution.submit(owner).result(timeout=1)
                assert schedule.call_count == 2
                assert blocked.pending_count == 0
            await asyncio.sleep(0)
            assert slow == [("close", {"reason_code": "mirror_backpressure"})]
            assert fast == [("snapshot", {"actor_ref": "actor:b"})]
            with pytest.raises(GameplayMirrorConnectionError, match="mirror_connection_unavailable"):
                blocked.post_snapshot({"actor_ref": "actor:a"})
        finally:
            await asyncio.to_thread(execution.stop)

    asyncio.run(check(), debug=True)


def test_drop_actor_clears_old_handoff_but_preserves_other_actor_and_resubscription():
    async def check():
        delivered = []
        sink = GameplayMirrorTransportSink(deliver=lambda kind, data: delivered.append((kind, data)), capacity=4)
        sink.post_snapshot({"actor_ref": "actor:a", "index": 1})
        sink.post_snapshot({"actor_ref": "actor:b", "index": 1})
        sink.drop_actor("actor:a")
        sink.post_initial_snapshot({"message_type": "ack"}, {"actor_ref": "actor:a", "index": 2})
        await asyncio.sleep(0)
        assert delivered == [
            ("drop_actor", {"actor_ref": "actor:a"}),
            ("snapshot", {"actor_ref": "actor:b", "index": 1}),
            ("initial_snapshot", {"ack": {"message_type": "ack"}, "projection": {"actor_ref": "actor:a", "index": 2}}),
        ]

    asyncio.run(check(), debug=True)


def test_sink_rejects_non_json_and_bounds_pending_drop_controls():
    async def check():
        delivered = []
        sink = GameplayMirrorTransportSink(deliver=lambda kind, data: delivered.append((kind, data)), capacity=2)
        with pytest.raises(ValueError):
            sink.post_snapshot({"actor_ref": "actor:a", "number": float("nan")})
        assert sink.pending_count == 0
        sink.drop_actor("actor:a")
        sink.drop_actor("actor:b")
        sink.drop_actor("actor:c")
        await asyncio.sleep(0)
        assert delivered == [("close", {"reason_code": "mirror_backpressure"})]

    asyncio.run(check(), debug=True)


def test_loop_delivery_failure_discards_later_data_and_delivers_terminal_once():
    async def check():
        calls = []

        def deliver(kind, payload):
            calls.append((kind, payload))
            if kind == "advisory":
                raise GameplayMirrorConnectionError("mirror_backpressure")

        sink = GameplayMirrorTransportSink(deliver=deliver, capacity=3)
        sink.post_advisory({"jurisdiction_ref": "room:a"})
        sink.post_prediction({"actor_ref": "actor:a", "resolutions": []})
        await asyncio.sleep(0)
        assert calls == [
            ("advisory", {"jurisdiction_ref": "room:a"}),
            ("close", {"reason_code": "mirror_delivery_unrecoverable"}),
        ]
        assert sink.closed and sink.pending_count == 0

    asyncio.run(check(), debug=True)


def test_owner_traffic_cannot_keep_one_drain_running_forever():
    async def check():
        delivered = []

        def deliver(kind, payload):
            delivered.append(payload["index"])
            if payload["index"] < 6:
                sink.post_snapshot({"actor_ref": "actor:a", "index": payload["index"] + 1})

        sink = GameplayMirrorTransportSink(deliver=deliver, capacity=2)
        sink.post_snapshot({"actor_ref": "actor:a", "index": 1})
        await asyncio.sleep(0)
        assert delivered == [1, 2]
        await asyncio.sleep(0)
        assert delivered == [1, 2, 3, 4]
        sink.close("test_finished")

    asyncio.run(check(), debug=True)


def test_initial_batch_is_bounded_and_never_coalesced():
    from app.gameplay.godot_mirror_delivery import GameplayMirrorOutboundQueue
    queue = GameplayMirrorOutboundQueue(projection_capacity=1, control_capacity=1, dirty_actor_limit=1)
    initial = {'message_type': 'gameplay_mirror_delivery', 'payload': {'actor_ref': 'actor:a'}}
    queue.enqueue_initial_batch({'message_type': 'ack'}, initial)
    with pytest.raises(GameplayMirrorConnectionError, match='mirror_backpressure'):
        queue.enqueue_initial_batch({'message_type': 'ack'}, initial)
    queue.enqueue_delivery({'message_type': 'gameplay_mirror_delivery', 'payload': {'actor_ref': 'actor:a', 'revision': 2}})
    assert queue.pop_next()['_initial_batch'] == [{'message_type': 'ack'}, initial]


def test_production_business_envelope_runs_on_owner(monkeypatch):
    from app import main
    from fastapi import WebSocketDisconnect

    async def check():
        main.reset_runtime_state()
        execution = RuntimeExecution(on_stop=main.close_runtime_resources)
        monkeypatch.setattr(main, 'runtime_execution', execution)
        loop_thread = get_ident()
        calls = []
        monkeypatch.setattr(main, '_handle_envelope', lambda envelope, **kwargs: calls.append(get_ident()) or [])

        class WebSocket:
            query_params = {}
            client = None
            received = False
            async def accept(self):
                pass
            async def send_json(self, message):
                assert get_ident() == loop_thread
            async def receive_json(self):
                if self.received:
                    raise WebSocketDisconnect()
                self.received = True
                return {'message_type': 'object_interaction', 'payload': {}}
        try:
            await main.websocket_endpoint(WebSocket())
            assert len(calls) == 1
            assert calls[0] != loop_thread
        finally:
            await asyncio.to_thread(execution.stop)
            monkeypatch.setattr(main, 'runtime_execution', None)
    asyncio.run(check(), debug=True)


def test_live_probe_http_commit_runs_on_owner(monkeypatch):
    from app import main
    from fastapi.testclient import TestClient
    main.reset_runtime_state()
    execution = RuntimeExecution(on_stop=main.close_runtime_resources)
    monkeypatch.setattr(main, 'runtime_execution', execution)
    owner_thread = execution.submit(get_ident).result(2)
    calls = []
    monkeypatch.setattr(main, '_require_trusted_local_gameplay_mirror_live_probe', lambda **kwargs: None)
    monkeypatch.setattr(main, '_commit_configured_trusted_local_gameplay_mirror_live_probe',
                        lambda **kwargs: calls.append(get_ident()) or {'actor_ref': 'actor:a'})
    try:
        response = TestClient(main.component_app).post('/internal/trusted-local-gameplay-mirror-live-probe-commit', json={})
        assert response.status_code == 200
        assert calls == [owner_thread]
    finally:
        execution.stop()
        monkeypatch.setattr(main, 'runtime_execution', None)


@pytest.mark.parametrize('finish', ['unsubscribe', 'renewal', 'revoke', 'popped_unsubscribe', 'popped_revoke', 'families', 'overflow', 'initial_unsubscribe', 'sending_revoke', 'shutdown', 'receipt_burst', 'popped_expiry', 'expired_advisory', 'expired_prediction', 'initial_expiry'])
def test_production_mirror_registry_receipt_and_ws_stay_on_loop(monkeypatch, finish):
    from types import SimpleNamespace
    from time import time
    from app import main
    from app.ws_protocol import GameplayMirrorCapabilityOffer
    from test_websocket_session_renewal_lifecycle import _godot_view
    from fastapi import WebSocketDisconnect

    async def check():
        main.reset_runtime_state()
        execution = RuntimeExecution(on_stop=main.close_runtime_resources)
        monkeypatch.setattr(main, 'runtime_execution', execution)
        monkeypatch.setattr(main, 'settings', main.settings.model_copy(update={'gameplay_mirror_live_probe_drop_first_delivery': True, 'gameplay_mirror_projection_queue_capacity': 160 if finish == 'receipt_burst' else 2}))
        loop_thread = get_ident()
        owner_thread = await asyncio.wrap_future(execution.submit(get_ident))
        calls = []
        registry = main.gameplay_mirror_connection_registry
        for method in ('register', 'unregister', 'deliver', 'acknowledge', 'connection_ref_for', 'deliver_government_drought_advisory', 'deliver_prediction_resolutions', 'mark_sent'):
            original = getattr(registry, method)
            def observed(*args, _method=method, _original=original, **kwargs):
                assert get_ident() == loop_thread, _method
                calls.append(_method)
                return _original(*args, **kwargs)
            monkeypatch.setattr(registry, method, observed)
        hold_started, hold_release, popped = asyncio.Event(), asyncio.Event(), asyncio.Event()
        saved_context = []
        original_handler = main._handle_envelope
        def handle(*args, **kwargs):
            assert get_ident() == owner_thread
            if args[0].message_type == 'transport_hold':
                return [{'message_type':'ack', 'payload':{'hold':True}}]
            saved_context[:] = [kwargs['connection_context']]
            return original_handler(*args, **kwargs)
        original_pop = main.GameplayMirrorOutboundQueue.pop_next
        def pop(queue):
            assert get_ident() == loop_thread
            item = original_pop(queue)
            if item and item.get('payload', {}).get('delivery_sequence') == 4:
                popped.set()
            return item
        monkeypatch.setattr(main.GameplayMirrorOutboundQueue, 'pop_next', pop)
        monkeypatch.setattr(main, '_handle_envelope', handle)

        def setup():
            credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
                principal_ref='principal:test', allowed_actor_refs=('actor:visible',),
                allowed_government_drought_advisory_jurisdiction_refs=('jurisdiction:a',),
                issued_at=int(time())-1, expires_at=int(time())+60)
            def source():
                assert get_ident() == owner_thread
                return _godot_view('actor:visible')
            main.gameplay_godot_projection_publisher.register_actor_source(actor_ref='actor:visible', source=source)
            return credential
        credential = await asyncio.wrap_future(execution.submit(setup))
        incoming, outgoing = asyncio.Queue(), asyncio.Queue()
        class WebSocket:
            query_params = {}
            client = SimpleNamespace(host='127.0.0.1')
            def __init__(self, input_queue=None, output_queue=None):
                self.input_queue = incoming if input_queue is None else input_queue
                self.output_queue = outgoing if output_queue is None else output_queue
            async def accept(self):
                assert get_ident() == loop_thread
            async def send_json(self, message):
                assert get_ident() == loop_thread
                if self.output_queue is outgoing and message['message_type'] in {'gameplay_mirror_delivery', 'government_drought_advisory_delivery'}:
                    payload = message['payload']
                    with pytest.raises(main.GameplayMirrorDeliveryError, match='mirror_receipt_unknown|mirror_receipt_out_of_window'):
                        registry.acknowledge(session_ref=session_ref, receipt=main.GameplayMirrorReceipt(
                            connection_epoch=payload['connection_epoch'], delivery_sequence=payload['delivery_sequence']))
                if (finish == 'sending_revoke' and message.get('payload', {}).get('delivery_sequence') == 4) or message.get('payload', {}).get('hold') or (finish in {'initial_unsubscribe', 'initial_expiry'} and message.get('payload', {}).get('source_type') == 'gameplay_mirror_subscribe'):
                    hold_started.set()
                    await hold_release.wait()
                self.output_queue.put_nowait(message)
            async def close(self, **kwargs):
                assert get_ident() == loop_thread
            async def receive_json(self):
                message = await self.input_queue.get()
                if message is None:
                    raise WebSocketDisconnect()
                return message
        task = asyncio.create_task(main.websocket_endpoint(WebSocket()))
        async def receive():
            return await asyncio.wait_for(outgoing.get(), 2)
        def send(kind, payload):
            incoming.put_nowait({'message_type': kind, 'payload': payload})
        try:
            send('websocket_session_bind', {'credential_kind':'trusted_local_launch', 'credential':credential,
                 'protocol_version': 2, 'capability_offer': GameplayMirrorCapabilityOffer(protocol_version=2, supports_snapshot=True, supports_receipt=True, projection_schemas=("gameplay_runtime_state.godot.v1",)).model_dump()})
            ack, bound = await receive(), await receive()
            assert ack['payload']['accepted'], ack
            assert bound['message_type'] == 'websocket_session_bound'
            session_ref = bound['payload']['session_ref']
            send('gameplay_mirror_subscribe', {'actor_ref':'actor:visible'})
            if finish in {'initial_unsubscribe', 'initial_expiry'}:
                await asyncio.wait_for(hold_started.wait(), 2)
                if finish == 'initial_expiry':
                    monkeypatch.setattr(main, 'time', lambda: bound['payload']['lease_expires_at'])
                else:
                    context = saved_context[0]
                    result = await asyncio.wrap_future(execution.submit(lambda: main._dialogue_connection_envelope(
                        '{"message_type":"gameplay_mirror_unsubscribe","payload":{"actor_ref":"actor:visible"}}', context)))
                    assert result[0][0]['payload']['subscription_removed']
                hold_release.set()
                assert (await receive())['payload']['accepted']
                if finish == 'initial_expiry':
                    revoked = await receive()
                    assert revoked['message_type'] == 'websocket_session_revoked'
                    assert revoked['payload']['reason_code'] == 'websocket_session_lease_expired'
                    send('websocket_session_revocation_received', revoked['payload'])
                    assert await asyncio.wrap_future(execution.submit(lambda: main.gameplay_mirror_subscription_registry.subscribed_session_refs(actor_ref='actor:visible'))) == ()
                await asyncio.wrap_future(execution.submit(lambda: None))
                await asyncio.sleep(0)
                assert outgoing.empty()
                incoming.put_nowait(None)
                await asyncio.wait_for(task, 2)
                return
            ack, initial = await receive(), await receive()
            assert ack['payload']['accepted']
            assert initial['message_type'] == 'gameplay_mirror_delivery', initial
            assert initial['payload']['delivery_sequence'] == 1
            async def update_twice():
                def update():
                    projection = main.gameplay_mirror_subscription_registry.after_commit_snapshots(affected_actor_refs=('actor:visible',))[0].payload
                    main._post_mirror_snapshot(session_ref, projection)
                    main._post_mirror_snapshot(session_ref, projection)
                await asyncio.wrap_future(execution.submit(update))
            await update_twice()
            update = await receive()
            assert update['payload']['delivery_sequence'] == 3  # 只丢首份 after-commit，不丢 initial。
            send('gameplay_mirror_receipt', {'connection_epoch': update['payload']['connection_epoch'], 'delivery_sequence':3})
            assert (await receive())['payload']['accepted']
            assert 'acknowledge' in calls
            if finish == 'receipt_burst':
                def burst():
                    projection = main.gameplay_mirror_subscription_registry.after_commit_snapshots(affected_actor_refs=('actor:visible',))[0].payload
                    for _ in range(160):
                        main._post_mirror_snapshot(session_ref, projection)
                execution.submit(burst).result(2)
                batch = [await receive() for _ in range(160)]
                assert [item['payload']['delivery_sequence'] for item in batch] == list(range(4, 164))
                # 直到整个无阻塞wire批次完成后，才在下一loop轮提交全部ACK。
                for item in batch:
                    send('gameplay_mirror_receipt', {key:item['payload'][key] for key in ('connection_epoch', 'delivery_sequence')})
                assert all([(await receive())['payload']['accepted'] for _ in batch])
                send('gameplay_mirror_receipt', {'connection_epoch':update['payload']['connection_epoch'], 'delivery_sequence':2})
                assert not (await receive())['payload']['accepted']  # 实际被drop的update。
            elif finish == 'shutdown':
                def fill_handoff():
                    projection = main.gameplay_mirror_subscription_registry.after_commit_snapshots(affected_actor_refs=('actor:visible',))[0].payload
                    sink = main._mirror_sink_for(session_ref)
                    sink.post_snapshot(projection)
                    sink.post_snapshot(projection)
                    assert sink.pending_count == 2
                execution.submit(fill_handoff).result(2)
                await main._stop_population_runtime_on_shutdown()
                assert not main._mirror_transport_routes
                assert registry.connection_ref_for(session_ref=session_ref) is None
                revoked = await receive()
                assert revoked['message_type'] == 'websocket_session_revoked'
                send('websocket_session_revocation_received', revoked['payload'])
                incoming.put_nowait(None)
                await asyncio.wait_for(task, 2)
                assert outgoing.empty()
                return
            elif finish == 'sending_revoke':
                def post_waiting():
                    projection = main.gameplay_mirror_subscription_registry.after_commit_snapshots(affected_actor_refs=('actor:visible',))[0].payload
                    main._post_mirror_snapshot(session_ref, projection)
                await asyncio.wrap_future(execution.submit(post_waiting))
                await asyncio.wait_for(hold_started.wait(), 2)
                connection_ref = registry.connection_ref_for(session_ref=session_ref)
                assert await asyncio.wrap_future(execution.submit(lambda: main._revoke_websocket_session_for_transport(
                    session_ref=session_ref, connection_ref=connection_ref, reason_code='test_revoked', now=int(time()))))
                revoked = await receive()
                assert revoked['message_type'] == 'websocket_session_revoked'
                assert not hold_release.is_set()  # blocked send 已由 mirror task cancel 释放锁。
                send('websocket_session_revocation_received', revoked['payload'])
            elif finish == 'overflow':
                fast_in, fast_out = asyncio.Queue(), asyncio.Queue()
                fast_task = asyncio.create_task(main.websocket_endpoint(WebSocket(fast_in, fast_out)))
                async def fast_receive():
                    return await asyncio.wait_for(fast_out.get(), 2)
                try:
                    second_credential = await asyncio.wrap_future(execution.submit(lambda:
                        main.websocket_session_auth_service.create_trusted_local_launch_credential(
                            principal_ref='principal:fast', allowed_actor_refs=('actor:visible',),
                            issued_at=int(time())-1, expires_at=int(time())+60)))
                    fast_in.put_nowait({'message_type':'websocket_session_bind', 'payload':{
                        'credential_kind':'trusted_local_launch', 'credential':second_credential, 'protocol_version':1}})
                    assert (await fast_receive())['payload']['accepted']
                    fast_session = (await fast_receive())['payload']['session_ref']
                    fast_in.put_nowait({'message_type':'gameplay_mirror_subscribe', 'payload':{'actor_ref':'actor:visible'}})
                    assert (await fast_receive())['payload']['accepted']
                    assert (await fast_receive())['payload']['delivery_sequence'] == 1
                    send('transport_hold', {})
                    await asyncio.wait_for(hold_started.wait(), 2)
                    def overflow():
                        projection = main.gameplay_mirror_subscription_registry.after_commit_snapshots(affected_actor_refs=('actor:visible',))[0].payload
                        sink = main._mirror_sink_for(session_ref)
                        sink.post_snapshot(projection)
                        sink.post_snapshot(projection)
                        with pytest.raises(GameplayMirrorConnectionError, match='mirror_backpressure'):
                            sink.post_snapshot(projection)
                        assert sink.pending_count == 0
                        main._post_mirror_snapshot(fast_session, projection)
                        main._post_mirror_snapshot(fast_session, projection)
                        return 'owner_remains_live'
                    # 保持 loop 暂不 drain，确定性填满 handoff；owner 不等待 sender 或 loop。
                    assert execution.submit(overflow).result(2) == 'owner_remains_live'
                    assert (await fast_receive())['payload']['delivery_sequence'] == 3
                    hold_release.set()
                    assert (await receive())['payload']['hold']
                    revoked = await receive()
                    assert revoked['message_type'] == 'websocket_session_revoked'
                    send('websocket_session_revocation_received', revoked['payload'])
                finally:
                    fast_in.put_nowait(None)
                    await asyncio.wait_for(fast_task, 2)
            elif finish in {'expired_advisory', 'expired_prediction'}:
                monkeypatch.setattr(main, 'time', lambda: bound['payload']['lease_expires_at'])
                def expired_post():
                    if finish == 'expired_advisory':
                        main._post_mirror_advisory(session_ref, {'projection_kind':'government_drought_advisory.project.v1',
                            'jurisdiction_ref':'jurisdiction:a', 'advisory_refs':['advisory:a'],
                            'source_revision_vector':{'government:a':1}, 'projection_hash':'sha256:a'})
                    else:
                        main._deliver_trusted_local_gameplay_mirror_prediction_resolutions(actor_ref='actor:visible',
                            resolutions=(main.GameplayMirrorPredictionResolution(prediction_id='p:a', command_id='c:a',
                                resolution='rejected', error_code='stale_revision'),))
                await asyncio.wrap_future(execution.submit(expired_post))
                revoked = await receive()
                assert revoked['message_type'] == 'websocket_session_revoked'
                assert revoked['payload']['reason_code'] == 'websocket_session_lease_expired'
                send('websocket_session_revocation_received', revoked['payload'])
                assert registry.connection_ref_for(session_ref=session_ref) is None
                assert outgoing.empty()
            elif finish == 'families':
                advisory = {'projection_kind':'government_drought_advisory.project.v1',
                            'jurisdiction_ref':'jurisdiction:a', 'advisory_refs':['advisory:a'],
                            'source_revision_vector':{'government:a':1}, 'projection_hash':'sha256:a'}
                def snapshot(**kwargs):
                    assert get_ident() == owner_thread
                    return advisory
                monkeypatch.setattr(main.government_drought_advisory_presentation_service, '_snapshot', snapshot)
                send('gameplay_government_drought_advisory_subscribe', {'jurisdiction_ref':'jurisdiction:a'})
                ack, first_advisory = await receive(), await receive()
                assert ack['payload']['accepted']
                assert first_advisory['message_type'] == 'government_drought_advisory_delivery'
                assert first_advisory['payload']['delivery_sequence'] == 4
                def post_other_families():
                    main._post_mirror_advisory(session_ref, advisory)
                    main._deliver_trusted_local_gameplay_mirror_prediction_resolutions(actor_ref='actor:visible',
                        resolutions=(main.GameplayMirrorPredictionResolution(prediction_id='p:a', command_id='c:a',
                            resolution='rejected', error_code='stale_revision'),))
                await asyncio.wrap_future(execution.submit(post_other_families))
                advisory_update, prediction = await receive(), await receive()
                assert advisory_update['payload']['delivery_sequence'] == 5
                assert prediction['payload']['delivery_sequence'] == 6
                assert prediction['payload']['delivery_kind'] == 'prediction'
                assert prediction['payload']['prediction_resolutions'][0]['error_code'] == 'stale_revision'
            elif finish.startswith('popped_'):
                send('transport_hold', {})
                await asyncio.wait_for(hold_started.wait(), 2)
                def post_waiting():
                    projection = main.gameplay_mirror_subscription_registry.after_commit_snapshots(affected_actor_refs=('actor:visible',))[0].payload
                    main._post_mirror_snapshot(session_ref, projection)
                await asyncio.wrap_future(execution.submit(post_waiting))
                await asyncio.wait_for(popped.wait(), 2)
                if finish == 'popped_expiry':
                    monkeypatch.setattr(main, 'time', lambda: bound['payload']['lease_expires_at'])
                elif finish == 'popped_unsubscribe':
                    context = saved_context[0]
                    result = await asyncio.wrap_future(execution.submit(lambda: main._dialogue_connection_envelope(
                        '{"message_type":"gameplay_mirror_unsubscribe","payload":{"actor_ref":"actor:visible"}}', context)))
                    assert result[0][0]['payload']['subscription_removed']
                else:
                    connection_ref = registry.connection_ref_for(session_ref=session_ref)
                    assert await asyncio.wrap_future(execution.submit(lambda: main._revoke_websocket_session_for_transport(
                        session_ref=session_ref, connection_ref=connection_ref, reason_code='test_revoked', now=int(time()))))
                hold_release.set()
                assert (await receive())['payload']['hold']
                if finish in {'popped_revoke', 'popped_expiry'}:
                    revoked = await receive()
                    assert revoked['message_type'] == 'websocket_session_revoked'
                    send('websocket_session_revocation_received', revoked['payload'])
                # 最后一次 owner roundtrip + loop turn 使已 pop sender 有确定的重验机会。
                await asyncio.wrap_future(execution.submit(lambda: None))
                await asyncio.sleep(0)
                assert outgoing.empty()
            elif finish == 'unsubscribe':
                send('gameplay_mirror_unsubscribe', {'actor_ref':'actor:visible'})
                assert (await receive())['payload']['subscription_removed']
            elif finish == 'renewal':
                old_sink = await asyncio.wrap_future(execution.submit(lambda: main._mirror_sink_for(session_ref)))
                old_context = saved_context[0]
                send('websocket_session_renewal', {'protocol_version':2})
                assert (await receive())['payload']['accepted']
                replacement = await receive()
                assert replacement['message_type'] == 'websocket_session_renewal_enrollment'
                send('gameplay_mirror_receipt', {'connection_epoch':update['payload']['connection_epoch'], 'delivery_sequence':3})
                assert not (await receive())['payload']['accepted']
                send('websocket_session_bind', replacement['payload'])
                assert (await receive())['payload']['accepted']
                rebound = await receive()
                assert rebound['payload']['connection_epoch'] > update['payload']['connection_epoch']
                session_ref = rebound['payload']['session_ref']
                send('gameplay_mirror_subscribe', {'actor_ref':'actor:visible'})
                assert (await receive())['payload']['accepted']
                fresh = await receive()
                assert fresh['payload']['delivery_sequence'] == 1
                assert await asyncio.wrap_future(execution.submit(lambda: main._mirror_send_lease(old_context, old_sink))) is None
                old_sink._deliver('snapshot', initial['payload']['payload'])
                await asyncio.wrap_future(execution.submit(lambda: main._drop_mirror_transport_session(old_context, old_context.binding.session_ref)))
                assert registry.connection_ref_for(session_ref=session_ref) is not None
                assert outgoing.empty()
            else:
                connection_ref = registry.connection_ref_for(session_ref=session_ref)
                import httpx
                monkeypatch.setattr(main, '_require_trusted_local_gameplay_mirror_live_probe', lambda **kwargs: None)
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.component_app), base_url='http://test') as client:
                    response = await client.post('/internal/trusted-local-gameplay-mirror-live-probe-controlled-close',
                                                 json={'session_ref':session_ref})
                    assert response.status_code == 200, response.text
                    assert registry.connection_ref_for(session_ref=session_ref) is None
                revoked = await receive()
                assert revoked['message_type'] == 'websocket_session_revoked'
                send('websocket_session_revocation_received', revoked['payload'])
            incoming.put_nowait(None)
            await asyncio.wait_for(task, 2)
            assert registry.connection_ref_for(session_ref=session_ref) is None
            assert await asyncio.wrap_future(execution.submit(lambda: len(main._mirror_transport_routes))) == 0
            assert await asyncio.wrap_future(execution.submit(lambda: main.gameplay_mirror_subscription_registry.subscribed_session_refs(actor_ref='actor:visible'))) == ()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await asyncio.to_thread(execution.stop)
            monkeypatch.setattr(main, 'runtime_execution', None)
    asyncio.run(check(), debug=True)





def test_initial_snapshot_is_posted_before_owner_command_returns(monkeypatch):
    from app import main
    from types import SimpleNamespace
    from app.services.websocket_session_auth_service import WebSocketConnectionContext
    async def check():
        execution = RuntimeExecution()
        monkeypatch.setattr(main, 'runtime_execution', execution)
        delivered = []
        sink = GameplayMirrorTransportSink(deliver=lambda kind, data: delivered.append((kind, data)), capacity=2)
        context = WebSocketConnectionContext(remote_host='', observed_at=0, connection_ref='connection:cut')
        context.binding = SimpleNamespace(session_ref='session:cut')
        ack = {'message_type':'ack', 'payload':{'accepted':True}}
        projection = {'actor_ref':'actor:a', 'message_type':'gameplay_runtime_state_projection'}
        monkeypatch.setattr(main, '_handle_websocket_envelope', lambda *args: [ack, projection])
        monkeypatch.setattr(main, '_get_dialogue_coordinator', lambda: None)
        try:
            def owner():
                main._install_mirror_route('session:cut', 'connection:cut', sink)
                result = main._dialogue_connection_envelope('{"message_type":"gameplay_mirror_subscribe","payload":{"actor_ref":"actor:a"}}', context)
                assert result[0] == []
                assert sink.pending_count == 1
                sink.post_snapshot({'actor_ref':'actor:a', 'revision':2})
                main._mirror_transport_routes.pop('session:cut')
            execution.submit(owner).result(2)
            await asyncio.sleep(0)
            assert [kind for kind, _ in delivered] == ['initial_snapshot', 'snapshot']
        finally:
            await asyncio.to_thread(execution.stop)
            monkeypatch.setattr(main, 'runtime_execution', None)
    asyncio.run(check(), debug=True)


def test_dirty_recovery_never_exceeds_projection_capacity():
    from app.gameplay.godot_mirror_delivery import GameplayMirrorOutboundQueue
    queue = GameplayMirrorOutboundQueue(projection_capacity=1, control_capacity=1, dirty_actor_limit=1)
    def item(actor):
        return {'message_type':'gameplay_mirror_delivery', 'payload':{'actor_ref':actor}}
    queue.enqueue_delivery(item('actor:a'))
    queue.enqueue_delivery(item('actor:b'))
    queue.pop_next()  # 为 B 安排 resync；新数据可占刚腾出的槽。
    queue.enqueue_delivery(item('actor:c'))
    recovered = [queue.pop_next()]
    assert len(queue._projections) <= 1
    recovered.extend([queue.pop_next(), queue.pop_next()])
    assert [item['message_type'] for item in recovered].count('gameplay_mirror_resync_required') == 1
    assert {item['payload']['actor_ref'] for item in recovered} == {'actor:b', 'actor:c'}


def test_prediction_control_cannot_be_coalesced_on_full_queue():
    from app.gameplay.godot_mirror_delivery import GameplayMirrorOutboundQueue
    queue = GameplayMirrorOutboundQueue(projection_capacity=1, control_capacity=1, dirty_actor_limit=1)
    queue.enqueue_delivery({'message_type':'gameplay_mirror_delivery', 'payload':{'actor_ref':'actor:a', 'delivery_kind':'snapshot'}})
    with pytest.raises(GameplayMirrorConnectionError, match='mirror_backpressure'):
        queue.enqueue_delivery({'message_type':'gameplay_mirror_delivery', 'payload':{'actor_ref':'actor:a', 'delivery_kind':'prediction'}})


def test_failed_initial_handoff_removes_new_scope_and_view(monkeypatch):
    from app import main
    from app.services.websocket_session_auth_service import WebSocketConnectionContext
    from app.ws_protocol import Envelope
    from time import time
    from test_websocket_session_renewal_lifecycle import _godot_view
    async def check():
        main.reset_runtime_state()
        execution = RuntimeExecution(on_stop=main.close_runtime_resources)
        monkeypatch.setattr(main, 'runtime_execution', execution)
        delivered = []
        sink = GameplayMirrorTransportSink(deliver=lambda kind, data: delivered.append((kind, data)), capacity=1)
        def owner():
            credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
                principal_ref='principal:test', allowed_actor_refs=('actor:visible',), issued_at=int(time())-1, expires_at=int(time())+60)
            context = WebSocketConnectionContext(remote_host='127.0.0.1', observed_at=int(time()), connection_ref='connection:failed')
            main._handle_envelope(Envelope(message_type='websocket_session_bind', payload={
                'credential_kind':'trusted_local_launch', 'credential':credential, 'protocol_version':1}), connection_context=context)
            main.gameplay_godot_projection_publisher.register_actor_source(actor_ref='actor:visible', source=lambda: _godot_view('actor:visible'))
            main._install_mirror_route(context.binding.session_ref, context.connection_ref, sink)
            sink.post_snapshot({'actor_ref':'actor:visible'})
            result, _ = main._dialogue_connection_envelope(
                '{"message_type":"gameplay_mirror_subscribe","payload":{"actor_ref":"actor:visible"}}', context)
            assert result[0]['payload']['accepted'] is False
            assert result[0]['payload']['error_code'] == 'mirror_backpressure'
            assert main.gameplay_mirror_subscription_registry.subscribed_session_refs(actor_ref='actor:visible') == ()
            assert context.binding.session_ref not in main._mirror_transport_routes
            with pytest.raises(main.GameplayMirrorDeliveryError, match='mirror_projection_unavailable'):
                main.gameplay_godot_projection_repository.view_for('actor:visible')
        try:
            execution.submit(owner).result(2)
            await asyncio.sleep(0)
            assert delivered == [('close', {'reason_code':'mirror_backpressure'})]
        finally:
            await asyncio.to_thread(execution.stop)
            monkeypatch.setattr(main, 'runtime_execution', None)
    asyncio.run(check(), debug=True)


def test_full_owner_queue_waits_without_stopping_and_real_stop_cleans_routes(monkeypatch):
    from app import main
    from threading import Event
    async def check():
        main.reset_runtime_state()
        execution = RuntimeExecution(max_pending=1, on_stop=main.close_runtime_resources)
        monkeypatch.setattr(main, 'runtime_execution', execution)
        closed, started, release = asyncio.Event(), Event(), Event()
        sink = GameplayMirrorTransportSink(deliver=lambda kind, data: closed.set() if kind == 'close' else None, capacity=1)
        await asyncio.wrap_future(execution.submit(lambda: main._install_mirror_route('session:full', 'connection:full', sink)))
        execution.submit(lambda: (started.set(), release.wait(3)))
        assert started.wait(1)
        execution.submit(lambda: None)
        try:
            pending = asyncio.create_task(main._dialogue_owner_call(execution, lambda: 'continued'))
            # 超过旧错误停服期限；loop 仍能继续，正常背压不关闭原路由。
            await asyncio.sleep(.5)
            assert not pending.done()
            assert execution.snapshot()['state'] == 'running'
            assert not sink.closed and main._mirror_transport_routes
            release.set()
            assert await asyncio.wait_for(pending, 2) == 'continued'
            assert not sink.closed and main._mirror_transport_routes
            assert await asyncio.to_thread(execution.stop)
            await asyncio.wait_for(asyncio.wrap_future(execution.closed), 2)
            await asyncio.wait_for(closed.wait(), 1)
            assert not main._mirror_transport_routes
            assert sink.closed
        finally:
            release.set()
            await asyncio.to_thread(execution.stop)
            monkeypatch.setattr(main, 'runtime_execution', None)
    asyncio.run(check(), debug=True)


def test_default_limits_accept_160_initial_actor_batch_and_count_both_buffers():
    from app.config import Settings
    from app.gameplay.godot_mirror_delivery import GameplayMirrorOutboundQueue
    async def check():
        settings = Settings()
        assert settings.gameplay_mirror_projection_queue_capacity == 160
        queue = GameplayMirrorOutboundQueue(projection_capacity=160, control_capacity=8, dirty_actor_limit=16)
        def deliver(kind, data):
            assert kind == 'initial_snapshot'
            queue.enqueue_initial_batch(data['ack'], {'message_type':'gameplay_mirror_delivery', 'payload':data['projection']})
        sink = GameplayMirrorTransportSink(deliver=deliver, capacity=160)
        for index in range(160):
            sink.post_initial_snapshot({'message_type':'ack'}, {'actor_ref':f'actor:{index}'})
        assert sink.pending_count + queue.pending_count == 160
        await asyncio.sleep(0)
        assert sink.pending_count == 0 and queue.pending_count == 160
        delivered = [queue.pop_next()['_initial_batch'][1]['payload']['actor_ref'] for _ in range(160)]
        assert delivered == [f'actor:{index}' for index in range(160)]
        assert sink.pending_count + queue.pending_count == 0
    asyncio.run(check(), debug=True)


def test_raw_fact_fast_ack_and_followup_both_run_on_owner(monkeypatch):
    from app import main
    from fastapi import WebSocketDisconnect
    async def check():
        main.reset_runtime_state()
        execution = RuntimeExecution(on_stop=main.close_runtime_resources)
        monkeypatch.setattr(main, 'runtime_execution', execution)
        owner_thread = await asyncio.wrap_future(execution.submit(get_ident))
        sent = asyncio.Event()
        calls = []
        ack = {'message_type':'ack', 'payload':{'accepted':True}}
        def fast(envelope):
            calls.append(('fast', get_ident()))
            return ack
        def followup(envelope, **kwargs):
            calls.append(('followup', get_ident()))
            return [{'message_type':'raw_fact_done', 'payload':{}}]
        monkeypatch.setattr(main, '_raw_fact_fast_authority_ack', fast)
        monkeypatch.setattr(main, '_handle_raw_fact_followup', followup)
        class WebSocket:
            query_params = {}
            client = None
            received = False
            async def accept(self):
                pass
            async def send_json(self, message):
                if message['message_type'] == 'raw_fact_done':
                    sent.set()
            async def receive_json(self):
                if self.received:
                    await asyncio.wait_for(sent.wait(), 2)
                    raise WebSocketDisconnect()
                self.received = True
                return {'message_type':'raw_fact_event', 'payload':{}}
        try:
            await main.websocket_endpoint(WebSocket())
            assert calls == [('fast', owner_thread), ('followup', owner_thread)]
        finally:
            await asyncio.to_thread(execution.stop)
            monkeypatch.setattr(main, 'runtime_execution', None)
    asyncio.run(check(), debug=True)


def test_raw_fact_followup_disconnect_does_not_send_a_second_error(monkeypatch):
    from app import main
    from fastapi import WebSocketDisconnect

    async def check():
        main.reset_runtime_state()
        execution = RuntimeExecution(on_stop=main.close_runtime_resources)
        monkeypatch.setattr(main, 'runtime_execution', execution)
        sent = []
        followup_send_started = asyncio.Event()
        debug_events = []
        ack = {'message_type':'ack', 'payload':{'accepted':True}}
        monkeypatch.setattr(main, '_raw_fact_fast_authority_ack', lambda envelope: ack)
        monkeypatch.setattr(main, '_handle_raw_fact_followup',
                            lambda envelope, **kwargs: [{'message_type':'raw_fact_done', 'payload':{}}])
        monkeypatch.setattr(main, '_publish_debug_event', debug_events.append)

        class WebSocket:
            query_params = {}
            client = None
            received = False

            async def accept(self):
                pass

            async def send_json(self, message):
                sent.append(message['message_type'])
                if message['message_type'] != 'ack':
                    followup_send_started.set()
                    raise WebSocketDisconnect()

            async def receive_json(self):
                if not self.received:
                    self.received = True
                    return {'message_type':'raw_fact_event', 'payload':{}}
                await asyncio.wait_for(followup_send_started.wait(), 2)
                raise WebSocketDisconnect()

        try:
            await main.websocket_endpoint(WebSocket())
            await asyncio.sleep(0)
            assert sent == ['ack', 'raw_fact_done']
            assert debug_events == []
        finally:
            await asyncio.to_thread(execution.stop)
            monkeypatch.setattr(main, 'runtime_execution', None)

    asyncio.run(check(), debug=True)


def test_production_registry_allocated_is_not_sent_and_160_late_acks_remain_valid():
    from app.gameplay.godot_mirror_delivery import GameplayMirrorConnectionRegistry, GameplayMirrorOutboundQueue, GameplayMirrorDeliveryError
    from app.ws_protocol import GameplayMirrorReceipt, GameplayMirrorPredictionResolution
    async def check():
        registry = GameplayMirrorConnectionRegistry()
        queue = GameplayMirrorOutboundQueue(projection_capacity=160, control_capacity=8, dirty_actor_limit=16)
        window = 160 * 2 + 8 + 16 + 1
        registry.register(session_ref='session:burst', connection_ref='connection:burst', connection_epoch=2,
                          deliver=lambda delivery: queue.enqueue_initial_batch({'message_type':'ack'}, delivery),
                          defer_receipts=True, receipt_window=window)
        def ack(sequence, epoch=2):
            return registry.acknowledge(session_ref='session:burst', receipt=GameplayMirrorReceipt(connection_epoch=epoch, delivery_sequence=sequence))
        for index in range(160):
            registry.deliver('session:burst', {'actor_ref':f'actor:{index}', 'projection_kind':'gameplay_runtime_state.godot.v1', 'facade_revision':'r:1'})
        for sequence in (1, 160):
            with pytest.raises(GameplayMirrorDeliveryError, match='mirror_receipt_unknown'):
                ack(sequence)
        sent = []
        async def send(message):
            sent.append(message['payload']['delivery_sequence'])  # 模拟正常不阻塞、不让出loop的socket send。
        async def sender():
            while (message := queue.pop_next()) is not None:
                await send(message)
                payload = message['payload']
                registry.mark_sent(session_ref='session:burst', connection_ref='connection:burst',
                                   connection_epoch=2, delivery_sequence=payload['delivery_sequence'])
        async def receiver():
            await asyncio.sleep(0)
            assert sent == list(range(1, 161))
            assert all(ack(sequence) for sequence in sent)
        await asyncio.gather(sender(), receiver())
        registry.deliver_government_drought_advisory('session:burst', {
            'projection_kind':'government_drought_advisory.project.v1', 'jurisdiction_ref':'j:a',
            'advisory_refs':['a:a'], 'source_revision_vector':{'g:a':1}, 'projection_hash':'h:a'})
        registry.deliver_prediction_resolutions(session_ref='session:burst', actor_ref='actor:0', facade_revision='r:1',
            resolutions=(GameplayMirrorPredictionResolution(prediction_id='p:a', command_id='c:a', resolution='rejected', error_code='stale'),))
        with pytest.raises(GameplayMirrorDeliveryError, match='mirror_receipt_unknown'):
            ack(161)
        await sender()
        assert ack(1) and ack(161) and ack(162)
        with pytest.raises(GameplayMirrorDeliveryError, match='mirror_receipt_stale_epoch'):
            ack(1, epoch=1)
        with pytest.raises(GameplayMirrorDeliveryError, match='mirror_receipt_unknown'):
            ack(99999)
        for index in range(window):
            registry.deliver('session:burst', {'actor_ref':'actor:a', 'projection_kind':'gameplay_runtime_state.godot.v1', 'facade_revision':'r:2'})
            await sender()
        ledger = registry._connections['session:burst'].receipt_ledger
        assert len(ledger._sent_sequences) == window
        with pytest.raises(GameplayMirrorDeliveryError, match='mirror_receipt_out_of_window'):
            ack(1)
    asyncio.run(check(), debug=True)


def test_production_receipts_exclude_dropped_items_and_track_real_send_order():
    from app.gameplay.godot_mirror_delivery import GameplayMirrorConnectionRegistry, GameplayMirrorDeliveryError
    from app.ws_protocol import GameplayMirrorReceipt
    registry = GameplayMirrorConnectionRegistry()
    queued = []
    registry.register(session_ref='s', connection_ref='c', connection_epoch=1, deliver=queued.append,
                      defer_receipts=True, receipt_window=3)
    for index in range(5):
        registry.deliver('s', {'actor_ref':f'actor:{index}', 'projection_kind':'gameplay_runtime_state.godot.v1', 'facade_revision':'r:1'})
    for sequence in (1, 4, 2):
        assert registry.mark_sent(session_ref='s', connection_ref='c', connection_epoch=1, delivery_sequence=sequence)
        assert registry.acknowledge(session_ref='s', receipt=GameplayMirrorReceipt(connection_epoch=1, delivery_sequence=sequence))
    for sequence in (3, 5):  # 已分配但被合并/drop/fence挡住，不能产生receipt资格。
        with pytest.raises(GameplayMirrorDeliveryError, match='mirror_receipt_unknown'):
            registry.acknowledge(session_ref='s', receipt=GameplayMirrorReceipt(connection_epoch=1, delivery_sequence=sequence))
    assert not registry.mark_sent(session_ref='s', connection_ref='old', connection_epoch=1, delivery_sequence=5)
    assert not registry.mark_sent(session_ref='s', connection_ref='c', connection_epoch=2, delivery_sequence=5)
    assert len(registry._connections['s'].receipt_ledger._sent_sequences) == 3
