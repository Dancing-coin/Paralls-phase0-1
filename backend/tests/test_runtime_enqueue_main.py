import json
from pathlib import Path
import subprocess
import sys
import pytest
from scripts.verification.population_godot_runner import child_environment


@pytest.mark.parametrize('mode', ['batch', 'batch_revoke', 'batch_expiry', 'batch_cancel', 'five', 'duplicate', 'capacity', 'revoked', 'raw', 'barrier', 'wrong_actor', 'disconnected', 'full_disconnect'])
def test_same_socket_accepts_five_actual_owner_commands_before_blocked_owner_finishes(tmp_path, mode):
    (tmp_path/'roster.json').write_text(json.dumps({'actor_ids':['char_a','char_b','char_c',*[f'resident_{i:05d}' for i in range(97)]]}))
    code = r'''
import asyncio,sys,time
from pathlib import Path
from contextlib import ExitStack
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import WebSocketDisconnect
from scripts.verification.population_mixed_backend import configure
async def run():
    with ExitStack() as stack:
        main,_,_=configure(Path(sys.argv[1]),stack,mode='one_x',provider_mode='local_probe')
        stack.enter_context(patch.object(main,'start_population_runtime',lambda:None))
        async with main.component_app.router.lifespan_context(main.component_app):
            async def owner(fn):return await asyncio.wrap_future(main.runtime_execution.submit(fn))
            credential=await owner(lambda:main.websocket_session_auth_service.create_trusted_local_launch_credential(principal_ref='player',allowed_actor_refs=('character:char_a',),issued_at=int(time.time()),expires_at=int(time.time())+60))
            entered,release=Event(),Event()
            mode=sys.argv[2]
            offered=130 if mode in {'capacity','full_disconnect'} else 5
            accepted=[];rejected=[];completed=[];original=[];processed=[];snapshots=[];terminals=[]
            authorization_checks=[]
            original_owner_call=main._dialogue_owner_call
            async def measured_owner_call(execution,command,*args,**kwargs):
                if '_connection_current' in command.__code__.co_names or command.__name__=='authorize_completed':
                    authorization_checks.append(True)
                return await original_owner_call(execution,command,*args,**kwargs)
            stack.enter_context(patch.object(main,'_dialogue_owner_call',measured_owner_call))
            original_handle=main._dialogue_connection_envelope
            def handle(command,context):
                if 'character_actor_status' in command or 'raw_fact_event' in command:processed.append(command)
                return original_handle(command,context)
            stack.enter_context(patch.object(main,'_dialogue_connection_envelope',handle))
            class Socket:
                query_params={};client=SimpleNamespace(host='127.0.0.1')
                index=0
                async def accept(self):pass
                async def close(self,**kwargs):pass
                async def finish_runtime_request(self,request_id,request_sequence):terminals.append(request_id)
                async def send_json(self,message):
                    if message['message_type']=='runtime_admission':
                        assert not release.is_set()
                        (accepted if message['payload']['accepted'] else rejected).append(message['payload']['request_id'])
                        if len(accepted)+len(rejected)==offered and mode not in {'disconnected','full_disconnect'}:release.set()
                    elif message['message_type']=='runtime_completion':
                        completed.append(message['payload']['request_id'])
                        original.extend(row for row in message['payload']['messages'] if row['message_type']=='ack' and row['payload'].get('source_type') in {'character_actor_status','raw_fact_event'})
                        snapshots.extend(row['payload'] for row in message['payload']['messages'] if row['message_type']=='spatial_access_runtime_state_snapshot')
                        if len(completed)==1 and mode=='batch_cancel':raise asyncio.CancelledError()
                        if len(completed)==1 and mode in {'batch_revoke','batch_expiry'}:
                            ref=next(iter(main._get_dialogue_coordinator()._connections))
                            pin=main._get_dialogue_coordinator()._connections[ref]
                            if mode=='batch_revoke':
                                await owner(lambda:main._revoke_websocket_session_for_transport(session_ref=pin[0],connection_ref=ref,reason_code='test-revoke',now=int(time.time())))
                            else:
                                stack.enter_context(patch.object(main,'time',lambda:pin[2]+1))
                            await asyncio.sleep(.02)
                    elif message['message_type']=='ack' and message['payload'].get('source_type')=='character_actor_status':
                        assert mode=='barrier' and completed==accepted
                        original.append(message)
                async def receive_json(self):
                    self.index+=1
                    if self.index==1:return {'message_type':'websocket_session_bind','payload':{'credential_kind':'trusted_local_launch','credential':credential,'protocol_version':1}}
                    if self.index==2:
                        def block():
                            entered.set();assert release.wait(3),'reader blocked admission behind owner'
                            if mode=='revoked':
                                ref=next(iter(main._get_dialogue_coordinator()._connections))
                                main._get_dialogue_coordinator().disconnect(ref)
                        main.runtime_execution.submit(block)
                        while not entered.is_set():await asyncio.sleep(.02)
                    if self.index<=offered+1 and mode in {'raw','disconnected','full_disconnect'}:return {'message_type':'runtime_enqueue','payload':{'request_id':str(self.index-2),'command':{'message_type':'raw_fact_event','payload':{'event_type':'raw_fact_event','fact_family':'spatial_access_fact','fact_type':'actor_entered_zone','producer_ts':100+self.index-2,'room_id':'room_demo','scene_id':'scene_demo','zone_id':'zone_focus','source':{'system':'godot.raw_fact_emitter','actor_id':'char_a'},'targets':{}}}}}
                    if self.index<=offered+1:return {'message_type':'runtime_enqueue','payload':{'request_id':'same' if mode=='duplicate' else str(self.index-2),'command':{'message_type':'character_actor_status','payload':{'actor_id':'char_b' if mode=='wrong_actor' else 'char_a'}}}}
                    if mode in {'disconnected','full_disconnect'}:
                        asyncio.get_running_loop().call_later(1.,release.set)
                        raise WebSocketDisconnect()
                    if mode=='barrier' and self.index==offered+2:return {'message_type':'character_actor_status','payload':{'actor_id':'char_a'}}
                    deadline=time.monotonic()+4
                    while len(terminals)<len(accepted) and time.monotonic()<deadline:await asyncio.sleep(.02)
                    raise WebSocketDisconnect()
            try:await main.websocket_endpoint(Socket())
            finally:release.set()
            if mode=='batch':assert len(authorization_checks)<=2,authorization_checks
            if mode=='raw':assert [row['updated_at'] for row in snapshots]==list(range(100,105)),snapshots
            if mode=='five':assert accepted==[str(i) for i in range(5)] and not rejected,accepted
            if mode=='duplicate':assert accepted==['same'] and len(rejected)==4
            if mode=='capacity':assert 1<=len(accepted)<=128 and rejected
            if mode in {'batch_revoke','batch_expiry','batch_cancel'}:
                assert completed==['0'],completed
                assert terminals==accepted,terminals
                assert len(processed)==5,processed
            elif mode in {'revoked','disconnected','full_disconnect'}:
                assert not completed and not original and not processed,(mode,len(processed))
                assert main.runtime_execution.snapshot()['state']=='running',main.runtime_execution.snapshot()
            else:
                assert completed==accepted,completed
                if mode=='wrong_actor':
                    assert not processed and len(original)==5
                    assert all(row['payload']['accepted'] is False for row in original)
                else:assert len(original)==len(accepted)+(mode=='barrier')==len(processed)
asyncio.run(run())
'''
    result=subprocess.run([sys.executable,'-c',code,str(tmp_path),mode],cwd=Path(__file__).resolve().parents[2],env=child_environment(),capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr

def test_completion_batch_cancellation_releases_taken_prefix_carry_and_queue():
    """直接运行原嵌套泵，控制取消发生在批次授权等待中。"""
    import ast
    import asyncio
    from concurrent.futures import Future
    from types import SimpleNamespace
    source = ast.parse((Path(__file__).parents[1] / 'app/main.py').read_text(encoding='utf-8'))
    endpoint = next(node for node in source.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'websocket_endpoint')
    functions = [node for node in endpoint.body if isinstance(node, ast.AsyncFunctionDef)
                 and node.name in {'finish_admitted', 'complete_admitted_commands'}]
    async def run():
        from app import main
        from app.services.runtime_execution import RuntimeExecution
        from threading import Event
        queue, entered = asyncio.Queue(), asyncio.Event()
        started, release = Event(), Event()
        execution = RuntimeExecution()
        execution.submit(lambda: (started.set(), release.wait(3)))
        assert started.wait(1)
        first, carry, queued = Future(), Future(), Future()
        first.set_result(([], ()))
        futures = dict(first=first, carry=carry, queued=queued)
        terminals = []
        for key, future in futures.items():
            queue.put_nowait((key, future, SimpleNamespace(binding=None, connection_ref='original'), key))
        async def owner(_execution, _command):
            entered.set()
            return await main._dialogue_owner_call(_execution, _command)
        async def finish(key, sequence):
            assert key == sequence
            terminals.append(key)
        namespace = dict(asyncio=asyncio, admitted_commands=queue, admitted_futures=futures,
            websocket=SimpleNamespace(finish_runtime_request=finish), execution=execution,
            coordinator=SimpleNamespace(_binding_pin=lambda _: (), _connection_current=lambda ref,pin: True), _dialogue_owner_call=owner)
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<original-completion-pump>', 'exec'), namespace)
        task = asyncio.create_task(namespace['complete_admitted_commands']())
        await asyncio.wait_for(entered.wait(), 1)
        assert queue.qsize() == 1 and set(futures) == {'first', 'carry', 'queued'}
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.wait_for(queue.join(), 1)
        assert terminals == ['first', 'carry', 'queued']
        assert not futures and carry.cancelled() and queued.cancelled()
        release.set()
        try:
            assert await asyncio.wrap_future(execution.submit(lambda: 'healthy')) == 'healthy'
            assert execution.snapshot()['state'] == 'running'
        finally:
            await asyncio.to_thread(execution.stop)
    asyncio.run(run())

def test_cancelled_future_inside_completed_prefix_keeps_original_cancellation():
    import ast
    import asyncio
    from concurrent.futures import Future
    from types import SimpleNamespace
    source = ast.parse((Path(__file__).parents[1] / 'app/main.py').read_text(encoding='utf-8'))
    endpoint = next(node for node in source.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'websocket_endpoint')
    functions = [node for node in endpoint.body if isinstance(node, ast.AsyncFunctionDef)
                 and node.name in {'finish_admitted', 'complete_admitted_commands'}]
    async def run():
        queue, futures, terminals, sent = asyncio.Queue(), {}, [], []
        for i in range(3):
            future = Future()
            future.cancel() if i == 1 else future.set_result(([], ()))
            futures[str(i)] = future
            queue.put_nowait((str(i), future, SimpleNamespace(binding=None, connection_ref='original'), str(i)))
        async def owner(_execution, command): return command()
        async def finish(key, _sequence): terminals.append(key)
        async def send(message, *, request_sequence): sent.append(request_sequence)
        namespace = dict(asyncio=asyncio, admitted_commands=queue, admitted_futures=futures,
            websocket=SimpleNamespace(finish_runtime_request=finish, send_runtime_completion=send), execution=None,
            coordinator=SimpleNamespace(_binding_pin=lambda _: ('s',1,100), _connection_current=lambda ref,pin: True),
            _dialogue_owner_call=owner, start_cognition_inputs=lambda *a: None, send_lock=asyncio.Lock(),
            transport_close_requested=asyncio.Event(), connection_context=SimpleNamespace(binding=None),
            time=lambda: 0, stream_mode='full', project_outbound_messages=lambda value,**kw: value,
            _as_envelope=lambda kind,payload: dict(message_type=kind,payload=payload))
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<original-completion-pump>', 'exec'), namespace)
        task = asyncio.create_task(namespace['complete_admitted_commands']())
        await asyncio.gather(task, return_exceptions=True)
        assert task.cancelled() and sent == ['0']
        assert terminals == ['0','1','2'] and not futures
        await asyncio.wait_for(queue.join(), 1)
    asyncio.run(run())
