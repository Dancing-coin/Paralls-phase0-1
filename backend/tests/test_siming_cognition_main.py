from pathlib import Path
import json
import subprocess
import sys
import pytest
from scripts.verification.population_godot_runner import child_environment


@pytest.mark.parametrize("kind", ["candidate", "staging", "target_ref", "target_object_id", "entity_id", "child", "child_assisted"])
def test_main_siming_bus_admits_without_waiting_for_provider(tmp_path, kind):
    (tmp_path / 'roster.json').write_text(json.dumps(dict(actor_ids=['char_a', 'char_b', 'char_c', *[f'resident_{i:05d}' for i in range(97)]])), encoding='utf-8')
    code = '''
import asyncio, sys
from pathlib import Path
from contextlib import ExitStack
from threading import Event, get_ident
from types import SimpleNamespace
from unittest.mock import patch
from scripts.verification.population_mixed_backend import configure
sys.path.insert(0, 'backend/tests')
from test_siming_continuation import make_visual_fact_event, make_candidate
async def run():
    with ExitStack() as stack:
        main, _, _ = configure(Path(sys.argv[1]), stack, mode='one_x', provider_mode='local_probe')
        if sys.argv[2] == 'staging':
            main.settings = main.settings.model_copy(update={'siming_heavenly_mode': 'active'})
        stack.enter_context(patch.object(main, 'start_population_runtime', lambda: None))
        release, started = Event(), Event()
        threads = []
        class Provider:
            def generate_candidates(self, **kwargs):
                threads.append(get_ident())
                started.set()
                assert release.wait(5)
                return [make_candidate(target_environment_id=None)] if sys.argv[2].startswith("child") else []
        async with main.component_app.router.lifespan_context(main.component_app):
            try:
                def publish():
                    main.siming_event_pipeline._runtime._llm_provider = Provider()
                    event = make_visual_fact_event()
                    if sys.argv[2].startswith('child'):
                        if sys.argv[2] == 'child_assisted':
                            main.character_agent_runtime.set_control_mode('char_b', 'player_priority_assisted')
                        gateways = {main.character_agent_runtime._l2._gateway, main.character_agent_runtime._l3._gateway}
                        for gateway in gateways:
                            original = gateway.complete_prepared_request
                            def observed(request, original=original):
                                threads.append(get_ident())
                                return original(request)
                            stack.enter_context(patch.object(gateway, 'complete_prepared_request', observed))
                    if sys.argv[2] == 'staging':
                        from test_siming_heavenly_runtime_composition import _prepare_staged_graph_dispatch
                        from app.character_agent.storage.graph_memory_store import CharacterGraphMemoryStore
                        state = SimpleNamespace(siming_runtime=main.siming_event_pipeline._runtime,
                            character_graph_memory=CharacterGraphMemoryStore(main.heavenly_graph, scope_resolver=main.actor_private_scope))
                        event = _prepare_staged_graph_dispatch(state).source_event
                        original = main.character_agent_runtime._l2._gateway.complete_prepared_request
                        def off_owner(request, owner_thread=get_ident()):
                            threads.append(get_ident())
                            assert get_ident() != owner_thread, 'staging must not run Character inline'
                            return original(request)
                        stack.enter_context(patch.object(main.character_agent_runtime._l2._gateway, 'complete_prepared_request', off_owner))
                    if sys.argv[2] in {'target_ref', 'target_object_id', 'entity_id'}:
                        event = event.model_copy(update={'payload': {**event.payload, sys.argv[2]: 'obj_letter'}})
                    main.authority_event_bus.publish(event)
                    coordinator = main._siming_cognition_driver.coordinator
                    from app.models.siming_heavenly_memory import SimingAdmissionKey
                    return get_ident(), SimingAdmissionKey(scope=main.SimingHeavenlyRuntimeSupport._scope_for(event), source_event_id=event.event_id), event
                owner, key, event = await asyncio.wait_for(asyncio.wrap_future(main.runtime_execution.submit(publish)), 2)
                assert main._siming_cognition_driver.slots is main._dialogue_provider_slots
                if sys.argv[2] != "staging":
                    assert await asyncio.to_thread(started.wait, 4)
                    assert threads and owner not in threads
                assert await asyncio.wrap_future(main.runtime_execution.submit(lambda: 17)) == 17
                if sys.argv[2] in {'target_ref', 'target_object_id', 'entity_id'}:
                    def change_object():
                        reader = main.siming_event_pipeline._runtime._source_pin_reader
                        before = reader(event)
                        main.esm_service.commit_interaction_state(room_id=event.room_id, scene_id=event.scene_id,
                            zone_id=event.zone_id, target_object_id='obj_letter', current_state='removed_from_surface')
                        assert reader(event) != before
                    await asyncio.wrap_future(main.runtime_execution.submit(change_object))
                release.set()
                for _ in range(200):
                    receipt = await asyncio.wrap_future(main.runtime_execution.submit(lambda: main._siming_cognition_driver.coordinator.admissions.read(key)))
                    assert receipt is not None
                    if receipt.entry.state in {'completed', 'stale'} or receipt.entry.transition and receipt.entry.transition.reason == 'character_admission_unavailable':
                        break
                    assert main.get_population_runtime_failure() is None
                    await asyncio.sleep(.02)
                if sys.argv[2] in {'candidate', 'child', 'child_assisted', 'staging'}:
                    assert receipt.entry.state == 'completed', receipt.entry
                elif sys.argv[2] != 'staging':
                    assert receipt.entry.state == 'stale' and receipt.entry.result_revision is None, receipt.entry
                if sys.argv[2] in {'child', 'child_assisted', 'staging'}:
                    def read_child():
                        effect = next(item for item in main._siming_cognition_driver.coordinator.admissions.read(key,
                            revision=receipt.entry.commit_revision).entry.transition.effects if item.kind == 'character_delivery')
                        admissions = main._character_cognition_driver.coordinator.admissions
                        child = admissions.read_delivery(dispatch_event=main.AuthorityEvent.model_validate(effect.payload['event']),
                            delivery_input=effect.payload['delivery'], effect_key=effect.effect_key, expires_at=receipt.entry.expires_at)
                        return child, admissions.read_progress(child.child_key)
                    for _ in range(300):
                        child, progress = await asyncio.wrap_future(main.runtime_execution.submit(read_child))
                        if progress is not None and progress.status in {'completed', 'stale'}:
                            break
                        assert main.get_population_runtime_failure() is None
                        await asyncio.sleep(.02)
                    assert progress.status == 'completed', progress
                    assert child.source_kind == 'ingest_siming_output'
                    assert child.expires_at == receipt.entry.expires_at
                    assert progress.stage == ('suggestion' if sys.argv[2] == 'child_assisted' else 'execution'), progress
                    assert threads and owner not in threads
                    if sys.argv[2].startswith('child'):
                        assert len(threads) >= 3
                    output_receipt = await asyncio.wrap_future(main.runtime_execution.submit(lambda:
                        main.character_agent_runtime._session_store.read_receipt(child.actor_id, kind='cognition_output', key=child.child_key)))
                    assert output_receipt['status'] == 'not_routed' and output_receipt['reason'] == 'no_origin_connection'
                    def retry_terminal():
                        store = main.character_agent_runtime._session_store
                        before = store._connection.total_changes
                        main._character_cognition_driver.on_completed(child, progress)
                        assert store._connection.total_changes == before
                    await asyncio.wrap_future(main.runtime_execution.submit(retry_terminal))
            finally:
                release.set()
asyncio.run(run())
'''
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path), kind], cwd=Path(__file__).resolve().parents[2],
        env=child_environment(), capture_output=True, text=True, encoding='utf-8', timeout=25)
    assert result.returncode == 0, result.stderr
