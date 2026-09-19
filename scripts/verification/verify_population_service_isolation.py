"""真实 Uvicorn 子进程隔离门禁；外部定速输入、原 owner、受控慢 provider，无 Godot。"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import ExitStack
from datetime import datetime, timezone
import json
from math import ceil, isclose, isfinite
from pathlib import Path
import socket
import subprocess
import sys
from threading import Lock, get_ident
from time import perf_counter, sleep, time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from scripts.verification.population_process_qos import recorded_high_qos
from scripts.verification.common import collection_output_path, collection_report_path
from scripts.verification.population_benchmark_metrics import percentile
from scripts.verification.population_godot_runner import child_environment, source_manifest, write_json
from scripts.verification.verify_population_transport_cost import _configure
from scripts.verification.verify_population_godot_runtime import digest, json_lines, read_json
from scripts.verification.verify_population_mixed_soak import read_control


async def until(deadline: float) -> None:
    # Windows asyncio 定时器可能按较粗时钟提前唤醒；用同一高精度时钟复核。
    while (remaining := deadline - perf_counter()) > 0:
        await asyncio.sleep(max(.001, remaining))


async def wait_for_process_drain(host) -> dict:
    """在正常 lifespan 关闭清表之前，等待原 IPC、发送和命令关联实际排空。"""
    async with asyncio.timeout(30):
        while True:
            state = host.snapshot()
            if state['status'] != 'ok':
                raise RuntimeError('service_process_failed_during_drain')
            if (all(state[key] == 0 for key in ('ipc_pending', 'pending_send', 'runtime_pending', 'transport_pending'))
                    and state['execution_credit']['current'] == 0):
                return state
            await asyncio.sleep(.02)


def _writer_boundaries():
    # 只列本负载实际装配的持久入口，不能以基类覆盖推断 durable 实现。
    from app.gameplay.event_store import DurableGameplayEventStore
    from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter
    from app.character_agent.storage.session_store import CharacterAgentSessionStore
    boundaries = [(DurableGameplayEventStore, "append_batch", "gameplay_durable_append"),
                  (DurableGameplayEventStore, "mark_outbox_delivered", "gameplay_outbox_delivered"),
                  (DurableGameplayEventStore, "mark_outbox_retryable", "gameplay_outbox_retryable"),
                  (SQLiteHeavenlyGraphAdapter, "write_batch", "heavenly_graph_batch")]
    boundaries.append((DurableGameplayEventStore, "save_projection_checkpoint", "gameplay_checkpoint"))
    boundaries.extend((CharacterAgentSessionStore, method, "character_session_" + method) for method in
        ("append_event", "save_runtime_state", "save_receipt", "set_projection_cursor", "write_ask",
         "commit_cognition_stage", "save_cognition_admission", "save_cognition_progress"))
    return boundaries


def install_writer_probes(stack, writer):
    boundaries = _writer_boundaries()
    for cls, method, name in boundaries:
        stack.enter_context(patch.object(cls, method, writer(name, getattr(cls, method))))
    return [name for _, _, name in boundaries]


def load_window_samples(values, starts, origin, end):
    if len(values) != len(starts) or end <= origin:
        raise ValueError("service_sample_window_invalid")
    return [value for value, started in zip(values, starts) if origin <= started < end]


def merge_process_observations(parent: dict, owner: dict, ready: dict) -> dict:
    """只合并同一实际子进程、同一测量区间；原始两方文件仍独立保存。"""
    try:
        if (parent['child_pid'] != owner['owner_pid'] or ready['owner_pid'] != owner['owner_pid']
                or any(parent[key] != owner[key] or ready[key] != owner[key]
                       for key in ('population', 'window_size'))
                or any(parent[key] != owner[key] for key in ('load_started_at', 'load_ended_at'))):
            raise ValueError('service_process_observations_mismatch')
        return dict(owner, **{key: parent[key] for key in ('parent_pid', 'child_exit_code',
            'heartbeat_ms', 'heartbeat_expected_at', 'queue_peak', 'execution_credit', 'asgi_lifecycle',
            'parent_drained', 'parent_drained_at')},
            parent_writer_calls=parent['writer_calls'], parent_mutation_threads=parent['mutation_threads'],
            parent_writer_boundaries=parent['writer_boundaries'], errors=owner['errors'] + parent['errors'])
    except (KeyError, TypeError) as error:
        raise ValueError('service_process_observations_invalid') from error


def evaluate(client: dict, server: dict) -> dict:
    def p(values, fraction=.95):
        return percentile(values, fraction) if values else None
    def identities(name):
        values = server.get(name)
        if not isinstance(values, list) or any(not isinstance(row, list) or len(row) != 2
                or any(type(value) is not int or value <= 0 for value in row) for row in values):
            return set()
        result = {tuple(row) for row in values}
        return result if len(result) == len(values) else set()
    try:
        origin, end = client["load_started_at"], client["load_ended_at"]
        window_valid = (server["load_started_at"] == origin and server["load_ended_at"] == end
                        and abs(end - origin - client["seconds"]) < .000001)
        heartbeat_values = load_window_samples(server["heartbeat_ms"], server["heartbeat_expected_at"], origin, end)
        window_values = load_window_samples(server["window_ms"], server["window_started_at"], origin, end)
    except (KeyError, TypeError, ValueError):
        window_valid, heartbeat_values, window_values = False, [], []
    metrics = dict(health_p95_ms=p(client["health_ms"]), accepted_p95_ms=p(client["accepted_ms"]),
                   business_p95_ms=p(client.get("business_ms", [])),
                   fact_p95_ms=p(client["fact_ms"]), heartbeat_p99_ms=p(heartbeat_values, .99),
                   window_p95_ms=p(window_values))
    offered = client["offered"]
    owner, mutations, providers = (identities(name) for name in
        ('owner_threads', 'mutation_threads', 'provider_threads'))
    parent_pid, owner_pid = server.get('parent_pid'), server.get('owner_pid')
    credit = server.get('execution_credit')
    credit_valid = (isinstance(credit, dict) and type(credit.get('capacity')) is int
        and credit['capacity'] == 128 and type(credit.get('current')) is int and credit['current'] == 0
        and type(credit.get('peak')) is int and 1 <= credit['peak'] <= 128
        and type(server.get('queue_peak')) is int and server['queue_peak'] == credit['peak'])
    try:
        state, sampled_at = server['parent_drained'], server['parent_drained_at']
        drained_credit = state['execution_credit']
        drain_valid = (state['status'] == 'ok' and type(state['child_pid']) is int and state['child_pid'] == owner_pid
            and isinstance(state['process_generation'], str) and bool(state['process_generation'])
            and all(type(state[key]) is int and state[key] == 0 for key in
                    ('ipc_pending', 'pending_send', 'runtime_pending', 'transport_pending'))
            and all(type(state[key]) is int and state[key] == 128 for key in
                    ('ipc_capacity', 'notification_capacity', 'runtime_pending_capacity', 'transport_pending_capacity'))
            and type(drained_credit['capacity']) is int and drained_credit['capacity'] == 128
            and type(drained_credit['current']) is int and drained_credit['current'] == 0
            and type(drained_credit['peak']) is int and credit_valid and 1 <= drained_credit['peak'] <= credit['peak']
            and type(sampled_at) in (int, float) and isfinite(sampled_at) and sampled_at >= end
            and all(sampled_at >= started + elapsed / 1000 for started, elapsed in
                    zip(server['window_started_at'], server['window_ms'], strict=True)))
    except (KeyError, TypeError, ValueError):
        drain_valid = False
    expected_boundaries = [name for _, _, name in _writer_boundaries()]
    checks = {
        "bounded_commands": credit_valid,
        "parent_drained": drain_valid,
        "process_boundary": (type(parent_pid) is int and type(owner_pid) is int
            and parent_pid > 0 and owner_pid > 0 and parent_pid != owner_pid
            and bool(owner) and bool(providers)
            and all(pid == owner_pid for pid, _ in owner | mutations | providers)
            and server.get('parent_mutation_threads') == [] and server.get('parent_writer_calls') == {}
            and server.get('writer_boundaries') == expected_boundaries
            and server.get('parent_writer_boundaries') == expected_boundaries
            and server.get('asgi_lifecycle') == dict(startup_failed=False, shutdown_failed=False, error_occurred=False)
            and type(server.get('child_exit_code')) is int and server['child_exit_code'] == 0),
        "measurement_window": window_valid,
        "scheduled_load": offered == {kind: ceil(client["seconds"] * rate) for kind, rate in
            (("health", 20), ("read", 5), ("fact", 2), ("dialogue", .1))},
        "complete_traffic": (len(client["health_ms"]) == offered["health"]
            and len(client["accepted_ms"]) == offered["read"] + offered["fact"]
            and len(client.get("business_ms", [])) == offered["read"] + offered["fact"]
            and len(client["fact_ms"]) == offered["fact"]
            and len(client["dialogue_ends"]) == offered["dialogue"]),
        "responses": all(metrics[key] is not None and 0 <= metrics[key] <= limit for key, limit in (
            ("health_p95_ms", 100), ("accepted_p95_ms", 100), ("fact_p95_ms", 1500),
            ("heartbeat_p99_ms", 50), ("window_p95_ms", 800))),
        "continuous_clock": (len(heartbeat_values) >= client["seconds"] * 100 - 1
            and len(window_values) >= max(1, int(client["seconds"]) - 1)
            and server["max_lag_windows"] <= 1 and server["final_backlog"] <= 1),
        "single_writer": (len(owner) == 1 and mutations == owner
            and server["max_writers"] == 1 and credit_valid
            and all(server.get("writer_calls", {}).get(name, 0) > 0 for name in
                ("gameplay_durable_append", "heavenly_graph_batch", "character_session_append_event"))),
        "provider_isolation": (server["provider_calls"] > 0 and bool(providers)
            and not owner.intersection(providers)
            and 1 <= server["provider_max_active"] <= 4 and server["windows_during_provider"] > 0),
        "dialogue_terminal": ("completed" in client["dialogue_ends"]
            and all(status in {"completed", "requeued", "cancelled"} for status in client["dialogue_ends"])),
        "no_errors": not client["errors"] and not server["errors"],
    }
    return dict(passed=all(checks.values()), checks=checks, metrics=metrics,
                formal_duration=client["seconds"] >= 120)


def raw_artifacts(directory: Path) -> dict:
    # 私有存档和短期启动凭据不进入可迁移证据。
    from hashlib import file_digest
    result = {}
    for path in directory.iterdir():
        if path.is_file() and path.name not in {"manifest.json", "manifest.json.tmp"}:
            with path.open('rb') as stream:
                result[path.name] = 'sha256:' + file_digest(stream, 'sha256').hexdigest()
    return result


def replay_responses(records: list[dict], client: dict) -> dict:
    """按定速发送记录和响应时刻重算客户端耗时，不读取 provider 正文或凭据。"""
    starts, request_ids, seen = {}, {}, set()
    admitted_at, completed_at = {}, {}
    values = dict(health_ms=[], accepted_ms=[], business_ms=[], fact_ms=[], dialogue_ends=[])
    origin, seconds = client["load_started_at"], client["seconds"]
    for kind, rate in (("health", 20), ("read", 5), ("fact", 2), ("dialogue", .1)):
        rows = [row for row in records if row["channel"] == kind
                and (kind == "health" or row.get("type") == "sent")]
        ordinals = [row["key"] if kind == "health" else row["ordinal"] for row in rows]
        if (any(type(value) is not int for value in ordinals)
                or sorted(ordinals) != list(range(ceil(seconds * rate)))):
            raise ValueError("service_raw_schedule_incomplete")
        for row, ordinal in zip(rows, ordinals):
            expected = origin + ordinal / rate
            actual = row["expected_at"]
            if type(actual) not in (int, float) or not isfinite(actual) or not isclose(actual, expected, rel_tol=0, abs_tol=1e-6):
                raise ValueError("service_raw_schedule_changed")
            at = row["completed_at"] if kind == "health" else row["sent_at"]
            if type(at) not in (int, float) or not isfinite(at) or at < expected:
                raise ValueError("service_raw_time_invalid")
            key = row["producer_ts"] if kind == "fact" else f"service-dialogue:{ordinal}" if kind == "dialogue" else ordinal
            if (kind, key) in starts:
                raise ValueError("service_raw_request_duplicate")
            starts[kind, key] = expected
            if kind in {"read", "fact"}:
                request_ids[kind, key] = f"service-{kind}:{ordinal}"
    for row in records:
        kind, category = row["channel"], row.get("type")
        if kind == "health":
            if row["status"] != "ok":
                raise ValueError("service_raw_health_failed")
            values["health_ms"].append((row["completed_at"] - starts[kind, row["key"]]) * 1000)
            continue
        if kind in {"read", "fact"} and category in {"runtime_admission", "runtime_completion", "ack", "spatial_access_runtime_state_snapshot"}:
            identity = kind, row["key"]
            if row.get("request_id") != request_ids.get(identity):
                raise ValueError("service_raw_request_binding_invalid")
            at = row["received_at"]
            if type(at) not in (int, float) or not isfinite(at):
                raise ValueError("service_raw_time_invalid")
            if category == "runtime_admission":
                admitted_at[identity] = at
            if category == "runtime_completion":
                if (row.get("status") != "owner_finished" or ("accepted_ms", identity) not in seen
                        or ("completion", identity) in seen or at < admitted_at[identity]):
                    raise ValueError("service_raw_completion_invalid")
                seen.add(("completion", identity))
                completed_at[identity] = at
            elif category == "ack" and row.get("accepted") is not True:
                raise ValueError("service_raw_business_rejected")
            if category in {"ack", "spatial_access_runtime_state_snapshot"} and completed_at.get(identity) != at:
                raise ValueError("service_raw_completion_time_mismatch")
        metric = ("accepted_ms" if category == "runtime_admission" and kind in {"read", "fact"}
                  else "business_ms" if category == "ack" and kind in {"read", "fact"}
                  else "fact_ms" if category == "spatial_access_runtime_state_snapshot" and kind == "fact"
                  else "dialogue_ends" if category == "dialogue_stream_end" and kind == "dialogue" else None)
        if metric is None:
            continue
        identity = kind, row["key"]
        if identity not in starts or (metric, identity) in seen:
            raise ValueError("service_raw_response_unknown_or_duplicate")
        seen.add((metric, identity))
        at = row["received_at"]
        if type(at) not in (int, float) or not isfinite(at) or at < starts[identity]:
            raise ValueError("service_raw_time_invalid")
        if metric == "accepted_ms" and row.get("accepted") is not True:
            raise ValueError("service_raw_request_rejected")
        values[metric].append(row["status"] if metric == "dialogue_ends" else (at - starts[identity]) * 1000)
    if any(("completion", identity) not in seen or ("business_ms", identity) not in seen for identity in request_ids):
        raise ValueError("service_raw_completion_missing")
    for key, actual in values.items():
        expected = client[key]
        if len(actual) != len(expected) or (actual != expected if key == "dialogue_ends" else
                any(not isclose(a, b, rel_tol=0, abs_tol=1e-6) for a, b in zip(actual, expected))):
            raise ValueError("service_raw_client_samples_mismatch")
    return values


def verify_artifacts(directory: Path, *, expected_commit: str) -> dict:
    def load(name):
        return read_json((directory / name).read_text(encoding="utf-8"))
    manifest = load("manifest.json")
    if (manifest.get("schema_version") != 1 or manifest.get("base_commit") != expected_commit
            or manifest.get("source") != source_manifest()
            or manifest.get("profile") != "population-service-isolation"):
        raise ValueError("service_evidence_identity_invalid")
    required = {"client.json", "server.json", "roster.json", "start", "stop", "responses.jsonl", "process.log",
                "parent-observed.json", "owner-observed.json", "owner-ready.json"}
    artifacts = raw_artifacts(directory)
    if not required.issubset(artifacts) or manifest.get("raw_artifacts") != artifacts:
        raise ValueError("service_evidence_raw_artifacts_invalid")
    client, server, roster = load("client.json"), load("server.json"), load("roster.json")
    if server != merge_process_observations(load('parent-observed.json'), load('owner-observed.json'), load('owner-ready.json')):
        raise ValueError('service_process_observations_summary_changed')
    from app.population_continuity.roster import PopulationRoster
    actors = PopulationRoster.model_validate(roster).actor_ids
    population, seconds = manifest["population"], manifest["seconds"]
    if (type(population) is not int or population not in (100, 1000, 10000)
            or len(actors) != population or server.get("population") != population
            or type(server.get("population")) is not int or server.get("window_size") != 1
            or type(seconds) is not int or seconds < 120 or client.get("seconds") != seconds
            or manifest.get("backend_exit_code") != 0 or type(manifest.get("backend_exit_code")) is not int
            or manifest.get("errors") != [] or manifest.get("passed") is not True
            or manifest.get("provider_mode") != "controlled_local_slow_not_live_proof"
            or server.get("provider_mode") != "controlled_local_one_second_delay"):
        raise ValueError("service_evidence_configuration_invalid")
    if load("start") != {key: client[key] for key in ("load_started_at", "load_ended_at")}:
        raise ValueError("service_evidence_interval_invalid")
    # 原始逐样本必须全部有限且非负；不能让百分位隐藏损坏值。
    for obj, names in ((client, ("health_ms", "accepted_ms", "fact_ms")),
                       (server, ("heartbeat_ms", "heartbeat_expected_at", "window_ms", "window_started_at"))):
        for name in names:
            values = obj[name]
            if not isinstance(values, list) or not values or any(
                    type(value) not in (int, float) or not isfinite(value) or value < 0 for value in values):
                raise ValueError("service_evidence_samples_invalid")
    for name in ("heartbeat_expected_at", "window_started_at"):
        if any(b <= a for a, b in zip(server[name], server[name][1:])):
            raise ValueError("service_evidence_sample_times_invalid")
    origin, end = client["load_started_at"], client["load_ended_at"]
    expected_heartbeats = [origin + ordinal * .01 for ordinal in range(1, ceil(seconds / .01))
        if origin + ordinal * .01 < end]
    tolerance = 1e-7
    if (len(server["heartbeat_expected_at"]) != len(expected_heartbeats)
            or any(abs(actual - expected) > tolerance
                for actual, expected in zip(server["heartbeat_expected_at"], expected_heartbeats))):
        raise ValueError("service_evidence_heartbeat_coverage_invalid")
    starts, durations = server["window_started_at"], server["window_ms"]
    windows = [(start, duration / 1000) for start, duration in zip(starts, durations) if origin <= start < end]
    # 同一 owner 串行计时；允许一窗调度偏差和负载末尾完成，排空起点不能填补覆盖。
    if (len(starts) != len(durations) or not windows
            or any(start + duration / 1000 > following + tolerance
                for start, duration, following in zip(starts, durations, starts[1:]))
            or any(not origin + index - tolerance <= start <= origin + index + 2 + tolerance
                for index, (start, _) in enumerate(windows))
            or windows[-1][0] + windows[-1][1] < end - 1 - tolerance):
        raise ValueError("service_evidence_window_coverage_invalid")
    replay_responses(list(json_lines(directory / "responses.jsonl")), client)
    result = evaluate(client, server)
    if not result["passed"] or any(manifest.get(key) != value for key, value in result.items()):
        raise ValueError("service_evidence_measurements_failed_or_summary_changed")
    return dict(**result, population=population, seconds=seconds, base_commit=expected_commit,
                godot_status="godot_unverified", provider_mode=manifest["provider_mode"])


async def backend(directory: Path) -> None:
    import os
    import uvicorn
    from app.services import runtime_process
    from scripts.verification.population_service_owner_probe import service_owner_child

    observed = dict(parent_pid=os.getpid(), heartbeat_ms=[], heartbeat_expected_at=[],
        queue_peak=None, parent_drained=None, parent_drained_at=None, writer_calls={}, errors=[])
    mutation_threads = set()
    lock = Lock()

    def writer(name, original):
        def invoke(*args, **kwargs):
            # parent 从装配前到实际 shutdown 都不应调用持久写入口。
            with lock:
                mutation_threads.add((os.getpid(), get_ident()))
                observed['writer_calls'][name] = observed['writer_calls'].get(name, 0) + 1
            return original(*args, **kwargs)
        return invoke

    with ExitStack() as stack, socket.socket() as listener:
        observed['writer_boundaries'] = install_writer_probes(stack, writer)
        main, actors, secret = _configure(directory / 'state', directory / 'roster.json')
        stack.enter_context(patch.object(runtime_process, 'CHILD_TARGET', service_owner_child))
        listener.bind(('127.0.0.1', 0))
        listener.listen(128)
        listener.setblocking(False)
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(main.app, ws=main.RUNTIME_WEBSOCKET_PROTOCOL, access_log=False, log_level='warning',
                               ws_per_message_deflate=False))
        serving = asyncio.create_task(server.serve(sockets=[listener]))
        heartbeat_task = None
        measuring = False
        host = None
        try:
            while not server.started:
                if serving.done():
                    await serving
                    raise RuntimeError('service_backend_start_failed')
                await asyncio.sleep(.02)
            host = main.app.state.runtime_process
            async with asyncio.timeout(90):
                while not (directory / 'owner-ready.json').exists():
                    if not host.process.is_alive():
                        raise RuntimeError('service_owner_exited')
                    await asyncio.sleep(.02)
            ready = await read_control(directory / 'owner-ready.json', loader=read_json)
            if (ready['owner_pid'] != host.process.pid or ready['population'] != len(actors)
                    or ready['window_size'] != 1):
                raise ValueError('service_fixture_driver_invalid')
            observed.update(child_pid=host.process.pid, population=len(actors), window_size=1)
            write_json(directory / 'ready.json', dict(port=port, secret=secret, population=len(actors)))
            while not (directory / 'start').exists():
                if serving.done() or not host.process.is_alive():
                    raise RuntimeError('service_backend_exited')
                await asyncio.sleep(.02)
            interval = await read_control(directory / 'start', loader=read_json)
            origin, load_end = interval['load_started_at'], interval['load_ended_at']
            if load_end <= origin:
                raise ValueError('service_load_interval_invalid')
            observed.update(interval)

            async def heartbeat():
                ordinal = 1
                while measuring:
                    expected = origin + ordinal * .01
                    if expected >= load_end:
                        break
                    await until(expected)
                    observed['heartbeat_expected_at'].append(expected)
                    observed['heartbeat_ms'].append(max(0., (perf_counter() - expected) * 1000))
                    ordinal += 1
            measuring = True
            heartbeat_task = asyncio.create_task(heartbeat())
            while perf_counter() < load_end and not (directory / 'stop').exists():
                if serving.done() or not host.process.is_alive():
                    raise RuntimeError('service_backend_exited')
                await asyncio.sleep(.02)
            observed['load_end_observed_at'] = perf_counter()
            if observed['load_end_observed_at'] < load_end:
                observed['errors'].append('service_load_interrupted')
            while not (directory / 'stop').exists():
                if serving.done() or not host.process.is_alive():
                    raise RuntimeError('service_backend_exited')
                await asyncio.sleep(.02)
            # child 先停实际人口 task 并完成原观察，随后再结束真实 ASGI lifespan。
            async with asyncio.timeout(35):
                while not (directory / 'owner-observed.json').exists():
                    if not host.process.is_alive():
                        raise RuntimeError('service_owner_exited')
                    await asyncio.sleep(.02)
            observed['parent_drained'] = await wait_for_process_drain(host)
            observed['parent_drained_at'] = perf_counter()
        except Exception as error:
            observed['errors'].append(type(error).__name__)
            raise
        finally:
            measuring = False
            if heartbeat_task is not None:
                await heartbeat_task
            server.should_exit = True
            try:
                await asyncio.wait_for(serving, 40)
            except Exception as error:
                observed['errors'].append(type(error).__name__)
                raise
            finally:
                lifecycle = getattr(server, 'lifespan', None)
                observed['asgi_lifecycle'] = {name: getattr(lifecycle, name, None) for name in
                    ('startup_failed', 'shutdown_failed', 'error_occurred')}
                if any(value is not False for value in observed['asgi_lifecycle'].values()):
                    observed['errors'].append('service_asgi_lifecycle_failed')
                write_json(directory / 'parent-qos.json', main.app.state.process_qos)
                observed['mutation_threads'] = sorted(mutation_threads)
                observed['child_exit_code'] = host.process.exitcode if host is not None else None
                if host is not None:
                    observed['execution_credit'] = host.snapshot()['execution_credit']
                    observed['queue_peak'] = observed['execution_credit']['peak']
                write_json(directory / 'parent-observed.json', observed)
                if (directory / 'owner-observed.json').exists() and (directory / 'owner-ready.json').exists():
                    owner = await read_control(directory / 'owner-observed.json', loader=read_json)
                    ready = await read_control(directory / 'owner-ready.json', loader=read_json)
                    write_json(directory / 'server.json', merge_process_observations(observed, owner, ready))
            if any(value is not False for value in observed['asgi_lifecycle'].values()):
                raise RuntimeError('service_asgi_lifecycle_failed')


async def load(directory: Path, seconds: int) -> dict:
    import httpx
    from websockets.asyncio.client import connect
    from scripts.launch_trusted_local_gameplay_mirror import request_enrollment
    ready = await read_control(directory / 'ready.json')
    http_url, ws_url = f'http://127.0.0.1:{ready["port"]}', f'ws://127.0.0.1:{ready["port"]}/ws'
    result = dict(seconds=seconds, offered={}, health_ms=[], accepted_ms=[], business_ms=[], fact_ms=[], dialogue_ends=[], errors=[])
    # 不保存凭据或模型正文；原始记录只有请求编号、状态和测量时间。
    records = []
    pending = {"read": {}, "fact": {}}
    completions = {}
    fact_started = {}
    dialogue_started = {}
    readers = []
    outstanding = set()
    async def receive(ws, kind):
        async for raw in ws:
            message = json.loads(raw)
            now = perf_counter()
            payload, message_type = message.get("payload", {}), message["message_type"]
            if message_type == "runtime_admission":
                request_id = payload["request_id"]
                key, expected = pending[kind].pop(request_id)
                if payload.get("accepted") is True:
                    result["accepted_ms"].append((now - expected) * 1000)
                    completions[request_id] = (kind, key, expected)
                else:
                    result["errors"].append(f'{kind}:{key}:{payload.get("reason")}')
                records.append(dict(channel=kind, type=message_type, received_at=now,
                    key=key, request_id=request_id, accepted=payload.get("accepted")))
                continue
            if message_type == "runtime_completion":
                request_id = payload["request_id"]
                expected_kind, key, expected = completions.pop(request_id)
                if expected_kind != kind or payload["status"] != "owner_finished":
                    raise ValueError("service_completion_binding_invalid")
                records.append(dict(channel=kind, type=message_type, received_at=now,
                    key=key, request_id=request_id, status=payload["status"]))
                messages = payload["messages"]
            else:
                request_id, key, messages = None, None, [message]
            for message in messages:
                payload = message.get("payload", {})
                message_type = message["message_type"]
                correlated_key = key
                if message_type == "ack" and request_id is not None:
                    result["business_ms"].append((now - expected) * 1000)
                    if payload.get("accepted") is not True:
                        result["errors"].append(f'{kind}:{key}:{payload.get("route")}')
                elif kind == "fact" and message_type == "spatial_access_runtime_state_snapshot":
                    if key != payload["updated_at"]:
                        raise ValueError("service_fact_request_binding_invalid")
                    if key in fact_started:
                        if payload["actor_id"] != "char_b" or payload["current_zone_id"] != "zone_focus":
                            result["errors"].append("fact_authority_result_mismatch")
                        result["fact_ms"].append((now - fact_started.pop(key)) * 1000)
                elif message_type == "dialogue_stream_end":
                    correlated_key = payload.get("request_id")
                    if correlated_key in dialogue_started:
                        dialogue_started.pop(correlated_key)
                        result["dialogue_ends"].append(payload.get("status"))
                records.append(dict(channel=kind, type=message_type, received_at=now,
                    key=correlated_key, request_id=request_id, status=payload.get("status"),
                    route=payload.get("route"), accepted=payload.get("accepted") if message_type == "ack" else None))

    async with httpx.AsyncClient(timeout=5., trust_env=False) as http:
        async with connect(ws_url, compression=None) as read_ws, connect(ws_url, compression=None) as fact_ws, connect(ws_url, compression=None) as dialogue_ws:
            for ws in (read_ws, fact_ws, dialogue_ws):
                enrollment = await asyncio.to_thread(request_enrollment, backend_http_url=http_url,
                    launch_profile_ref="population-cost-probe", launcher_secret=ready["secret"])
                await ws.send(json.dumps(dict(message_type="websocket_session_bind", payload=enrollment.model_dump(mode="json"))))
                while True:
                    response = json.loads(await asyncio.wait_for(ws.recv(), 10))
                    if response["message_type"] == "websocket_session_bound":
                        break
                    if response.get("payload", {}).get("accepted") is False:
                        raise ValueError("service_probe_bind_rejected")
            for ws, kind in ((read_ws, "read"), (fact_ws, "fact"), (dialogue_ws, "dialogue")):
                readers.append(asyncio.create_task(receive(ws, kind)))
            # 同机 perf_counter 为跨进程同钟；先公布固定区间，双方使用同一绝对截止。
            origin = perf_counter() + .1
            result.update(load_started_at=origin, load_ended_at=origin + seconds)
            write_json(directory / "start", {key: result[key] for key in ("load_started_at", "load_ended_at")})
            async def health(expected, ordinal):
                try:
                    response = await http.get(http_url + "/health")
                    if response.status_code != 200 or response.json()["status"] != "ok":
                        raise ValueError("unhealthy_response")
                    completed = perf_counter()
                    result["health_ms"].append((completed - expected) * 1000)
                    records.append(dict(channel="health", key=ordinal, expected_at=expected,
                                        completed_at=completed, status="ok"))
                except Exception as error:
                    result["errors"].append(f"health:{ordinal}:{type(error).__name__}")
            async def send_kind(kind, rate, ws=None):
                count = ceil(seconds * rate)
                result["offered"][kind] = count
                for ordinal in range(count):
                    expected = origin + ordinal / rate
                    await until(expected)
                    if kind == "health":
                        if len(outstanding) >= 128:
                            result["errors"].append("probe_http_capacity")
                            continue
                        task = asyncio.create_task(health(expected, ordinal))
                        outstanding.add(task)
                        task.add_done_callback(outstanding.discard)
                        continue
                    if kind in pending and len(pending[kind]) >= 128:
                        result["errors"].append(f"probe_{kind}_capacity")
                        continue
                    timestamp = int(time() * 1000)
                    if kind == "read":
                        payload = dict(message_type="character_actor_status", payload={"actor_id": "char_a"})
                        pending[kind][f"service-{kind}:{ordinal}"] = (ordinal, expected)
                    elif kind == "fact":
                        fact_started[timestamp] = expected
                        pending[kind][f"service-{kind}:{ordinal}"] = (timestamp, expected)
                        payload = dict(message_type="raw_fact_event", payload=dict(
                            event_type="raw_fact_event", fact_family="spatial_access_fact", fact_type="actor_entered_zone",
                            producer_ts=timestamp, room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
                            source=dict(system="godot.raw_fact_emitter", actor_id="char_b"), targets={},
                            causation_id=f"service-fact:{ordinal}", correlation_id=f"service-fact:{ordinal}"))
                    else:
                        key = f"service-dialogue:{ordinal}"
                        dialogue_started[key] = expected
                        payload = dict(message_type="player_input", payload=dict(
                            player_id="p1", room_id="room_demo", actor_id="char_c", intent_type="dialogue_submit",
                            producer_ts=timestamp, target_actor_id="char_a", content="Hello", request_id=key))
                    if kind in pending:
                        payload = dict(message_type="runtime_enqueue", payload=dict(
                            request_id=f"service-{kind}:{ordinal}", command=payload))
                    await asyncio.wait_for(ws.send(json.dumps(payload)), 5)
                    records.append(dict(channel=kind, ordinal=ordinal, type="sent", expected_at=expected,
                                        sent_at=perf_counter(), producer_ts=timestamp))
            try:
                await asyncio.gather(send_kind("health", 20), send_kind("read", 5, read_ws),
                                     send_kind("fact", 2, fact_ws), send_kind("dialogue", .1, dialogue_ws))
                await until(origin + seconds)
                if outstanding:
                    await asyncio.gather(*outstanding)
                deadline = perf_counter() + 15
                while (pending["read"] or pending["fact"] or completions or fact_started or dialogue_started) and perf_counter() < deadline:
                    if any(task.done() for task in readers):
                        raise RuntimeError("service_probe_reader_exited")
                    await asyncio.sleep(.02)
                if pending["read"] or pending["fact"] or completions or fact_started or dialogue_started:
                    result["errors"].append("service_probe_incomplete_responses")
            finally:
                try:
                    # 先完成客户端 Close 与 reader 收口，避免 stop 触发服务端 1012 抢先关闭。
                    for ws in (read_ws, fact_ws, dialogue_ws):
                        await ws.close()
                    for task in readers:
                        try:
                            await task
                        except Exception as error:
                            result["errors"].append(f"reader:{type(error).__name__}")
                finally:
                    (directory / "stop").touch()
                write_json(directory / "client.json", result)
                (directory / "responses.jsonl").write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
    return result


def collect(directory: Path, population: int, seconds: int) -> dict:
    directory.mkdir(parents=True, exist_ok=False)
    report = None
    try:
        with recorded_high_qos(directory / 'collector-qos.json'):
            report = _collect(directory, population, seconds)
        return report
    finally:
        if directory.exists():
            path = directory / 'manifest.json'
            if path.exists():
                final = json.loads(path.read_text(encoding='utf-8'))
                if sys.exc_info()[0] is not None:
                    final['passed'] = False
                    final.setdefault('errors', []).append('collection_scope:' + sys.exc_info()[0].__name__)
                final['raw_artifacts'] = raw_artifacts(directory)
                write_json(path, final)
                if report is not None:
                    report.update(final)


def _collect(directory: Path, population: int, seconds: int) -> dict:
    (directory / "state").mkdir()
    write_json(directory / "roster.json", dict(actor_ids=["char_a", "char_b", "char_c",
        *(f"resident_{i:05d}" for i in range(population - 3))]))
    report = dict(schema_version=1, profile="population-service-isolation", population=population,
        seconds=seconds, base_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        source=source_manifest(), started_at=datetime.now(timezone.utc).isoformat(), passed=False,
        godot_status="godot_unverified", provider_mode="controlled_local_slow_not_live_proof", errors=[])
    try:
        with (directory / "process.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--backend-child", str(directory)],
                cwd=ROOT, env=child_environment(), stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = perf_counter() + 90
                while not (directory / "ready.json").exists():
                    if process.poll() is not None or perf_counter() > deadline:
                        raise RuntimeError("service_probe_backend_not_ready")
                    sleep(.05)
                client = asyncio.run(load(directory, seconds))
                process.wait(timeout=60)
                report["backend_exit_code"] = process.returncode
                server = json.loads((directory / "server.json").read_text(encoding="utf-8"))
                originals = [read_json((directory / name).read_text(encoding='utf-8')) for name in
                    ('parent-observed.json', 'owner-observed.json', 'owner-ready.json')]
                if server != merge_process_observations(*originals):
                    raise ValueError('service_process_observations_summary_changed')
                if process.returncode:
                    report["errors"].append("backend_nonzero_exit")
                replay_responses([json.loads(line) for line in
                    (directory / "responses.jsonl").read_text(encoding="utf-8").splitlines()], client)
                report.update(evaluate(client, server))
                if source_manifest() != report["source"]:
                    report["errors"].append("service_probe_source_changed")
                report["passed"] = report["passed"] and not report["errors"]
            finally:
                (directory / "stop").touch()
                if process.poll() is None:
                    try:
                        process.wait(timeout=45)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
    except Exception as error:
        report["errors"].append(type(error).__name__)
        report["passed"] = False
    finally:
        # bootstrap secret只在本次两个进程间使用，不进入可分享证据。
        (directory / "ready.json").unlink(missing_ok=True)
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["raw_artifacts"] = raw_artifacts(directory)
        write_json(directory / "manifest.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--population", type=int, choices=(100, 1000, 10000), nargs="+", default=[100, 1000])
    parser.add_argument("--seconds", type=int, default=120)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--backend-child", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--verify-artifacts", type=Path, help="离线复验一档至少120秒的原始服务隔离证据")
    parser.add_argument("--require-fresh-commit")
    args = parser.parse_args()
    if args.verify_artifacts:
        if not args.require_fresh_commit:
            parser.error("--verify-artifacts requires --require-fresh-commit")
        result = verify_artifacts(args.verify_artifacts.resolve(), expected_commit=args.require_fresh_commit)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.backend_child:
        asyncio.run(backend(args.backend_child))
        return 0
    if args.seconds < 1:
        parser.error("seconds must be positive")
    # run_scope/attempt已提供唯一目录，重复profile名和时间戳会挤占Windows存档路径长度。
    root = args.output or collection_output_path(ROOT, "service")
    rows = [collect((root / str(population)).resolve(), population, args.seconds) for population in args.population]
    overall = all(row["passed"] for row in rows)
    report = dict(profile="population-service-isolation", overall_passed=overall,
                  formal_matrix=sorted(args.population) == [100, 1000] and args.seconds >= 120,
                  godot_status="godot_unverified", cases=[str((root / str(n) / "manifest.json").resolve()) for n in args.population])
    write_json(collection_report_path(ROOT, root, "population-service-isolation-report.json"), report)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
