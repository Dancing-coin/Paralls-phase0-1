import json
import subprocess
import sys

import pytest
from scripts.verification.population_godot_runner import child_environment


@pytest.mark.parametrize(('disconnect', 'owner_work_delay', 'provider_delay'),
    [(False, 0, 0), (True, 0, 0), (False, 1, 0), (True, 1, 0), (False, 0, 10)])
def test_ws_perception_wait_does_not_hold_owner_and_disconnect_preserves_prefix(tmp_path, disconnect, owner_work_delay, provider_delay):
    (tmp_path / 'roster.json').write_text(json.dumps({'actor_ids': ['char_a', 'char_b', 'char_c', *[f'resident_{i:05d}' for i in range(97)]]}))
    code = r'''
import asyncio, sys, time
from pathlib import Path
from contextlib import ExitStack
from threading import Event, get_ident
from unittest.mock import patch
from fastapi import WebSocketDisconnect
from scripts.verification.population_mixed_backend import configure
async def run():
    with ExitStack() as stack:
        main, _, _ = configure(Path(sys.argv[1]), stack, mode='one_x', provider_mode='local_probe')
        stack.enter_context(patch.object(main, 'start_population_runtime', lambda: None))
        started, release, provider_exited = Event(), Event(), Event()
        threads, messages, provider_returns, outcomes = [], [], [], []
        from app.services import cognition_wait
        original_wait = cognition_wait.finish_cognition_wait
        async def observe_completion(**kwargs):
            result = await original_wait(**kwargs)
            outcomes.append((result.status, result.reason))
            return result
        stack.enter_context(patch.object(cognition_wait, 'finish_cognition_wait', observe_completion))
        async with main.component_app.router.lifespan_context(main.component_app):
            try:
                def prepare():
                    gateway = main.character_agent_runtime._l2._gateway
                    original = gateway.complete_prepared_request
                    def complete(request):
                        threads.append(get_ident())
                        first = len(threads) == 1
                        started.set()
                        try:
                            assert release.wait(10)
                            if first:
                                time.sleep(float(sys.argv[4]))
                            result = original(request)
                            provider_returns.append(True)
                            return result
                        finally:
                            provider_exited.set()
                    stack.enter_context(patch.object(gateway, 'complete_prepared_request', complete))
                    return get_ident()
                owner = await asyncio.wrap_future(main.runtime_execution.submit(prepare))
                class Socket:
                    query_params = {}
                    client = None
                    received = False
                    async def accept(self): pass
                    async def send_json(self, message): messages.append(message)
                    async def receive_json(self):
                        if not self.received:
                            self.received = True
                            return {'message_type':'raw_fact_event', 'payload':{
                                'fact_family':'visual_fact', 'fact_type':'light_level_drop',
                                'room_id':'room_demo', 'scene_id':'scene_demo', 'zone_id':'zone_focus',
                                'producer_ts':int(time.time()*1000), 'source':{'system':'godot.raw_fact_emitter','actor_id':'char_a'},
                                'targets':{'environment_id':'env_lamp'}, 'observability':{'visual':True}, 'causation_id':'raw:10000', 'correlation_id':'raw:10000'}}
                        deadline = time.monotonic()+5
                        while not started.is_set() and time.monotonic() < deadline:
                            await asyncio.sleep(.02)
                        assert started.is_set(), messages
                        def healthy():
                            time.sleep(float(sys.argv[3]))
                            # 验证provider仍阻塞时owner已执行，不能等provider超时退出后假通过。
                            assert started.is_set() and not release.is_set() and not provider_exited.is_set()
                            return 'healthy'
                        assert await asyncio.wait_for(asyncio.wrap_future(main.runtime_execution.submit(healthy)), 5) == 'healthy'
                        if sys.argv[2] == 'True':
                            raise WebSocketDisconnect()
                        release.set()
                        async with asyncio.timeout(30):
                            while main._transient_cognition_tasks:
                                await asyncio.sleep(.02)
                        assert not main._transient_cognition_tasks
                        raise WebSocketDisconnect()
                await main.websocket_endpoint(Socket())
                assert threads and all(thread != owner for thread in threads)
                def check():
                    assert not main._transient_cognition_turns
                    assert not main.character_agent_runtime.pending_cognition_jobs()
                    return main.character_agent_runtime._session_store.list_events('char_a')
                before = await asyncio.wrap_future(main.runtime_execution.submit(check))
                assert before
                release.set()
                async with asyncio.timeout(10):
                    while not provider_exited.is_set():
                        await asyncio.sleep(.02)
                await asyncio.sleep(.1)
                assert len(provider_returns) == len(threads)
                assert not main._transient_cognition_tasks
                if sys.argv[2] == 'True':
                    assert await asyncio.wrap_future(main.runtime_execution.submit(check)) == before
                else:
                    assert outcomes and all(status == 'completed' for status, _reason in outcomes), outcomes
            finally:
                release.set()
asyncio.run(run())
'''
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path), str(disconnect), str(owner_work_delay), str(provider_delay)],
        env=child_environment(), capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('during_output', [False, True])
def test_bound_raw_wait_revocation_preserves_prefix_and_suppresses_execution(tmp_path, during_output):
    code = r'''
import asyncio, json, sys, time
from pathlib import Path
from contextlib import ExitStack
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import WebSocketDisconnect
from scripts.verification.population_mixed_backend import configure
async def run():
    folder=Path(sys.argv[1])
    folder.mkdir(exist_ok=True)
    (folder/'roster.json').write_text(json.dumps({'actor_ids':['char_a','char_b','char_c',*[f'resident_{i:05d}' for i in range(97)]]}))
    with ExitStack() as stack:
        main, _, _=configure(folder,stack,mode='one_x',provider_mode='local_probe')
        stack.enter_context(patch.object(main,'start_population_runtime',lambda:None))
        started,release=Event(),Event()
        messages=[]
        async with main.component_app.router.lifespan_context(main.component_app):
            async def owner(fn): return await asyncio.wrap_future(main.runtime_execution.submit(fn))
            def prepare():
                gateway=main.character_agent_runtime._l2._gateway
                original=gateway.complete_prepared_request
                def complete(request):
                    started.set()
                    assert release.wait(5)
                    return original(request)
                stack.enter_context(patch.object(gateway,'complete_prepared_request',complete))
                now=int(time.time())
                return main.websocket_session_auth_service.create_trusted_local_launch_credential(
                    principal_ref='player',allowed_actor_refs=('character:char_a',),issued_at=now,expires_at=now+60)
            credential=await owner(prepare)
            if sys.argv[2] == 'True':
                encode = main._as_character_agent_execution_envelopes
                # 传输允许任意多帧；复用真实完成结果构成受控的两帧 bundle。
                stack.enter_context(patch.object(main, '_as_character_agent_execution_envelopes', lambda commands: encode(commands)*2))
            class Socket:
                query_params={}
                client=SimpleNamespace(host='127.0.0.1')
                phase=0
                async def accept(self):pass
                async def send_json(self,m):
                    messages.append(m)
                    if sys.argv[2] == 'True' and m['message_type'] == 'character_agent_execution':
                        session=next(row['payload']['session_ref'] for row in messages if row['message_type']=='websocket_session_bound')
                        def revoke_during_send():
                            ref=main.gameplay_mirror_connection_registry.connection_ref_for(session_ref=session)
                            assert main._revoke_websocket_session_for_transport(session_ref=session,connection_ref=ref,reason_code='revoked',now=int(time.time()))
                        await owner(revoke_during_send)
                async def close(self,**kwargs):pass
                async def receive_json(self):
                    self.phase+=1
                    if self.phase==1:
                        return {'message_type':'websocket_session_bind','payload':{'credential_kind':'trusted_local_launch','credential':credential,'protocol_version':1}}
                    if self.phase==2:
                        return {'message_type':'raw_fact_event','payload':{'fact_family':'visual_fact','fact_type':'light_level_drop','room_id':'room_demo','scene_id':'scene_demo','zone_id':'zone_focus','producer_ts':int(time.time()*1000),'source':{'system':'godot.raw_fact_emitter','actor_id':'char_a'},'targets':{'environment_id':'env_lamp'},'observability':{'visual':True},'causation_id':'raw:revoke','correlation_id':'raw:revoke'}}
                    stop=time.monotonic()+5
                    while not started.is_set() and time.monotonic()<stop: await asyncio.sleep(.02)
                    assert started.is_set(), messages
                    if sys.argv[2] == 'True':
                        release.set()
                        stop=time.monotonic()+2
                        while main._transient_cognition_tasks and time.monotonic()<stop: await asyncio.sleep(.02)
                        assert not main._transient_cognition_tasks
                        assert len([m for m in messages if m['message_type']=='character_agent_execution']) == 1
                        raise WebSocketDisconnect()
                    binding=next(m['payload'] for m in messages if m['message_type']=='websocket_session_bound')
                    session=binding['session_ref']
                    def revoke():
                        ref=main.gameplay_mirror_connection_registry.connection_ref_for(session_ref=session)
                        before=len(main.character_agent_runtime._session_store.list_events('char_a'))
                        assert main._revoke_websocket_session_for_transport(session_ref=session,connection_ref=ref,reason_code='revoked',now=int(time.time()))
                        c=main._get_dialogue_coordinator()
                        pin = c._connections[ref]
                        # 已排队但尚未准备的旧绑定也必须在感知 prefix 前拒绝。
                        pending = main._prepare_transport_cognition(ref, 'ingest_character_perceived_event', '{}', pin)
                        assert pending.status == 'zero_write'
                        assert not main.character_agent_runtime.pending_cognition_jobs()
                        assert len(main.character_agent_runtime._session_store.list_events('char_a')) == before
                        return before,c._connection_current(ref,pin)
                    before,current=await owner(revoke)
                    await asyncio.sleep(.04)
                    marker=len(messages)
                    release.set()
                    async with asyncio.timeout(10):
                        while main._transient_cognition_tasks:
                            await asyncio.sleep(.02)
                    after=await owner(lambda:len(main.character_agent_runtime._session_store.list_events('char_a')))
                    assert after == before
                    assert not current
                    assert not any(m['message_type'] == 'character_agent_execution' for m in messages[marker:])
                    assert not main._transient_cognition_tasks
                    print(json.dumps({'connection_current_after_revoke':current,'events_before_release':before,'events_after_release':after,'revocation_sent':any(m['message_type']=='websocket_session_revoked' for m in messages),'outbound_after_revoke':[m['message_type'] for m in messages[marker:]],'tasks_pending':len(main._transient_cognition_tasks)}))
                    raise WebSocketDisconnect()
            try:await main.websocket_endpoint(Socket())
            finally:release.set()
asyncio.run(run())
'''
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path), str(during_output)], env=child_environment(), capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
