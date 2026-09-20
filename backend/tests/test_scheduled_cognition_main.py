import json
import subprocess
import sys
import pytest
from scripts.verification.population_godot_runner import child_environment


@pytest.mark.parametrize(('head_delta', 'provider_delay'), [(None, 0), (0, 0), (1, 0), (None, 10)])
def test_real_raw_completion_admits_original_session_background_without_sync_provider(tmp_path, head_delta, provider_delay):
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
        started, release = Event(), Event()
        threads, messages = [], []
        observed = {}
        if sys.argv[3] != 'None':
            from app.services import cognition_wait
            original_wait = cognition_wait.finish_cognition_wait
            async def finish_and_advance(**kwargs):
                result = await original_wait(**kwargs)
                if result.status == 'completed':
                    def next_event():
                        store = main.character_agent_runtime._session_store
                        original = store.last_event('char_a')
                        later = store.append_event('char_a', 'character_perceived_event', original['producer_ts']+int(sys.argv[3]), {'summary':'later perception'})
                        observed['later_id'] = later['event_id']
                    await kwargs['owner_call'](next_event)
                return result
            stack.enter_context(patch.object(cognition_wait, 'finish_cognition_wait', finish_and_advance))
        async with main.component_app.router.lifespan_context(main.component_app):
            try:
                def prepare():
                    main.character_agent_runtime.set_background_mode('char_a', 'active')
                    def forbidden(*args, **kwargs): raise AssertionError('synchronous scheduled cognition forbidden')
                    stack.enter_context(patch.object(main.character_agent_runtime, 'run_scheduled_background_cognition_ticks', forbidden))
                    gateway = main.character_agent_runtime._l2._gateway
                    original = gateway.complete_prepared_request
                    def complete(request):
                        threads.append(get_ident())
                        started.set()
                        assert release.wait(5)
                        if len(threads) == 1:
                            # 合法模型耗时可以超过原测试轮询总时长，owner 仍须保持可用。
                            time.sleep(float(sys.argv[4]))
                        return original(request)
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
                        assert await asyncio.wait_for(asyncio.wrap_future(main.runtime_execution.submit(lambda: 'healthy')), .5) == 'healthy'
                        if sys.argv[2] == 'True':
                            raise WebSocketDisconnect()
                        release.set()
                        # 等待真实完成；固定轮询次数在慢机器上会先于合法模型期限失败。
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
                async with asyncio.timeout(30):
                    while True:
                        pending = await asyncio.wrap_future(main.runtime_execution.submit(lambda: main._character_cognition_driver.coordinator.admissions.list_pending(limit=1)))
                        if not pending: break
                        await asyncio.sleep(.02)
                assert not pending
                def proof():
                    admissions = main._character_cognition_driver.coordinator.admissions
                    store = admissions.store
                    rows = store._connection.execute("SELECT receipt_json FROM character_session_receipts WHERE kind='cognition_admission'").fetchall()
                    import json
                    entries = [admissions.read(json.loads(row[0])['child_key']) for row in rows]
                    entries = [entry for entry in entries if 'scheduled_session' in entry.source_pins]
                    assert entries
                    for entry in entries:
                        main._scheduled_cognition_source.validate(entry)
                        progress = admissions.read_progress(entry.child_key)
                        if observed and progress.status == 'stale':
                            assert progress.reason == 'cognition_provider_stale_pin'
                        else:
                            assert progress.status == 'completed'
                        assert entry.payload == {}
                        assert entry.source_event['event_id'] != observed.get('later_id')
                await asyncio.wrap_future(main.runtime_execution.submit(proof))
                release.set()
                await asyncio.sleep(.1)
                if sys.argv[2] == 'True':
                    assert await asyncio.wrap_future(main.runtime_execution.submit(check)) == before
            finally:
                release.set()
asyncio.run(run())
'''
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path), 'False', str(head_delta), str(provider_delay)], env=child_environment(), capture_output=True, text=True, timeout=75)
    assert result.returncode == 0, result.stdout + result.stderr
