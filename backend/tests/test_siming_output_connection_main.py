import json
from pathlib import Path
import subprocess
import sys
import pytest
from scripts.verification.population_godot_runner import child_environment


@pytest.mark.parametrize('mode', ['auto', 'assisted', 'revoked', 'wrong_actor', 'disconnected', 'frame_revoke', 'queued_revoke', 'closed_after_post', 'blocked_send', 'raw'])
def test_durable_siming_child_uses_only_original_authorized_socket(tmp_path, mode):
    (tmp_path/'roster.json').write_text(json.dumps({'actor_ids':['char_a','char_b','char_c',*[f'resident_{i:05d}' for i in range(97)]]}))
    code = r'''
import asyncio,sys,time,json
from pathlib import Path
from contextlib import ExitStack
from types import SimpleNamespace
from threading import Event
from unittest.mock import patch
from fastapi import WebSocketDisconnect
from scripts.verification.population_mixed_backend import configure
sys.path.insert(0,'backend/tests')
from test_siming_continuation import make_candidate
async def run():
    with ExitStack() as stack:
        main,_,_=configure(Path(sys.argv[1]),stack,mode='one_x',provider_mode='local_probe')
        stack.enter_context(patch.object(main,'start_population_runtime',lambda:None))
        started,release=Event(),Event()
        done=asyncio.Event()
        mode=sys.argv[2]
        class Provider:
            def generate_candidates(self,**kwargs):
                started.set()
                assert release.wait(5)
                return [make_candidate(target_environment_id=None)]
        async with main.component_app.router.lifespan_context(main.component_app):
            async def owner(fn): return await asyncio.wrap_future(main.runtime_execution.submit(fn))
            def prepare():
                main.siming_event_pipeline._runtime._llm_provider=Provider()
                if mode=='assisted': main.character_agent_runtime.set_control_mode('char_b','player_priority_assisted')
                if mode=='frame_revoke':
                    encode=main._as_character_agent_execution_envelopes
                    stack.enter_context(patch.object(main,'_as_character_agent_execution_envelopes',lambda commands:encode(commands)*2))
                if mode=='closed_after_post':
                    deliver=main.CognitionOutputSink._deliver
                    def close_then_deliver(sink,encoded):
                        sink.close()
                        return deliver(sink,encoded)
                    stack.enter_context(patch.object(main.CognitionOutputSink,'_deliver',close_then_deliver))
                if mode=='queued_revoke':
                    original_post=main.CognitionOutputSink.post
                    def revoke_then_post(sink,payload):
                        pin=payload['binding_pin']
                        assert main._revoke_websocket_session_for_transport(session_ref=pin[0],connection_ref=payload['connection_ref'],reason_code='revoked',now=int(time.time()))
                        return original_post(sink,payload)
                    stack.enter_context(patch.object(main.CognitionOutputSink,'post',revoke_then_post))
                now=int(time.time())
                def credential(actors): return main.websocket_session_auth_service.create_trusted_local_launch_credential(principal_ref='player',allowed_actor_refs=actors,issued_at=now,expires_at=now+60)
                return credential(('character:char_c',) if mode=='wrong_actor' else ('character:char_b','character:char_c')),credential(('character:char_b','character:char_c'))
            credentials=await owner(prepare)
            class Socket:
                query_params={}
                client=SimpleNamespace(host='127.0.0.1')
                def __init__(self,index): self.index=index;self.phase=0;self.messages=[]
                async def accept(self):pass
                async def close(self,**kwargs):pass
                async def send_json(self,message):
                    if mode=='blocked_send' and message['message_type']=='character_agent_execution':
                        await asyncio.Event().wait()
                    self.messages.append(message)
                    if mode=='frame_revoke' and message['message_type']=='character_agent_execution':
                        binding=next(row['payload'] for row in self.messages if row['message_type']=='websocket_session_bound')
                        def revoke():
                            ref=main.gameplay_mirror_connection_registry.connection_ref_for(session_ref=binding['session_ref'])
                            assert main._revoke_websocket_session_for_transport(session_ref=binding['session_ref'],connection_ref=ref,reason_code='revoked',now=int(time.time()))
                        await owner(revoke)
                async def receive_json(self):
                    self.phase+=1
                    if self.phase==1: return {'message_type':'websocket_session_bind','payload':{'credential_kind':'trusted_local_launch','credential':credentials[self.index],'protocol_version':1}}
                    if self.index==1:
                        await done.wait()
                        raise WebSocketDisconnect()
                    if self.phase==2 and mode=='raw': return {'message_type':'raw_fact_event','payload':{'fact_family':'visual_fact','fact_type':'light_level_drop','room_id':'room_demo','scene_id':'scene_demo','zone_id':'zone_focus','producer_ts':300,'source':{'system':'godot.raw_fact_emitter','actor_id':'char_c'},'targets':{'environment_id':'env_lamp'},'observability':{'visual':True}}}
                    if self.phase==2: return {'message_type':'visual_fact_event','payload':{'actor_id':'char_c','fact_type':'light_level_drop','room_id':'room_demo','scene_id':'scene_demo','zone_id':'zone_focus','producer_ts':300,'target_environment_id':'env_lamp'}}
                    deadline=time.monotonic()+5
                    while not started.is_set() and time.monotonic()<deadline: await asyncio.sleep(.02)
                    assert started.is_set(),self.messages
                    if mode=='revoked':
                        binding=next(row['payload'] for row in self.messages if row['message_type']=='websocket_session_bound')
                        def revoke():
                            ref=main.gameplay_mirror_connection_registry.connection_ref_for(session_ref=binding['session_ref'])
                            assert main._revoke_websocket_session_for_transport(session_ref=binding['session_ref'],connection_ref=ref,reason_code='revoked',now=int(time.time()))
                        await owner(revoke)
                    release.set()
                    if mode=='disconnected':raise WebSocketDisconnect()
                    deadline=time.monotonic()+8
                    while time.monotonic()<deadline:
                        rows=await owner(lambda:main.character_agent_runtime._session_store._connection.execute("SELECT receipt_json FROM character_session_receipts WHERE kind='cognition_output'").fetchall())
                        if rows and (mode=='blocked_send' or not main._transient_cognition_tasks):break
                        await asyncio.sleep(.02)
                    assert rows,main.get_population_runtime_failure()
                    await asyncio.sleep(.1)
                    done.set()
                    raise WebSocketDisconnect()
            sockets=[Socket(0),Socket(1)]
            tasks=[asyncio.create_task(main.websocket_endpoint(socket)) for socket in sockets]
            try:
                await tasks[0]
                if mode=='disconnected':
                    deadline=time.monotonic()+8
                    while time.monotonic()<deadline:
                        rows=await owner(lambda:main.character_agent_runtime._session_store._connection.execute("SELECT receipt_json FROM character_session_receipts WHERE kind='cognition_output'").fetchall())
                        if rows:break
                        await asyncio.sleep(.02)
                    assert rows
                done.set();await tasks[1]
                outputs=lambda socket:[row for row in socket.messages if row['message_type'] in {'character_agent_execution','character_agent_suggestion'} and row['payload'].get('actor_id')=='char_b']
                assert not outputs(sockets[1])
                actual=outputs(sockets[0])
                assert bool(actual)==(mode in {'auto','assisted','frame_revoke','raw'}),(mode,sockets[0].messages)
                if mode=='frame_revoke':assert len(actual)==1
                if mode=='assisted':assert all(row['message_type']=='character_agent_suggestion' for row in actual)
                def receipts():
                    store=main.character_agent_runtime._session_store
                    rows=[json.loads(row[0]) for row in store._connection.execute("SELECT receipt_json FROM character_session_receipts WHERE kind='cognition_output'")]
                    assert rows
                    outputs=rows
                    assert all(row['status']==('handoff_started' if mode in {'auto','assisted','frame_revoke','queued_revoke','closed_after_post','blocked_send','raw'} else 'not_routed') for row in rows)
                    for output in outputs:
                        child=main._character_cognition_driver.coordinator.admissions.read(output['child_key'])
                        progress=main._character_cognition_driver.coordinator.admissions.read_progress(child.child_key)
                        before=store._connection.total_changes
                        main._character_cognition_driver.on_completed(child,progress)
                        assert store._connection.total_changes==before
                        transport=store.read_receipt(child.actor_id,kind='cognition_transport',key=child.child_key)
                        if mode in {'auto','assisted','raw'}:
                            assert transport['status']=='sent' and transport['sent_frames']>0
                        if mode in {'frame_revoke','queued_revoke','closed_after_post','blocked_send'}:
                            assert transport['status']=='not_sent'
                            assert transport['sent_frames']==(1 if mode=='frame_revoke' else 0)
                await owner(receipts)
            finally:
                release.set();done.set()
                for task in tasks:
                    if not task.done():task.cancel()
                await asyncio.gather(*tasks,return_exceptions=True)
asyncio.run(run())
'''
    result=subprocess.run([sys.executable,'-c',code,str(tmp_path),mode],cwd=Path(__file__).resolve().parents[2],
        env={**child_environment(), 'CHARACTER_MODEL_PROVIDER_KIND':'local', 'SIMING_LLM_MODE':'disabled'},
        capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
