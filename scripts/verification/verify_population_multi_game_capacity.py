"""共同墙钟起点的 2/4 局容量采集；保留容量失败，不把缺证据当完成。"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import ntpath
import posixpath
from urllib.parse import unquote, urlsplit
from pathlib import Path
import subprocess
import sys
from time import perf_counter, sleep

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'backend')]

from scripts.verification.population_godot_runner import write_json
from scripts.verification.common import collection_output_path, collection_report_path
from scripts.verification.population_mixed_evidence import number
from scripts.verification.population_mixed_matrix import identity
from scripts.verification.population_mixed_verification import verify_case
from scripts.verification.verify_population_godot_runtime import json_lines, read_json, digest


def specifications():
    return [dict(games=count, directory=f'{count}-games', cases=[dict(directory=f'game-{i}',
        population=1000, seconds=600, seed=30+i, mode='one_x', provider_mode='live', capacity_metrics=True)
        for i in range(1, count+1)]) for count in (2, 4)]


def resource_metrics(directory):
    """实测逻辑 SQLite 读量及 writer 调用；存储文件大小不充作磁盘吞吐。"""
    records, windows, drains = [], [], []
    for row in json_lines(directory / 'server.jsonl'):
        if row['type'] == 'capacity_resources':
            records.append(row)
        elif row['type'] == 'window':
            windows.append(row)
        elif row['type'] == 'drain':
            drains.append(row)
    if [row['phase'] for row in records] != ['start', 'after_drain'] or not windows or not drains:
        raise ValueError('capacity_resource_evidence_missing')
    start, end = records
    interval = read_json((directory / 'start').read_text(encoding='utf-8'))
    at = number(start['at'], minimum=interval['origin'])
    until = number(end['at'], minimum=max(interval['load_end'], at))
    tail_end = max(windows[-1]['finished_at'], number(drains[-1]['at']))
    if at > windows[0]['started_at'] or until < tail_end:
        raise ValueError('capacity_resource_interval_invalid')
    cpu_start = number(start['cpu_seconds'])
    cpu = number(end['cpu_seconds'], minimum=cpu_start)-cpu_start
    before, after = start['sqlite'], end['sqlite']
    if (before['vm_interval'] != after['vm_interval'] or before['vm_steps_are_sampled'] is not True
            or after['vm_steps_are_sampled'] is not True or not before['databases'].keys() <= after['databases'].keys()):
        raise ValueError('capacity_sqlite_meter_changed')
    databases = {}
    for path, counters in after['databases'].items():
        old = before['databases'].get(path, {})
        databases[path] = {key: number(counters[key], integer=True, minimum=number(old.get(key, 0), integer=True))-old.get(key, 0)
            for key in ('rows', 'payload_bytes', 'statements', 'scripts', 'vm_steps_sampled')}
    if any(sum(row[key] for row in databases.values()) <= 0 for key in ('rows', 'payload_bytes', 'statements')):
        raise ValueError('capacity_sqlite_io_missing')
    server = read_json((directory / 'server.json').read_text(encoding='utf-8'))
    parent = [row for row in json_lines(directory / 'parent.jsonl') if row['type'] == 'resources']
    if ([row['phase'] for row in parent] != ['start', 'after_drain']
            or any(row['process_id'] != server['parent_pid'] for row in parent)):
        raise ValueError('capacity_parent_resource_evidence_missing')
    parent_start, parent_end = parent
    parent_at = number(parent_start['at'], minimum=interval['origin'])
    parent_until = number(parent_end['at'], minimum=max(interval['load_end'], parent_at))
    if parent_at > windows[0]['started_at'] or parent_until < max(tail_end, until):
        raise ValueError('capacity_parent_resource_interval_invalid')
    parent_cpu_start = number(parent_start['cpu_seconds'])
    parent_cpu = number(parent_end['cpu_seconds'], minimum=parent_cpu_start)-parent_cpu_start
    return dict(cpu_seconds=cpu+parent_cpu, cpu_seconds_by_role=dict(owner=cpu, parent=parent_cpu),
        observed_seconds=until-at, parent_observed_seconds=parent_until-parent_at, includes_tail_drain=True,
        sqlite_io=dict(scope='logical_sqlite_io', physical_disk_bytes_measured=False,
            databases=databases, writer_calls=server['writer_calls']), writer_count=server['max_writers'])


def database_identities(resources, directory):
    """按采集路径的稳定 group/game/state 位置绑定主库；不依赖证据现存目录。"""
    identities = set()
    for value in resources['sqlite_io']['databases']:
        path = value
        if path.startswith('file:'):
            uri = urlsplit(path)
            path = ('//' + uri.netloc if uri.netloc else '') + unquote(uri.path)
            if len(path) > 2 and path[0] == '/' and path[2] == ':':
                path = path[1:]
        path = path.replace('\\', '/')
        if path.startswith('//?/UNC/'):
            path = '//' + path[8:]
        elif path.startswith('//?/'):
            path = path[4:]
        windows = bool(ntpath.splitdrive(path)[0])
        path = (ntpath.normpath(path).replace('\\', '/').lower() if windows else posixpath.normpath(path))
        if path.rsplit('/', 1)[-1] in {'graph.sqlite3', 'graph.sqlite3.gameplay.json'}:
            if not (windows or path.startswith('/')):
                raise ValueError('capacity_database_identity_not_absolute')
            identities.add(path)
    suffix = f'/{directory.parent.name}/{directory.name}/state/graph.sqlite3'
    graph = [path for path in identities if path.endswith(suffix)]
    if len(graph) != 1 or identities != {graph[0], graph[0]+'.gameplay.json'}:
        raise ValueError('capacity_database_game_binding_invalid')
    return graph[0][:-len(suffix)], identities


def verify_artifacts(directory, *, expected_commit):
    directory = directory.resolve()
    manifest = read_json((directory / 'manifest.json').read_text(encoding='utf-8'))
    source = identity(expected_commit)
    groups = specifications()
    if (manifest.get('schema_version') != 1 or manifest.get('profile') != 'population-multi-game-capacity'
            or manifest.get('base_commit') != expected_commit or manifest.get('source') != source
            or manifest.get('groups') != groups):
        raise ValueError('capacity_matrix_identity_invalid')
    expected_qos = {group['directory'] + '/collector-qos.json': digest((directory / group['directory'] / 'collector-qos.json').read_bytes()) for group in groups}
    if manifest.get('qos_artifacts') != expected_qos:
        raise ValueError('capacity_qos_artifacts_changed')
    if manifest.get('errors'):
        raise ValueError('capacity_collection_failed')
    from scripts.verification.population_process_qos import require_restored_qos
    for group in groups:
        require_restored_qos(read_json((directory / group['directory'] / 'collector-qos.json').read_text(encoding='utf-8')))
    results, environment = [], None
    for group in groups:
        root = (directory / group['directory']).resolve()
        if not root.is_relative_to(directory):
            raise ValueError('capacity_directory_outside_root')
        interval = read_json((root / 'start.json').read_text(encoding='utf-8'))
        if number(interval['load_end'])-number(interval['origin']) != 600:
            raise ValueError('capacity_full_overlap_required')
        pids, ports, cases = set(), set(), []
        database_paths, captured_root = set(), None
        for case in group['cases']:
            path = (root / case['directory']).resolve()
            if not path.is_relative_to(root):
                raise ValueError('capacity_directory_outside_root')
            result = verify_case(path, expected_commit=expected_commit)
            if (result['config'] != {key: value for key, value in case.items() if key != 'directory'}
                    or result['interval'] != interval):
                raise ValueError('capacity_configuration_or_overlap_invalid')
            pid = number(result['backend_pid'], integer=True, minimum=1)
            owner_pid = number(result['processes']['owner_pid'], integer=True, minimum=1)
            port = number(result['endpoint']['port'], integer=True, minimum=1)
            if (pid == owner_pid or {pid, owner_pid} & pids or port in ports
                    or port > 65535 or result['endpoint']['host'] != '127.0.0.1'):
                raise ValueError('capacity_game_process_or_port_reused')
            pids.update((pid, owner_pid))
            ports.add(port)
            if environment is not None and result['environment'] != environment:
                raise ValueError('capacity_machine_changed')
            environment = result['environment']
            resources = resource_metrics(path)
            original_root, databases = database_identities(resources, path)
            if databases & database_paths or (captured_root is not None and original_root != captured_root):
                raise ValueError('capacity_database_shared_or_capture_root_changed')
            database_paths.update(databases)
            captured_root = original_root
            cases.append(dict(directory=case['directory'], resources=resources, **result))
        results.append(dict(games=group['games'], capacity_passed=all(row['integrity_passed'] is True
            and row['performance_passed'] is True for row in cases), cases=cases))
    if identity(expected_commit) != source:
        raise ValueError('capacity_source_changed')
    return dict(passed=all(row['integrity_passed'] is True for group in results for row in group['cases']),
        groups=results, environment=environment, godot_status='godot_unverified')


def collect_group(directory, *, games, population=1000, seconds=600, provider_mode='live'):
    if games not in (2, 4):
        raise ValueError('capacity_game_count_invalid')
    directory.mkdir(parents=True, exist_ok=False)
    from scripts.verification.population_process_qos import recorded_high_qos
    with recorded_high_qos(directory / 'collector-qos.json'):
        return _collect_group_with_policy(directory, games=games, population=population,
                                          seconds=seconds, provider_mode=provider_mode)


def _collect_group_with_policy(directory, *, games, population=1000, seconds=600, provider_mode='live'):
    from scripts.verification.verify_population_mixed_soak import collect
    gate = directory / 'start.json'
    paths = [directory / f'game-{i}' for i in range(1, games+1)]
    # 每个collect只协调自己的实际后端子进程；权威库与writer仍在独立进程。
    with ThreadPoolExecutor(max_workers=games) as executor:
        futures = [executor.submit(collect, path, population=population, seconds=seconds, seed=31+i,
            mode='one_x', provider_mode=provider_mode, shared_start=gate, capacity_metrics=True)
            for i, path in enumerate(paths)]
        try:
            deadline = perf_counter()+150
            while not all((path / 'prepared.json').exists() for path in paths):
                if any(future.done() for future in futures) or perf_counter() >= deadline:
                    raise ValueError('capacity_backend_barrier_failed')
                sleep(.02)
            origin = perf_counter()+1
            write_json(gate, dict(origin=origin, load_end=origin+seconds))
            return [future.result() for future in futures]
        finally:
            if not gate.exists():
                # 解除其他已就绪collect的等待，让其走原有stop/finally回收自己的后端。
                write_json(gate, dict(abort=True))


def collect_matrix(directory, *, expected_commit):
    source = identity(expected_commit)
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    groups = specifications()
    manifest = dict(schema_version=1, profile='population-multi-game-capacity', base_commit=expected_commit,
        source=source, groups=groups, status='running', passed=False, godot_status='godot_unverified',
        started_at=datetime.now(timezone.utc).isoformat(), errors=[])
    write_json(directory / 'manifest.json', manifest)
    for group in groups:
        try:
            if identity(expected_commit) != source:
                raise ValueError('capacity_source_changed')
            collect_group(directory / group['directory'], games=group['games'])
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
            manifest['errors'].append(dict(group=group['directory'], error=f'{type(error).__name__}: {error}'))
            break
    manifest['qos_artifacts'] = {group['directory'] + '/collector-qos.json': digest((directory / group['directory'] / 'collector-qos.json').read_bytes()) for group in groups if (directory / group['directory'] / 'collector-qos.json').is_file()}
    write_json(directory / 'manifest.json', manifest)
    try:
        result = verify_artifacts(directory, expected_commit=expected_commit)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        result = dict(passed=False, error=f'{type(error).__name__}: {error}')
    result['passed'] = result['passed'] and not manifest['errors']
    manifest.update(status='passed' if result['passed'] else 'failed', passed=result['passed'], result=result,
        finished_at=datetime.now(timezone.utc).isoformat())
    write_json(directory / 'manifest.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--verify-artifacts', type=Path)
    parser.add_argument('--require-fresh-commit')
    args = parser.parse_args()
    revision = args.require_fresh_commit or subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if args.verify_artifacts:
        result = verify_artifacts(args.verify_artifacts, expected_commit=revision)
    else:
        directory = args.output or collection_output_path(ROOT, 'population-multi-game-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        result = collect_matrix(directory, expected_commit=revision)
        write_json(collection_report_path(ROOT, directory, 'population-multi-game-capacity-report.json'), result)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
