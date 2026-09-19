"""固定混合负载矩阵；逐份复验原始证据，10× 性能单独报告。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'backend')]

from scripts.verification.aggregate_population_closure import _identity
from scripts.verification.population_godot_runner import write_json
from scripts.verification.population_mixed_verification import verify_case
from scripts.verification.verify_population_godot_runtime import read_json


def identity(commit):
    return _identity(commit)[0]


def specifications(kind):
    if kind not in {'soak', 'short'}:
        raise ValueError('mixed_matrix_kind_invalid')
    cases = [(n, 30 if kind == 'short' else 1800, 'one_x') for n in (100, 1000)]
    if kind == 'soak':
        cases.extend((n, 3, 'ten_x') for n in (100, 1000))
        cases.append((1000, 7200, 'one_x'))
    return [dict(directory=f'{n}-{mode}-{seconds}s', population=n, seconds=seconds,
        seed=31, mode=mode, provider_mode='live') for n, seconds, mode in cases]


def verify_matrix(directory, *, expected_commit, kind):
    directory = directory.resolve()
    manifest = read_json((directory / 'manifest.json').read_text(encoding='utf-8'))
    source = identity(expected_commit)
    cases = specifications(kind)
    if (manifest.get('schema_version') != 1 or manifest.get('profile') != 'population-mixed-'+kind
            or manifest.get('base_commit') != expected_commit or manifest.get('source') != source
            or manifest.get('matrix') != kind or manifest.get('cases') != cases):
        raise ValueError('mixed_matrix_identity_or_coverage_invalid')
    results, environment = [], None
    for case in cases:
        path = (directory / case['directory']).resolve()
        if not path.is_relative_to(directory) or path == directory:
            raise ValueError('mixed_matrix_directory_outside_root')
        result = verify_case(path, expected_commit=expected_commit)
        if result['config'] != {key: value for key, value in case.items() if key != 'directory'}:
            raise ValueError('mixed_matrix_case_configuration_invalid')
        if environment is not None and environment != result['environment']:
            raise ValueError('mixed_matrix_environment_changed')
        environment = result['environment']
        results.append(dict(directory=case['directory'], **result))
    if identity(expected_commit) != source:
        raise ValueError('mixed_matrix_source_changed')
    one_x = [row for row in results if row['config']['mode'] == 'one_x']
    ten_x = [row for row in results if row['config']['mode'] == 'ten_x']
    return dict(passed=all(row['integrity_passed'] is True for row in results)
        and all(row['performance_passed'] is True for row in one_x),
        matrix=kind, environment=environment, cases=results, ten_x_results=ten_x,
        godot_status='godot_unverified')


def collect_matrix(directory, *, expected_commit, kind):
    from scripts.verification.verify_population_mixed_soak import collect
    source = identity(expected_commit)
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    cases = specifications(kind)
    manifest = dict(schema_version=1, profile='population-mixed-'+kind, base_commit=expected_commit,
        source=source, matrix=kind, cases=cases, status='running', passed=False,
        godot_status='godot_unverified', started_at=datetime.now(timezone.utc).isoformat(), errors=[])
    write_json(directory / 'manifest.json', manifest)
    for case in cases:
        try:
            # 变码后不继续消耗数小时采集不可能通过的证据。
            if identity(expected_commit) != source:
                raise ValueError('mixed_matrix_source_changed')
            report = collect(directory / case['directory'], **{key: value for key, value in case.items() if key != 'directory'})
            if not report['collection_finished']:
                manifest['errors'].append(dict(case=case['directory'], error='collection_incomplete'))
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
            manifest['errors'].append(dict(case=case['directory'], error=f'{type(error).__name__}: {error}'))
            break
        finally:
            write_json(directory / 'manifest.json', manifest)
    try:
        result = verify_matrix(directory, expected_commit=expected_commit, kind=kind)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        result = dict(passed=False, error=f'{type(error).__name__}: {error}')
    manifest.update(status='passed' if result['passed'] else 'failed', passed=result['passed'],
        finished_at=datetime.now(timezone.utc).isoformat(), result=result)
    write_json(directory / 'manifest.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=('soak', 'short'), default='soak')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--verify-artifacts', type=Path)
    parser.add_argument('--require-fresh-commit')
    args = parser.parse_args()
    revision = args.require_fresh_commit or subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if args.verify_artifacts:
        result = verify_matrix(args.verify_artifacts, expected_commit=revision, kind=args.kind)
    else:
        directory = args.output or ROOT / '.harness/verification' / ('population-mixed-'+args.kind+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        result = collect_matrix(directory, expected_commit=revision, kind=args.kind)
        write_json(ROOT / '.harness/verification' / ('population-mixed-'+args.kind+'-report.json'), result)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
