"""进程局部 QoS：原策略恢复、交叠生命周期和真实 Windows 调用。"""
import os
import pytest
from app.services import process_qos as qos


def test_overlapping_lifetimes_restore_only_after_last_exit(monkeypatch):
    monkeypatch.setattr(qos, '_is_windows', lambda: True)
    state = [1, 4, 4]
    writes = []
    monkeypatch.setattr(qos, '_read_power_state', lambda: tuple(state))
    def write(value):
        writes.append(value)
        state[:] = value
    monkeypatch.setattr(qos, '_write_power_state', write)
    first = qos.high_qos()
    second = qos.high_qos()
    first.__enter__()
    second.__enter__()
    first.__exit__(None, None, None)
    assert state == [1, 5, 4]
    assert writes == [(1, 5, 4)]
    second.__exit__(None, None, None)
    assert state == [1, 4, 4]
    assert qos.process_qos_snapshot()['restored'] == [1, 4, 4]


def test_exception_restores_and_other_platform_does_not_call_native(monkeypatch):
    monkeypatch.setattr(qos, '_is_windows', lambda: False)
    monkeypatch.setattr(qos, '_read_power_state', lambda: pytest.fail('native called'))
    with pytest.raises(ValueError):
        with qos.high_qos():
            raise ValueError('body')
    assert qos.process_qos_snapshot()['supported'] is False


@pytest.mark.skipif(os.name != 'nt', reason='真实 Windows API')
def test_real_windows_policy_restored_after_exception():
    before = qos._read_power_state()
    with pytest.raises(ValueError):
        with qos.high_qos():
            current = qos._read_power_state()
            assert current == (before[0], before[1] | 1, before[2] & ~1)
            raise ValueError('body')
    assert qos._read_power_state() == before
    assert qos.process_qos_snapshot()['restored'] == list(before)


def test_native_apply_failure_propagates_and_restores_original(monkeypatch):
    monkeypatch.setattr(qos, '_is_windows', lambda: True)
    state = [1, 0, 0]
    monkeypatch.setattr(qos, '_read_power_state', lambda: tuple(state))
    def write(value):
        if value[1] == 1:
            raise OSError('apply failed')
        state[:] = value
    monkeypatch.setattr(qos, '_write_power_state', write)
    with pytest.raises(OSError, match='apply failed'):
        with qos.high_qos():
            pytest.fail('entered after native failure')
    assert state == [1, 0, 0]
    assert qos._users == 0
    assert qos._original is None


def test_failed_restore_retains_original_for_next_lifetime(monkeypatch):
    monkeypatch.setattr(qos, '_is_windows', lambda: True)
    state = [1, 0, 0]
    fail = [True]
    monkeypatch.setattr(qos, '_read_power_state', lambda: tuple(state))
    def write(value):
        if value == (1, 0, 0) and fail[0]:
            fail[0] = False
            raise OSError('restore failed')
        state[:] = value
    monkeypatch.setattr(qos, '_write_power_state', write)
    with pytest.raises(OSError, match='restore failed'):
        with qos.high_qos():
            pass
    assert qos._original == (1, 0, 0)
    state[:] = [1, 5, 4]
    with qos.high_qos():
        assert state == [1, 5, 4]
    assert state == [1, 4, 4]
    assert qos._original is None


def test_restore_preserves_non_owned_bits_changed_during_scope(monkeypatch):
    monkeypatch.setattr(qos, '_is_windows', lambda: True)
    state = [1, 0, 0]
    monkeypatch.setattr(qos, '_read_power_state', lambda: tuple(state))
    monkeypatch.setattr(qos, '_write_power_state', lambda value: state.__setitem__(slice(None), value))
    with qos.high_qos():
        state[:] = [1, 5, 4]
    assert state == [1, 4, 4]
    assert qos.process_qos_snapshot()['restored'] == [1, 4, 4]


def test_recorded_generator_context_hashes_actual_restore(tmp_path):
    import json
    from scripts.verification.population_process_qos import recorded_high_qos
    from scripts.verification.verify_population_service_isolation import raw_artifacts
    path = tmp_path / 'collector-qos.json'
    with pytest.raises(ValueError):
        with recorded_high_qos(path):
            raise ValueError('body')
    record = json.loads(path.read_text(encoding='utf-8'))
    assert record['pid'] == os.getpid()
    assert record['restored'] == record['before']
    assert 'collector-qos.json' in raw_artifacts(tmp_path)


@pytest.mark.parametrize('kind', ['service', 'mixed', 'cost', 'render', 'capacity', 'fixture'])
def test_existing_capture_directory_is_never_modified_by_qos(tmp_path, kind):
    import json
    from pathlib import Path
    from scripts.verification import verify_population_service_isolation as service
    from scripts.verification import verify_population_mixed_soak as mixed
    from scripts.verification import verify_population_transport_cost as cost
    from scripts.verification import population_godot_runner as render
    from scripts.verification import verify_population_multi_game_capacity as capacity
    from scripts.verification import verify_population_long_session_recovery as recovery
    path = tmp_path / 'existing'
    path.mkdir()
    for name in ('manifest.json', 'collector-qos.json', 'raw.json'):
        (path / name).write_text(json.dumps({'passed': True, 'raw_artifacts': {'raw.json': 'original'}}))
    before = {item.name: item.read_bytes() for item in path.iterdir()}
    calls = dict(service=lambda: service.collect(path, 100, 1),
        mixed=lambda: mixed.collect(path, population=100, seed=31, seconds=1, mode='one_x', provider_mode='local_probe'),
        cost=lambda: cost.collect(path, population=100, windows=1, repeats=1),
        render=lambda: render.collect(path, Path('never-run-godot')),
        capacity=lambda: capacity.collect_group(path, games=2),
        fixture=lambda: recovery.generate_fixture(path, population=3, history=16, tail=1))
    with pytest.raises((FileExistsError, ValueError)):
        calls[kind]()
    assert {item.name: item.read_bytes() for item in path.iterdir()} == before


def test_service_restore_failure_cannot_overwrite_manifest_with_success(tmp_path, monkeypatch):
    import json
    from scripts.verification import verify_population_service_isolation as service
    from scripts.verification.population_godot_runner import write_json
    monkeypatch.setattr(qos, '_is_windows', lambda: True)
    state = [1, 0, 0]
    monkeypatch.setattr(qos, '_read_power_state', lambda: tuple(state))
    def write(value):
        if value == (1, 0, 0):
            raise OSError('restore failed')
        state[:] = value
    monkeypatch.setattr(qos, '_write_power_state', write)
    def collect(directory, *_args):
        report = {'passed': True, 'errors': []}
        write_json(directory / 'manifest.json', report)
        return report
    monkeypatch.setattr(service, '_collect', collect)
    directory = tmp_path / 'new'
    try:
        with pytest.raises(OSError, match='restore failed'):
            service.collect(directory, 100, 1)
        assert json.loads((directory / 'manifest.json').read_text())['passed'] is False
        assert json.loads((directory / 'collector-qos.json').read_text())['error'] == 'OSError'
    finally:
        # 模拟原生恢复重试成功，避免污染后续控制。
        monkeypatch.setattr(qos, '_write_power_state', lambda value: state.__setitem__(slice(None), value))
        with qos.high_qos():
            pass


def test_fixture_scope_restore_failure_is_saved_as_failed_generation(tmp_path, monkeypatch):
    import json
    from scripts.verification import verify_population_long_session_recovery as recovery
    from scripts.verification.population_godot_runner import write_json
    monkeypatch.setattr(qos, '_is_windows', lambda: True)
    state = [1, 0, 0]
    monkeypatch.setattr(qos, '_read_power_state', lambda: tuple(state))
    def write(value):
        if value == (1, 0, 0):
            raise OSError('restore failed')
        state[:] = value
    monkeypatch.setattr(qos, '_write_power_state', write)
    monkeypatch.setattr(recovery, '_generate_fixture_with_policy',
        lambda directory, **kwargs: write_json(directory / 'manifest.json', dict(schema_version=1)))
    path = tmp_path / 'fixture'
    try:
        with pytest.raises(OSError, match='restore failed'):
            recovery.generate_fixture(path, population=3, history=16, tail=1)
        generation = json.loads((path / 'manifest.json').read_text())['generation']
        assert generation['completed'] is False and generation['error'] == 'OSError'
    finally:
        monkeypatch.setattr(qos, '_write_power_state', lambda value: state.__setitem__(slice(None), value))
        with qos.high_qos():
            pass


def test_qos_record_validation_checks_only_owned_bits():
    from scripts.verification.population_process_qos import require_restored_qos
    require_restored_qos(dict(pid=123, supported=True, before=[1, 0, 0],
                             applied=[1, 1, 0], restored=[1, 4, 4]))
    require_restored_qos(dict(pid=123, supported=False, before=None, applied=None, restored=None))
    with pytest.raises(ValueError):
        require_restored_qos(dict(pid=123, supported=True, before=[1, 0, 0],
                                 applied=[1, 1, 0], restored=None, error='OSError'))
