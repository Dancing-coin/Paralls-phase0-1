import asyncio
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.verification import verify_population_mixed_soak as soak


def test_live_child_environment_preserves_only_explicit_model_configuration():
    values = {key: 'private-value' for key in ('DIALOGUE_MODE', 'CHARACTER_MODEL_PROVIDER_KIND', 'CHARACTER_MODEL_ENDPOINT',
        'CHARACTER_MODEL_API_KEY', 'CHARACTER_MODEL_MODEL', 'SIMING_LLM_MODE', 'SIMING_LLM_API_KEY',
        'SIMING_LLM_ROUTES_JSON', 'SIMING_LLM_PROVIDER_ORDER', 'SIMING_UNRELATED_SECRET')}
    live = soak.backend_environment('live', values)
    assert all(live[key] == value for key, value in values.items() if key != 'SIMING_UNRELATED_SECRET')
    assert 'SIMING_UNRELATED_SECRET' not in live
    assert not set(values).intersection(soak.backend_environment('local_probe', values))


@pytest.mark.parametrize('provider_mode', ['local_probe', 'live'])
def test_mixed_configuration_reaches_preimported_model_modules(tmp_path, provider_mode):
    from scripts.verification.population_godot_runner import child_environment
    (tmp_path / 'roster.json').write_text(json.dumps({'actor_ids': ['char_a', 'char_b', 'char_c',
        *[f'resident_{index:05d}' for index in range(97)]]}), encoding='utf-8')
    code = '''
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from app import config
config.settings = config.Settings(dialogue_mode='online', character_model_provider_kind='openai_compatible',
    character_model_endpoint='https://example.invalid', character_model_api_key='test-key',
    character_model_model='test-model', siming_llm_mode='http', siming_llm_api_key='test-key')
from app.character_agent.gateway import model_provider, model_router
from scripts.verification.population_mixed_backend import configure
with ExitStack() as stack:
    stack.enter_context(patch.object(model_provider, 'urlopen', side_effect=AssertionError('local probe attempted network')))
    main, _, _ = configure(Path(sys.argv[1]), stack, mode='one_x', provider_mode=sys.argv[2])
    live = sys.argv[2] == 'live'
    expected = 'openai_compatible' if live else 'local'
    route = model_router.CharacterModelRouter().resolve_route()
    assert route['provider_kind'] == expected, route
    provider = model_provider.CharacterModelProvider()
    assert provider._provider_kind == expected
    assert model_provider.settings.character_model_require_online == live
    assert model_router.settings.population_roster_path == str(Path(sys.argv[1]) / 'roster.json')
    if live:
        assert provider._model_name == 'test-model' and main.settings.siming_llm_mode == 'http'
    else:
        result = provider.complete(dict(task_kind='dialogue_generation', route=route, context={}, prompt={}, policy={}))
        assert result['content'] and not provider.last_call_evidence.transport_attempted
        assert main.settings.siming_llm_mode == 'disabled'
'''
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path), provider_mode],
        cwd=soak.ROOT, env=child_environment(), capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stderr


def test_drain_waits_for_domain_indexed_cognition_and_live_holders():
    from types import SimpleNamespace
    entries = [('actor', 'projection:organization-window-due:tail', 3, 1)]
    pending = []
    calls = []
    def outbox(**kwargs):
        calls.append(kwargs)
        return pending
    char_pending, siming_pending = [], []
    character = SimpleNamespace(_active={}, _handles={}, coordinator=SimpleNamespace(
        admissions=SimpleNamespace(list_pending=lambda **kw: char_pending)))
    siming = SimpleNamespace(_active={}, _unsubmitted={}, coordinator=SimpleNamespace(
        admissions=SimpleNamespace(list_pending_all=lambda **kw: SimpleNamespace(entries=siming_pending)),
        runtime=SimpleNamespace(pending_count=0)))
    main = SimpleNamespace(_population_runtime_driver=SimpleNamespace(current_tick=3,
        world_runtime=SimpleNamespace(_population_due_index=SimpleNamespace(export_entries=lambda: entries))),
        gameplay_event_store=SimpleNamespace(list_outbox=outbox), _character_cognition_driver=character,
        _siming_cognition_driver=siming, _transient_cognition_turns={}, _transient_cognition_tasks=set(),
        _cognition_output_routes=SimpleNamespace(connections={}),
        _dialogue_coordinator=SimpleNamespace(_pending={}),
        character_agent_runtime=SimpleNamespace(pending_cognition_jobs=lambda: ()))
    publisher = SimpleNamespace(DOMAIN_TOPIC='original-domain-topic')
    assert not soak.drain_state(main, publisher)['b1_drained']
    entries.clear()
    pending.append('original')
    assert not soak.drain_state(main, publisher)['b1_drained']
    pending.clear()
    state = soak.drain_state(main, publisher)
    assert state['b1_drained']
    assert calls == [dict(include_delivered=False, topic='original-domain-topic', limit=1)] * 3
    state.update(soak.drain_loop_state(main), provider_active=0, population_stopped=True)
    assert soak.drain_complete(state)
    assert not soak.drain_complete(dict(state, population_stopped=False))
    # 模型尚未占槽的持久待办、completed后尚未释放的lease也阻止提前结束。
    for values in (char_pending, siming_pending):
        values.append('queued')
        current = dict(state, **soak.drain_state(main, publisher))
        assert not soak.drain_complete(current)
        values.clear()
    character._handles['finished-but-not-released'] = object()
    assert not soak.drain_complete(dict(state, **soak.drain_state(main, publisher)))
    character._handles.clear()
    main._transient_cognition_tasks = {type('Task', (), {'done': lambda self: False})()}
    assert not soak.drain_complete(dict(state, **soak.drain_loop_state(main)))
    main._transient_cognition_tasks.clear()
    async def check_output_handoff():
        from app.services.cognition_output_route import CognitionOutputSink, CognitionOutputRoutes
        releases = []
        main._cognition_output_routes = CognitionOutputRoutes()
        sink = CognitionOutputSink(deliver=lambda payload, release, closed: releases.append(release))
        main._cognition_output_routes.connections['original-connection'] = sink
        assert sink.post({'original': 'output'})
        def current():
            return dict(state, **soak.drain_state(main, publisher), **soak.drain_loop_state(main))
        # call_soon已接纳而loop尚未执行，不能误报所有任务已排空。
        assert not releases and current()['cognition_output_pending'] == 1
        assert not soak.drain_complete(current())
        main._cognition_output_routes.disconnect('original-connection')
        assert current()['cognition_output_pending'] == 1
        assert not soak.drain_complete(current())
        await asyncio.sleep(0)
        assert releases and not soak.drain_complete(current())
        releases.pop()()
        main._cognition_output_routes.release('original-connection', sink)
        assert not main._cognition_output_routes.connections
        assert soak.drain_complete(current())
        incomplete = current()
        del incomplete['cognition_output_pending']
        assert not soak.drain_complete(incomplete)
    asyncio.run(check_output_handoff())


def test_drain_does_not_accept_missing_counters_or_running_population():
    assert not soak.drain_complete(dict(b1_drained=True, population_stopped=True, provider_active=0))


def test_early_stop_cancels_full_duration_load_and_writes_final_evidence(tmp_path):
    from time import perf_counter, sleep
    from scripts.verification.population_godot_runner import child_environment, write_json
    (tmp_path / 'state').mkdir()
    (tmp_path / 'run.json').write_text(json.dumps(dict(population=100, seconds=60, seed=31, mode='one_x', provider_mode='local_probe')), encoding='utf-8')
    (tmp_path / 'roster.json').write_text(json.dumps(dict(actor_ids=['char_a','char_b','char_c',
        *[f'resident_{i:05d}' for i in range(97)]])), encoding='utf-8')
    with (tmp_path / 'child.log').open('w') as log:
        child = subprocess.Popen([sys.executable, str(soak.ROOT / 'scripts/verification/verify_population_mixed_soak.py'),
            '--backend-child', str(tmp_path)], cwd=soak.ROOT, env=child_environment(), stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = perf_counter() + 30
            while not (tmp_path / 'ready.json').exists():
                assert child.poll() is None and perf_counter() < deadline
                sleep(.02)
            origin = perf_counter() + .1
            write_json(tmp_path / 'start', dict(origin=origin, load_end=origin+60))
            sleep(.3)
            (tmp_path / 'stop').touch()
            child.wait(timeout=8)
            assert child.returncode == 0, (tmp_path / 'child.log').read_text(encoding='utf-8')
            assert (tmp_path / 'server.json').exists() and (tmp_path / 'final-state.json').exists()
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)


def test_control_file_transient_lock_retries_but_corrupt_json_does_not(monkeypatch):
    calls = []
    def read(path):
        calls.append(path)
        if len(calls) < 3:
            raise PermissionError("transient sharing lock")
        return dict(origin=1, load_end=4)
    monkeypatch.setattr(soak, "read", read)
    assert asyncio.run(soak.read_control(Path("unused"))) == dict(origin=1, load_end=4)
    assert len(calls) == 3
    def corrupt(path):
        raise json.JSONDecodeError("bad json", "{", 1)
    monkeypatch.setattr(soak, "read", corrupt)
    with pytest.raises(json.JSONDecodeError):
        asyncio.run(soak.read_control(Path("unused")))


def test_client_load_stops_when_owned_backend_exits(monkeypatch):
    cancelled = []

    async def blocked_load(*_args):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)

    class ExitedProcess:
        returncode = 7

        def poll(self):
            return self.returncode

    monkeypatch.setattr(soak, "load", blocked_load)
    with pytest.raises(RuntimeError, match="mixed_backend_exited_during_load"):
        asyncio.run(soak.load_while_backend_alive(
            Path("unused"), {}, ExitedProcess(), None
        ))
    assert cancelled == [True]


def test_real_local_collection_preserves_windows_and_does_not_claim_formal_pass(tmp_path):
    from scripts.verification.population_godot_runner import child_environment
    directory = tmp_path / "collection"
    result = subprocess.run([sys.executable, str(soak.ROOT / "scripts/verification/verify_population_mixed_soak.py"),
        "--collect", str(directory), "--seconds", "3", "--population", "100", "--provider-mode", "local_probe"],
        cwd=soak.ROOT, env=child_environment(), capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = soak.read(directory / "manifest.json")
    assert manifest["collection_finished"] and not manifest["passed"]
    assert manifest["godot_status"] == "godot_unverified" and manifest["config"]["provider_mode"] == "local_probe"
    from scripts.verification.verify_population_service_isolation import raw_artifacts
    assert manifest["raw_artifacts"] == raw_artifacts(directory)
    assert {"server.jsonl", "client.json", "responses.jsonl", "final-state.json", "run.json",
        'authority.jsonl', 'character.jsonl', 'siming.jsonl', 'server-requests.json'} <= manifest["raw_artifacts"].keys()
    assert manifest["environment"]["godot"] == "not_run" and manifest["environment"]["packages"]
    assert manifest["started_at"] < manifest["finished_at"] and manifest["backend_pid"] > 0
    rows = [json.loads(line) for line in (directory / "server.jsonl").read_text(encoding="utf-8").splitlines()]
    windows = [row for row in rows if row["type"] == "window"]
    assert [row["target_tick"] for row in windows if row['phase'] == 'measurement'] == [1, 2, 3]
    assert any(row['phase'] == 'drain' for row in windows)
    assert all(row["sample"]["confirmed_tick"] == row["target_tick"] for row in windows)
    assert all(row["result"]["b0_advanced_count"] == 100 for row in windows)
    assert all(len(row["fixtures"][0]["rows"]) == 28 for row in windows if row['phase'] == 'measurement')
    assert all(row['fixtures'] == [] for row in windows if row['phase'] == 'drain')
    final = soak.read(directory / 'final-state.json')
    assert final['drain']['b1_drained'] and final['drain']['proven']
    assert final['drain']['limitations'] == [] and soak.drain_complete(final['drain'])
    assert final['recovery_state']['state_digest'] == final['state_digest'] and final['mode']
    server = soak.read(directory / "server.json")
    assert len(server["owner_threads"]) == 1 and server["owner_threads"] == server["mutation_threads"]
    assert server["max_writers"] == 1 and server["active_writers"] == {}
    assert soak.read(directory / "client.json")["offered"] == 10
    assert not (directory / "ready.json").exists()
    assert manifest['endpoint']['host'] == '127.0.0.1' and manifest['endpoint']['port'] > 0
    from scripts.verification.population_mixed_authority import verify_gameplay
    from scripts.verification.population_mixed_cognition import verify_character
    from scripts.verification.population_mixed_siming import verify_siming
    authority = verify_gameplay(directory / 'authority.jsonl', mode=final['mode'],
        actors=soak.read(directory / 'roster.json')['actor_ids'], expected_confirmed_tick=final['confirmed_tick'], window_ticks=1)
    assert authority['b1_completed'] == 84 and authority['pending_b1'] == 0
    children = verify_character(directory / 'character.jsonl')
    verify_siming(directory / 'siming.jsonl', character_jobs=children['jobs'])

def test_sqlite_export_failure_preserves_failed_manifest_and_partial_raw(tmp_path, monkeypatch):
    import sqlite3
    from scripts.verification import population_godot_runner as runner
    from scripts.verification import verify_population_runtime_correctness as correctness
    directory = tmp_path / 'collection'
    waited = []
    class Child:
        pid = 123
        returncode = 0
        def __init__(self, *args, **kwargs):
            (directory/'ready.json').write_text('{"port":12345}', encoding='utf-8')
            sqlite3.connect(directory/'state/graph.sqlite3.gameplay.json').close()
        def wait(self, **kwargs):
            waited.append(True)
            return 0
    async def load(*args):
        return {}
    monkeypatch.setattr(soak.subprocess, 'Popen', Child)
    monkeypatch.setattr(soak.subprocess, 'check_output', lambda *args, **kwargs: '')
    monkeypatch.setattr(soak, 'load', load)
    monkeypatch.setattr(runner, 'source_manifest', lambda: {'files': {}})
    monkeypatch.setattr(correctness, 'environment', lambda: {})
    result = soak.collect(directory, population=100, seconds=3, seed=1, mode='one_x', provider_mode='local_probe')
    assert waited and result['backend_exit_code'] == 0
    assert result['collection_finished'] is False and result['passed'] is False
    assert result['errors'] == ['proof_export:OperationalError']
    assert soak.read(directory/'manifest.json') == result
    from scripts.verification.verify_population_service_isolation import raw_artifacts
    assert result['raw_artifacts'] == raw_artifacts(directory)
    assert 'authority.jsonl' in result['raw_artifacts']
