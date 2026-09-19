import json

import pytest

from scripts.verification import population_mixed_matrix as matrix


def test_current_mixed_matrix_keeps_only_100_and_1000_populations():
    assert {row['population'] for row in matrix.specifications('short')} == {100, 1000}
    soak = matrix.specifications('soak')
    assert {row['population'] for row in soak} == {100, 1000}
    assert any(row['population'] == 1000 and row['seconds'] == 7200 for row in soak)


def test_full_matrix_requires_all_original_cases_but_reports_ten_x_performance_separately(tmp_path, monkeypatch):
    cases = matrix.specifications('soak')
    manifest = dict(schema_version=1, profile='population-mixed-soak', base_commit='a'*40,
        source={'files': {}}, matrix='soak', cases=cases)
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    monkeypatch.setattr(matrix, 'identity', lambda _: {'files': {}})
    def verify(path, **kwargs):
        expected = next(row for row in cases if row['directory'] == path.name)
        return dict(config={key:expected[key] for key in ('population', 'seconds', 'seed', 'mode', 'provider_mode')},
            integrity_passed=True, performance_passed=expected['mode'] == 'one_x', environment={'cpu': 'fixed'})
    monkeypatch.setattr(matrix, 'verify_case', verify)
    result = matrix.verify_matrix(tmp_path, expected_commit='a'*40, kind='soak')
    assert result['passed'] and len(result['ten_x_results']) == 2
    assert not any(row['performance_passed'] for row in result['ten_x_results'])
    for failure in ('missing', 'duplicate', 'escaped', 'changed_seed'):
        changed = json.loads(json.dumps(manifest))
        if failure == 'missing':
            changed['cases'].pop()
        elif failure == 'duplicate':
            changed['cases'][-1] = changed['cases'][0]
        elif failure == 'escaped':
            changed['cases'][0]['directory'] = '../outside'
        else:
            changed['cases'][0]['seed'] += 1
        (tmp_path / 'manifest.json').write_text(json.dumps(changed), encoding='utf-8')
        with pytest.raises(ValueError):
            matrix.verify_matrix(tmp_path, expected_commit='a'*40, kind='soak')
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    monkeypatch.setattr(matrix, 'verify_case', lambda path, **kwargs: dict(verify(path, **kwargs), integrity_passed=False))
    assert not matrix.verify_matrix(tmp_path, expected_commit='a'*40, kind='soak')['passed']


def test_matrix_collector_preserves_failed_case_and_continues_remaining_cases(tmp_path, monkeypatch):
    from scripts.verification import verify_population_mixed_soak as collector
    monkeypatch.setattr(matrix, 'identity', lambda _: {'files': {}})
    observed = []
    def collect(directory, **config):
        observed.append(config)
        directory.mkdir()
        return dict(collection_finished=len(observed) != 1)
    monkeypatch.setattr(collector, 'collect', collect)
    monkeypatch.setattr(matrix, 'verify_matrix', lambda *args, **kwargs: dict(passed=False))
    target = tmp_path / 'capture'
    result = matrix.collect_matrix(target, expected_commit='a'*40, kind='short')
    assert len(observed) == 2 and all(row['seconds'] == 30 for row in observed)
    assert result['status'] == 'failed' and not result['passed']
    assert result['errors'] == [dict(case='100-one_x-30s', error='collection_incomplete')]
    assert json.loads((target / 'manifest.json').read_text(encoding='utf-8')) == result
    with pytest.raises(FileExistsError):
        matrix.collect_matrix(target, expected_commit='a'*40, kind='short')
