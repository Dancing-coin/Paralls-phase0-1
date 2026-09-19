"""真实 main 冷进程恢复门禁；造档、正常 ready 和完整历史核对分别计量。"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from contextlib import ExitStack
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
from time import perf_counter, perf_counter_ns
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from scripts.verification.population_benchmark_metrics import (
    SqliteReadMeter, implementation_digest, peak_rss_bytes, percentile,
)
from scripts.verification.population_godot_runner import source_manifest, write_json
from scripts.verification.verify_population_godot_runtime import read_json, digest as file_digest


def digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


class StartupInstrumentation(ExitStack):
    """只包装实际调用；不跳过生产工作，不记录 provider 配置或业务 payload。"""

    def __enter__(self):
        super().__enter__()
        self.sql = self.enter_context(SqliteReadMeter())
        self.calls = Counter()
        self.times = Counter()
        self.publishers = []
        from pydantic import BaseModel
        from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
        from app.character_agent.storage.session_store import CharacterAgentSessionStore
        from app.character_agent.storage.memory_store import CharacterAgentMemoryStore
        from app.character_agent.storage.graph_memory_store import CharacterGraphMemoryStore
        from app.population_continuity.runtime_publication import RuntimeCadencePublisher
        from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter

        for cls, methods in (
            (CharacterAgentRuntime, ("__init__", "_rehydrate_graph_continuity", "_rehydrate_runtime_state_from_timeline", "_update_memory_scene_knowledge")),
            (CharacterAgentSessionStore, ("__init__", "list_events", "read_events_page")),
            (CharacterAgentMemoryStore, ("write_event",)),
            (CharacterGraphMemoryStore, ("write_event",)),
            (SQLiteHeavenlyGraphAdapter, ("__init__",)),
            (RuntimeCadencePublisher, ("__init__", "_restore")),
        ):
            for method in methods:
                original = getattr(cls, method)
                name = f"{cls.__name__}.{method}"

                def observe(instance, *args, _method=original, _name=name, **kwargs):
                    started = perf_counter()
                    self.calls[_name] += 1
                    try:
                        result = _method(instance, *args, **kwargs)
                        if _name == "RuntimeCadencePublisher.__init__":
                            self.publishers.append(instance)
                        return result
                    finally:
                        self.times[_name] += (perf_counter() - started) * 1000

                self.enter_context(patch.object(cls, method, observe))

        # 顶层反序列化入口数不是嵌套模型数，报告明确保留此口径。
        for method in ("model_validate", "model_validate_json"):
            original = getattr(BaseModel, method).__func__

            def decode(cls, *args, _method=original, _name=method, **kwargs):
                self.calls[f"decode:{cls.__name__}.{_name}"] += 1
                return _method(cls, *args, **kwargs)

            self.enter_context(patch.object(BaseModel, method, classmethod(decode)))
        for method in ("read_text", "read_bytes"):
            original = getattr(Path, method)

            def read(path, *args, _method=original, **kwargs):
                result = _method(path, *args, **kwargs)
                if any(part.endswith(".character-agent") for part in path.parts):
                    # 固定迁移标记也如实计量，但它不包含历史事件。
                    prefix = "session_marker" if path.name == "character_sessions.migrated" else "legacy_session_file"
                    self.calls[f"{prefix}_reads"] += 1
                    self.calls[f"{prefix}_bytes"] += len(result.encode("utf-8") if isinstance(result, str) else result)
                return result

            self.enter_context(patch.object(Path, method, read))
        return self

    def snapshot(self) -> dict[str, object]:
        return {
            "sql": self.sql.snapshot(), "calls": dict(self.calls), "phase_ms": dict(self.times),
            "phase_times_are_inclusive": True,
            "decode_unit": "top-level model_validate/model_validate_json calls; nested models are not separately counted",
            "replayed_windows": [publisher.replayed_windows for publisher in self.publishers],
            "publisher_record_cache": [len(publisher._records) for publisher in self.publishers],
        }


def pending_state(store) -> dict[str, object]:
    """在 ready 截面外核对稳定身份及状态，包含被未交付 outbox 阻塞的刷新义务。"""
    outbox = [entry.model_dump(mode="json") for entry in sorted(
        store.list_outbox(include_delivered=False), key=lambda entry: entry.outbox_id,
    )]
    refresh = store._rows("SELECT transaction_id, refresh_state FROM transactions WHERE refresh_state='pending' ORDER BY transaction_id")
    return {name: {"count": len(rows), "digest": digest(rows)}
            for name, rows in (("outbox", outbox), ("projection_refresh", refresh))}


def state_oracle(main, driver, audit_directory: Path, *, owner: bool = False) -> dict[str, object]:
    """完整历史核对明确发生在 ready 计时/计数截面之外。"""
    from app.gameplay.inventory_runtime import InventoryProjector
    from scripts.verification.population_ask_audit import write_audit

    runtime = main.character_agent_runtime
    actors = {}
    for actor_id in ("char_a", "char_b"):
        timeline = runtime.get_session_timeline(actor_id)
        actors[actor_id] = {
            "session_count": runtime.get_memory_revision(actor_id),
            "session_digest": digest(timeline),
            "session_head": timeline[-1]["event_id"] if timeline else None,
            "dynamic": runtime.get_dynamic_state(actor_id),
            "need": runtime.get_need_tension_state(actor_id),
            "goal": runtime.get_goal_state(actor_id),
            "goal_history": runtime.get_goal_state_history(actor_id),
            "unresolved_tensions": runtime.get_unresolved_tensions(actor_id),
            "supervision": runtime.get_supervision_state(actor_id),
            "agenda": runtime.get_background_agenda_state(actor_id),
            "continuity": runtime.get_runtime_continuity_state(actor_id),
            "continuity_revision": runtime.get_continuity_revision(actor_id),
            "seed_projection": runtime.get_seed_projection(actor_id),
            "candidates_digest": digest(runtime.get_pending_seed_candidates(actor_id)),
            "old_continuity_receipt": runtime._session_store.read_receipt(actor_id, kind="continuity", key="recovery-probe:continuity:1"),
            "working_memory": runtime.get_working_memory_state_record(actor_id).model_dump(mode="json"),
            "memory_bundle_digest": digest(runtime.get_memory_bundle(actor_id)),
            "knowledge": write_audit(runtime._session_store, actor_id, audit_directory / ask_audit_name(actor_id, owner=owner)),
        }
    store = main.gameplay_event_store
    # 全账本 digest 及旧幂等结果证明 ready 没有丢事实或改旧收据。
    events = store.read_events()
    authority = [event.model_dump(mode="json") for event in events]
    inventory = InventoryProjector(main.inventory_definition_registry).rebuild("character:char_a", events)
    turns = {}
    for actor in ("char_a", "char_b"):
        for ordinal in (1, driver.current_tick // driver.window_size):
            node_id = f"behavior-turn:recovery-probe:{actor}:{ordinal}:turn"
            node = main.heavenly_graph.get_node(node_id=node_id, scope=main.actor_private_scope(actor), valid_at=2**63 - 1)
            if node is None:
                raise ValueError("fixture_behavior_turn_missing")
            turns[node_id] = node.model_dump(mode="json")
    return {
        "population": driver.world_runtime.export_recovery_state(),
        "confirmed_tick": driver.current_tick, "actors": actors,
        "authority_digest": digest(authority), "authority_events": len(authority),
        "pending": pending_state(store),
        "stream_heads": store.get_stream_heads(),
        "behavior_turns": turns,
        "inventory": {"items": {key: asdict(value) for key, value in inventory.items.items()},
                      "containers": {key: asdict(value) for key, value in inventory.containers.items()},
                      "locations": dict(inventory.locations), "projection_revision": inventory.projection_revision,
                      "source_revision_vector": dict(inventory.source_revision_vector)},
        "old_cadence": store.get_by_idempotency("world_runtime.cadence", f"population-runtime:cadence:{driver.world_runtime.mode.world_ref}:0").model_dump(mode="json"),
    }


def recovery_owner_child(commands, controls, results, notifications, settings_json):
    """在原 owner 装配边界计量恢复；完整 oracle 等待 parent 发布 ready 后再运行。"""
    from app.services.runtime_process import runtime_child_main
    output = Path(sys.argv[sys.argv.index('--ready-child') + 1])
    started = perf_counter()
    task = None
    with StartupInstrumentation() as meter:
        from app import main
        original_startup = main._start_population_runtime_on_startup
        original_shutdown = main._stop_population_runtime_on_shutdown

        async def verify(driver, population_task, ready):
            try:
                try:
                    await population_task
                except asyncio.CancelledError:
                    pass
                while not output.with_suffix('.verify').exists():
                    await asyncio.sleep(.02)
                verification_started = perf_counter()
                ready['caches'] = await asyncio.wrap_future(main.runtime_execution.submit(lambda: ready_caches(main, driver)))
                oracle = await asyncio.wrap_future(main.runtime_execution.submit(lambda: state_oracle(main, driver, output.parent, owner=True)))
                write_json(output.with_suffix('.owner-result.json'), dict(ready=ready, oracle=oracle,
                    verification_ms=(perf_counter() - verification_started) * 1000))
            except BaseException as error:
                write_json(output.with_suffix('.owner-result.json'), dict(owner_pid=os.getpid(), error=type(error).__name__))
                raise

        async def startup():
            nonlocal task
            await original_startup()
            driver, population_task = main._population_runtime_driver, main._population_runtime_task
            if driver is None or population_task is None:
                raise RuntimeError('population_ready_driver_missing')
            # startup 返回后尚未再次 await；不让正常 driver 偷跑一个恢复窗口。
            population_task.cancel()
            ready = dict(restore_ms=(perf_counter() - started) * 1000,
                process_peak_rss_bytes=peak_rss_bytes(), owner_pid=os.getpid(), **meter.snapshot())
            write_json(output.with_suffix('.owner-ready.json'), ready)
            task = asyncio.create_task(verify(driver, population_task, ready))

        async def shutdown():
            if task is not None and not task.done():
                task.cancel()
            try:
                if task is not None:
                    await task
            finally:
                await original_shutdown()

        with patch.object(main, '_start_population_runtime_on_startup', startup), patch.object(
                main, '_stop_population_runtime_on_shutdown', shutdown):
            try:
                runtime_child_main(commands, controls, results, notifications, settings_json)
            finally:
                from app.services.process_qos import process_qos_snapshot
                write_json(output.with_suffix('.owner-qos.json'), process_qos_snapshot())


async def ready_child(output: Path) -> None:
    try:
        await _ready_child_with_policy(output)
    finally:
        from app.services.process_qos import process_qos_snapshot
        write_json(output.with_suffix('.parent-qos.json'), process_qos_snapshot())


async def _ready_child_with_policy(output: Path) -> None:
    database = Path(os.environ["PARALLS_HEAVENLY_GRAPH_PATH"])
    expected_implementation = json.loads((database.parent / "manifest.json").read_text(encoding="utf-8"))["implementation_digest"]
    if implementation_digest(ROOT) != expected_implementation:
        raise ValueError("fixture_implementation_changed_before_ready")
    started = perf_counter()
    from app.services import runtime_process
    with patch.object(runtime_process, 'CHILD_TARGET', recovery_owner_child):
        from app import main
        async with main.app.router.lifespan_context(main.app):
            host = main.app.state.runtime_process
            async def read_owner(suffix, timeout):
                from scripts.verification.verify_population_mixed_soak import read_control
                path = output.with_suffix(suffix)
                async with asyncio.timeout(timeout):
                    while not path.exists():
                        if not host.process.is_alive():
                            raise RuntimeError('recovery_owner_exited')
                        await asyncio.sleep(.02)
                return await read_control(path, loader=read_json)
            owner_ready = await read_owner('.owner-ready.json', 120)
            if owner_ready['owner_pid'] != host.process.pid:
                raise ValueError('recovery_owner_identity_invalid')
            parent_peak = peak_rss_bytes()
            ready = dict(owner_ready, parent_pid=os.getpid(), owner_restore_ms=owner_ready['restore_ms'],
                restore_ms=(perf_counter()-started)*1000, parent_peak_rss_bytes=parent_peak,
                owner_peak_rss_bytes=owner_ready['process_peak_rss_bytes'],
                process_peak_rss_bytes=parent_peak+owner_ready['process_peak_rss_bytes'],
                rss_scope='sum_of_parent_and_owner_startup_peaks')
            print('POPULATION_READY ' + json.dumps(ready, separators=(',', ':')), flush=True)
            output.with_suffix('.verify').touch()
            owner_result = await read_owner('.owner-result.json', 900)
            result = _merge_owner_result(ready, owner_ready, owner_result)
        result['runtime_process'] = dict(parent_pid=os.getpid(), owner_pid=host.process.pid, exit_code=host.process.exitcode)
        if host.process.exitcode != 0:
            raise RuntimeError('recovery_owner_shutdown_failed')
    if implementation_digest(ROOT) != expected_implementation:
        raise ValueError("implementation_changed_during_ready")
    write_json(output, result)


def _merge_owner_result(parent_ready: dict, owner_ready: dict, owner_result: dict) -> dict:
    # 原 owner 记录逐项绑定 parent 的计时/RSS 包装；不从汇总反推原子进程证据。
    if (owner_result.get('error') or set(owner_result) != {'ready', 'oracle', 'verification_ms'}
            or {key: value for key, value in owner_result['ready'].items() if key != 'caches'} != owner_ready):
        raise ValueError('recovery_owner_result_invalid')
    ready = dict(owner_ready, parent_pid=parent_ready['parent_pid'],
        owner_restore_ms=owner_ready['restore_ms'], restore_ms=parent_ready['restore_ms'],
        parent_peak_rss_bytes=parent_ready['parent_peak_rss_bytes'],
        owner_peak_rss_bytes=owner_ready['process_peak_rss_bytes'],
        process_peak_rss_bytes=parent_ready['parent_peak_rss_bytes'] + owner_ready['process_peak_rss_bytes'],
        rss_scope='sum_of_parent_and_owner_startup_peaks')
    if ready != parent_ready:
        raise ValueError('recovery_owner_ready_binding_invalid')
    ready['caches'] = owner_result['ready']['caches']
    return dict(ready=ready, oracle=owner_result['oracle'], verification_ms=owner_result['verification_ms'])


def ready_caches(main, driver) -> dict[str, object]:
    runtime, graph = main.character_agent_runtime, main.heavenly_graph
    memory = runtime._memory_store
    return {
        "graph": {name: len(getattr(graph, name)) for name in ("_nodes", "_relations", "_idempotency", "_checkpoints", "_branch_markers")},
        "gameplay": {name: len(getattr(main.gameplay_event_store, name)) for name in ("_events", "_transactions", "_outbox")},
        "session_events": sum(map(len, runtime._session_store._events_by_actor.values())),
        "light_memory_events": sum(map(len, memory._light._events_by_actor.values())),
        "heavy_normalizer_events": sum(map(len, memory._graph._normalizer._events_by_actor.values())),
        "population_receipts": len(driver.world_runtime._confirmed_receipts),
        "population_fingerprints": len(driver.world_runtime._confirmed_fingerprints),
    }


def child_environment(database: Path, roster: Path) -> dict[str, str]:
    return dict(os.environ, PYTHONPATH=str(ROOT / "backend"), PYTHONUTF8="1",
                PARALLS_HEAVENLY_GRAPH_PATH=str(database.resolve()),
                POPULATION_ROSTER_PATH=str(roster.resolve()),
                CHARACTER_MODEL_PROVIDER_KIND="local", SIMING_LLM_MODE="disabled", POPULATION_RUNTIME_PROFILE="production",
                CHARACTER_GRAPH_REQUIRE_CONTINUITY="0")


def authority_digest(database: Path) -> str:
    """维护允许完整扫描，包含 outbox、transaction 的所有字段，不只比较 event ID。"""
    result = hashlib.sha256()
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        for table, order in (("events", "global_sequence"), ("transactions", "sequence"),
                             ("outbox", "id"), ("stream_heads", "stream_id"), ("metadata", "key")):
            result.update(table.encode())
            for row in connection.execute(f"SELECT * FROM {table} ORDER BY {order}"):
                result.update(json.dumps(row, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
                result.update(b"\n")
    return "sha256:" + result.hexdigest()


def backup_archive(database: Path, destination: Path) -> dict[str, str]:
    """持有同一 runtime lease 后调用；逐库 backup 包含 WAL 中的已提交内容。"""
    destination.mkdir(parents=True, exist_ok=False)
    files = [database, database.with_name(database.name + ".gameplay.json"),
             database.with_name(database.stem + ".harness-task-ledger.sqlite3"),
             database.with_name(database.stem + ".harness-capabilities.sqlite3")]
    session = database.with_name(database.name + ".character-agent")
    if session.is_dir():
        files.extend(path for path in session.rglob("*") if path.is_file()
                     and not path.name.endswith(("-wal", "-shm")))
    copied = {}
    for source in files:
        if not source.exists():
            continue
        target = destination / source.relative_to(database.parent)
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as stream:
            is_database = stream.read(16) == b"SQLite format 3\x00"
        if is_database:
            with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as origin:
                with sqlite3.connect(target) as backup:
                    origin.backup(backup)
        else:
            shutil.copy2(source, target)
        copied[str(source.relative_to(database.parent))] = str(target)
    return copied


def rebuild_population_copy(database: Path, *, mode, roster) -> list:
    """仅在备份的工作副本重放已交付前缀；复用生产核验/确认，不发布外部消息。"""
    from app.gameplay.event_store import DurableGameplayEventStore
    from app.population_continuity.runtime_publication import RuntimeCadencePublisher
    from app.population_continuity.world import WorldContinuityRuntime
    from app.services.authority_event_bus import InMemoryAuthorityEventBus

    projectors = (f"population-recovery:{mode.world_ref}", f"population-receipt:{mode.world_ref}")
    with sqlite3.connect(database) as connection:
        connection.execute("DELETE FROM checkpoints WHERE projector_id IN (?,?)", projectors)
    store = DurableGameplayEventStore(database)
    # 全量旧存档验证在显式维护阶段进行，不混入正常 ready。
    store.audit()

    class OfflineRebuild(RuntimeCadencePublisher):
        def _restore(self):
            revision = 0
            expected_start = 0
            pending = False
            while events := self.store.read_stream(self.stream_id, from_revision=revision + 1, limit=128):
                for event in events:
                    cadence = self._validate_record(event.payload)
                    if event.stream_revision != revision + 1 or cadence.window_start != expected_start:
                        raise ValueError("population_cadence_history_gap")
                    revision = event.stream_revision
                    expected_start = cadence.window_end
                    outbox = self.store.get_outbox(f"outbox:population-runtime:{cadence.cadence_id}")
                    if outbox.event_id != event.event_id or outbox.transaction_id != event.transaction_id:
                        raise ValueError("population_cadence_outbox_anchor")
                    if outbox.delivery_state != "delivered":
                        pending = True
                        continue
                    if pending:
                        raise ValueError("population_cadence_delivery_gap")
                    self._event_from_record(event.payload)
                    self._confirm(cadence, event.payload)

    world = WorldContinuityRuntime(store=store, mode=mode, roster=roster)
    OfflineRebuild(world_runtime=world, event_bus=InMemoryAuthorityEventBus(), room_id="", scene_id="", zone_id="")
    from app.gameplay.models import ProjectionCheckpoint
    with sqlite3.connect(database) as connection:
        return [ProjectionCheckpoint.model_validate_json(row[0]) for row in connection.execute(
            "SELECT value FROM checkpoints WHERE projector_id IN (?,?) ORDER BY global_sequence,id", projectors,
        )]


def maintain_archive(database: Path, *, mode, roster, output: Path, rebuild: bool) -> dict[str, object]:
    from app.gameplay.event_store import DurableGameplayEventStore
    from app.population_continuity.recovery import parse_population_checkpoint
    from app.population_continuity.world import WorldContinuityRuntime
    from app.population_continuity.runtime_publication import RuntimeCadencePublisher
    from app.services.authority_event_bus import InMemoryAuthorityEventBus
    from app.world_runtime.storage_lease import RuntimeStorageLease

    database = database.resolve(strict=True)
    gameplay = database.with_name(database.name + ".gameplay.json")
    output = output.resolve()
    started = perf_counter()
    with RuntimeStorageLease(database):
        before = authority_digest(gameplay)
        backups = backup_archive(database, output / "backup")
        working = output / "rebuild.sqlite3"
        shutil.copy2(Path(backups[gameplay.name]), working)
        report = {"action": "rebuild-checkpoint" if rebuild else "audit-store", "backups": backups,
                  "authority_digest_before": before, "godot_status": "godot_unverified"}
        if rebuild:
            checkpoints = rebuild_population_copy(working, mode=mode, roster=roster)
        store = DurableGameplayEventStore(working)
        if not rebuild:
            store.audit()
        world = WorldContinuityRuntime(store=store, mode=mode, roster=roster)
        for checkpoint in store.list_projection_checkpoints():
            if checkpoint.projector_id in (f"population-recovery:{mode.world_ref}", f"population-receipt:{mode.world_ref}"):
                parse_population_checkpoint(world, checkpoint)
        # 副本复用真实恢复入口，验证可用检查点、tail 上限与交付连续性；不会发布消息。
        publisher = RuntimeCadencePublisher(world_runtime=world, event_bus=InMemoryAuthorityEventBus(),
                                            room_id="", scene_id="", zone_id="")
        report["startup_recovery"] = {"confirmed_tick": publisher.confirmed_tick,
                                      "replayed_windows": publisher.replayed_windows}
        if rebuild:
            # 一次提交替换派生行，故障不能留下半套新 checkpoint。
            projectors = (f"population-recovery:{mode.world_ref}", f"population-receipt:{mode.world_ref}")
            with sqlite3.connect(gameplay) as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("DELETE FROM checkpoints WHERE projector_id IN (?,?)", projectors)
                connection.executemany("INSERT INTO checkpoints(id,value,projector_id,global_sequence) VALUES(?,?,?,?)", [
                    (checkpoint.checkpoint_id, checkpoint.model_dump_json(), checkpoint.projector_id, checkpoint.last_global_sequence)
                    for checkpoint in checkpoints
                ])
            report["rebuilt_checkpoints"] = len(checkpoints)
        after = authority_digest(gameplay)
        if before != after:
            raise RuntimeError("maintenance_changed_authority")
        report.update(authority_digest_after=after, passed=True, elapsed_ms=(perf_counter() - started) * 1000)
        (output / "maintenance.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report


def fixture_window(main, driver, ordinal: int) -> None:
    from app.character_agent.models.simulation_seed import CharacterContinuityCommand, CharacterMemoryCandidate
    from app.models.character_perceived import CharacterPerceivedEvent
    from app.models.behavior_turn import BEHAVIOR_TURN_STAGE_ORDER, BehaviorTurnRecordRequest, BehaviorTurnStageRecord
    from app.models.siming_heavenly_graph import GraphProvenance, GraphRevisionVector
    from app.services.behavior_turn_recorder import BehaviorTurnRecorder

    result = driver.tick(driver.current_tick + driver.window_size)
    if result.rejected_windows or len(result.published_cadence_ids) != 1:
        raise RuntimeError(f"fixture_window_rejected:{result}")
    timestamp = driver.current_tick
    runtime = main.character_agent_runtime
    for actor_id in ("char_a", "char_b"):
        source = f"recovery-probe:{actor_id}:{ordinal}"
        runtime.record_character_perceived_event_without_cognition(CharacterPerceivedEvent(
            actor_id=actor_id, percept_channel="visual", producer_ts=timestamp,
            room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
            perceived_summary=f"观察到箱子状态 {ordinal % 2}", source_candidate_event_id=source,
            target_object_id="obj_crate", fact_claim={
                "scope_ref": "room_demo", "subject_ref": "obj_crate", "predicate": "state",
                "value": str(ordinal % 2), "valid_at": timestamp, "source_ref": source,
            },
        ))
        runtime.record_settlement_result(actor_id=actor_id, producer_ts=timestamp, payload={
            "result_id": source + ":settlement", "result_type": "constraint_state_result",
            "settlement_status": "rejected", "constraint_summary": "箱子超出交互距离",
            "target_object_id": "obj_crate", "causation_id": source, "correlation_id": source,
        })
        event = runtime._session_store.last_event(actor_id)
        turn = source + ":turn"
        BehaviorTurnRecorder(main.heavenly_graph).record(BehaviorTurnRecordRequest(
            turn_id=turn, scope=main.actor_private_scope(actor_id), valid_at=timestamp, recorded_at=timestamp,
            policy_revision="policy:recovery-probe:v1",
            source_revision_vector=GraphRevisionVector(source_revision=runtime.get_memory_revision(actor_id)),
            scope_digest=f"recovery-probe:{actor_id}",
            provenance=GraphProvenance(source_kind="runtime_outcome", source_ref=event["event_id"],
                                      causation_id=source, correlation_id=source,
                                      producer_system="character_agent_runtime", actor_id=actor_id),
            transaction_id="tx:" + turn, idempotency_key=turn,
            stages=tuple(BehaviorTurnStageRecord(
                stage=stage, outcome="rejected" if stage == "settlement" else "recorded" if stage == "context" else "skipped",
                source_refs=(event["event_id"],),
                payload={"fixture": "perception-and-rejected-settlement-without-model"},
            ) for stage in BEHAVIOR_TURN_STAGE_ORDER),
        ))
        if actor_id == "char_a":
            candidate = CharacterMemoryCandidate(
                candidate_id=source + ":memory", actor_ref="character:char_a", candidate_kind="event_experience",
                source_event_refs=(event["event_id"],), event_valid_at=timestamp, event_recorded_at=timestamp,
                knowledge_available_at=timestamp, exposure_basis="observed", summary="观察到箱子仍超出交互距离",
                confidence=0.8, salience=0.3, visibility_scope="actor:self", privacy_disposition="actor_private",
                materialization_policy="on_activation", dedup_key=source + ":memory",
                source_revision_vector={"world:recovery-probe": ordinal},
            )
            receipt = runtime.apply_character_continuity_command(CharacterContinuityCommand(
                command_id=f"recovery-probe:continuity:{ordinal}", actor_ref="character:char_a",
                expected_character_revision=runtime.get_continuity_revision(actor_id),
                from_tick=driver.current_tick - driver.window_size, to_tick=driver.current_tick,
                simulation_tick_cursor=driver.current_tick, source_revision_vector={"world:recovery-probe": ordinal},
                state_delta={"need_tension": {"physiological_pressure": 0.001}},
                memory_candidate_refs=(candidate.candidate_id,), exposure_evidence={
                    "exposure_basis": "observed", "memory_candidates": [candidate.model_dump(mode="json")],
                }, policy_revision="policy:character-continuity:v1", idempotency_key=f"recovery-probe:continuity:{ordinal}",
            ))
            if receipt.status != "committed":
                raise ValueError(f"fixture_continuity_rejected:{receipt.status}:{receipt.refusal_reason}")
    # 在两只真实容器间移动同一物品；完整走现有 Owner 校验，不绕过历史读取成本。
    source = f"recovery-probe:inventory:{ordinal}"
    origin, target = ("left", "right") if ordinal % 2 else ("right", "left")
    appended = main.inventory_authority_service.move(
        command_id=source, actor_ref="character:char_a", item_id="item:recovery-probe",
        from_container_id=f"container:recovery-probe:{origin}", to_container_id=f"container:recovery-probe:{target}",
        idempotency_key=source, causation_id=source, correlation_id=source,
    )
    if not appended.committed:
        raise RuntimeError(f"fixture_inventory_rejected:{appended}")
    main.gameplay_outbox_dispatcher.dispatch_pending()
    # fixture 没有客户端，及时消费展示消息，避免临时 debug 文本随历史窗口积压。
    runtime.drain_observatory_messages()


def full_checkpoint(publisher):
    from app.population_continuity.recovery import parse_population_checkpoint, recovery_digest

    world, store = publisher.world, publisher.store
    cadence_id = world.last_population_confirmation.cadence_id
    receipt = store.get_projection_checkpoint(f"population-receipt:{world.mode.world_ref}:{cadence_id}")
    projector = f"population-recovery:{world.mode.world_ref}"
    slot = (receipt.state["cadence_stream_revision"] // 16) % 2
    checkpoint = receipt.model_copy(update={
        "checkpoint_id": f"{projector}:{slot}", "projector_id": projector,
        "state": {**receipt.state, "recovery_state": world.export_recovery_state()},
    }, deep=True)
    checkpoint = checkpoint.model_copy(update={"projection_hash": recovery_digest(
        checkpoint.model_dump(mode="json", exclude={"projection_hash"}),
    )})
    parse_population_checkpoint(world, checkpoint)
    return checkpoint


def generate_fixture(directory: Path, *, population: int, history: int, tail: int) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    from app.services.process_qos import high_qos, process_qos_snapshot
    began = perf_counter()
    completed = False
    try:
        with high_qos():
            _generate_fixture_with_policy(directory, population=population, history=history, tail=tail)
        completed = True
    finally:
        path = directory / 'manifest.json'
        if path.exists():
            manifest = json.loads(path.read_text(encoding='utf-8'))
            manifest['generation'] = dict(wall_ms=(perf_counter() - began) * 1000,
                completed=completed, error=sys.exc_info()[0].__name__ if sys.exc_info()[0] else None,
                process_qos=process_qos_snapshot())
            write_json(path, manifest)


def _generate_fixture_with_policy(directory: Path, *, population: int, history: int, tail: int) -> None:
    """只能在新子进程生成；目录已存在则拒绝覆盖。"""
    from app.population_continuity.roster import PopulationRoster
    from app.population_continuity.runtime_publication import RuntimeCadencePublisher
    from app.world_runtime.storage_lease import RuntimeStorageLease
    from app.gameplay.inventory_runtime import ContainerSpec

    expected_implementation = implementation_digest(ROOT)
    fixture_identity = _source_identity()
    roster = directory / "roster.json"
    roster.write_text(PopulationRoster(actor_ids=("char_a", "char_b", *(
        f"resident_{index:05d}" for index in range(population - 2)
    ))).model_dump_json(), encoding="utf-8")
    database = directory / "graph.sqlite3"
    os.environ.update(child_environment(database, roster))
    from app import main

    started = perf_counter()
    publishers = []
    original = RuntimeCadencePublisher.__init__

    def capture(instance, *args, **kwargs):
        original(instance, *args, **kwargs)
        publishers.append(instance)

    checkpoints = []
    with RuntimeStorageLease(database), patch.object(RuntimeCadencePublisher, "__init__", capture):
        try:
            main.reset_runtime_state(restore_gameplay=True)
            for side in ("left", "right"):
                identity = f"container:recovery-probe:{side}"
                result = main.inventory_authority_service.create_container(
                    command_id=identity, actor_ref="character:char_a", spec=ContainerSpec(identity, 10, 10, 1),
                    idempotency_key=identity, causation_id=identity, correlation_id=identity,
                )
                if not result.committed:
                    raise ValueError("fixture_container_rejected")
            result = main.inventory_authority_service.instantiate(
                command_id="recovery-probe:item", actor_ref="character:char_a", item_id="item:recovery-probe",
                definition_id="archive_token", quantity=1, container_id="container:recovery-probe:left",
                idempotency_key="recovery-probe:item", causation_id="recovery-probe:item", correlation_id="recovery-probe:item",
            )
            if not result.committed:
                raise ValueError("fixture_item_rejected")
            driver = main._build_population_driver()
            if driver is None or driver.current_tick != 0 or len(publishers) != 1:
                raise RuntimeError("fixture_initial_state_invalid")
            publisher = publishers[0]
            for ordinal in range(1, history + tail + 1):
                fixture_window(main, driver, ordinal)
                if ordinal in (history - 16, history):
                    checkpoints.append(full_checkpoint(publisher))
                if ordinal % 100 == 0:
                    print(f"fixture {history}: {ordinal}/{history + tail}", flush=True)
            main.gameplay_event_store.save_projection_checkpoints_atomic(checkpoints)
            oracle = state_oracle(main, driver, directory)
            manifest = {
                **fixture_identity, "schema_version": 2, "runtime_profile": main.settings.population_runtime_profile,
                "window_size": driver.window_size, "roster_sha256": file_digest(roster.read_bytes()),
                "population": population, "active_private_history_actors": ["char_a", "char_b"],
                "prefix_windows": history, "tail_windows": tail,
                "checkpoint_layout": "explicit H-16/H cuts for fixed-tail comparison; production cadence remains every 16 windows",
                "checkpoint_bytes": [len(checkpoint.model_dump_json().encode("utf-8")) for checkpoint in checkpoints],
                "pending_before": oracle["pending"],
                "distinct_streams": len(oracle["stream_heads"]),
                "model_mode": "local Character and disabled Siming; persistence test only",
                "generator_ms": (perf_counter() - started) * 1000,
                "implementation_digest": expected_implementation,
                "graph_history_rows": {table: main.heavenly_graph._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                                       for table in ("graph_nodes", "graph_relations", "graph_idempotency", "character_session_events", "character_session_receipts", "character_session_candidates", "character_session_ask_trace")},
                "character_current_bytes": dict(main.heavenly_graph._connection.execute("SELECT actor_id,length(CAST(state_json AS BLOB)) FROM character_session_recovery")),
                "actor_session_counts": {actor: value["session_count"] for actor, value in oracle["actors"].items()},
            }
            if implementation_digest(ROOT) != expected_implementation or _source_identity() != fixture_identity:
                raise ValueError("implementation_changed_during_fixture_generation")
            (directory / "oracle.json").write_text(json.dumps(oracle, ensure_ascii=False), encoding="utf-8")
            (directory / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        finally:
            main.close_runtime_resources()


async def measure_process(directory: Path, output: Path) -> dict[str, object]:
    from scripts.verification.population_process_qos import recorded_high_qos
    with recorded_high_qos(directory / 'collector-qos.json'):
        return await _measure_process_with_policy(directory, output)


async def _measure_process_with_policy(directory: Path, output: Path) -> dict[str, object]:
    parent = dict(schema_version=1, started_ns=perf_counter_ns(), marker_ns=None, exit_ns=None,
                  exit_code=None, marker=None, error=None)
    process = None
    with (directory / "stdout.log").open("wb") as stdout, (directory / "stderr.log").open("wb") as stderr:
        try:
            from scripts.verification.population_python_process import python_process
            command, environment = python_process(
                [Path(__file__).resolve(), "--ready-child", output],
                child_environment(directory / "graph.sqlite3", directory / "roster.json"))
            process = await asyncio.create_subprocess_exec(
                *command, env=environment,
                stdout=asyncio.subprocess.PIPE, stderr=stderr,
            )
            parent["pid"] = process.pid
            async with asyncio.timeout(120):
                while line := await process.stdout.readline():
                    stdout.write(line)
                    if line.startswith(b"POPULATION_READY "):
                        parent.update(marker_ns=perf_counter_ns(), marker=line.decode("utf-8").strip())
                        break
                else:
                    raise RuntimeError("ready_marker_missing")
            remaining, _ = await asyncio.wait_for(process.communicate(), timeout=900)
            stdout.write(remaining)
            if process.returncode != 0:
                raise RuntimeError(f"oracle_child_failed:{process.returncode}")
            child = read_json(output.read_text(encoding="utf-8"))
            parent["database_names"] = {path: Path(path).relative_to(directory).as_posix()
                                        for path in child["ready"]["sql"]["databases"]}
        except BaseException as exc:
            parent["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            if process is not None:
                if process.returncode is None:
                    process.kill()
                await process.wait()
                parent["exit_code"] = process.returncode
            parent["exit_ns"] = perf_counter_ns()
            write_json(directory / "parent.json", parent)
    expected = read_json((directory / "oracle.json").read_text(encoding="utf-8"))
    verify_ask_oracle(directory, expected)
    verify_ask_oracle(directory, child["oracle"], owner=True)
    return _measurement(child, parent, expected)


def _source_identity() -> dict:
    return dict(base_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                source=source_manifest())


def _measurement(child: dict, parent: dict, expected: dict) -> dict:
    if (parent.get("schema_version") != 1 or parent.get("error") is not None
            or type(parent.get("exit_code")) is not int or parent["exit_code"] != 0
            or any(type(parent.get(key)) is not int for key in ("started_ns", "marker_ns", "exit_ns", "pid"))
            or not 0 < parent["started_ns"] < parent["marker_ns"] <= parent["exit_ns"] or parent["pid"] <= 0):
        raise ValueError("recovery_parent_timing_or_exit_invalid")
    marker = parent["marker"]
    if not isinstance(marker, str) or not marker.startswith("POPULATION_READY "):
        raise ValueError("recovery_parent_marker_missing")
    ready = child["ready"]
    if read_json(marker.removeprefix("POPULATION_READY ")) != {key: value for key, value in ready.items() if key != "caches"}:
        raise ValueError("recovery_ready_marker_mismatch")
    runtime = child.get('runtime_process', {})
    owner_time = ready.get('owner_restore_ms')
    if (type(ready.get('owner_pid')) is not int or ready['owner_pid'] <= 0 or ready['owner_pid'] == parent['pid']
            or type(ready.get('parent_pid')) is not int or ready['parent_pid'] != parent['pid']
            or not isinstance(runtime, dict) or type(runtime.get('exit_code')) is not int or runtime['exit_code'] != 0
            or any(type(runtime.get(key)) is not int or runtime[key] != ready[key] for key in ('owner_pid', 'parent_pid'))
            or any(type(ready.get(key)) is not int or ready[key] <= 0
                   for key in ('owner_peak_rss_bytes', 'parent_peak_rss_bytes', 'process_peak_rss_bytes'))
            or ready['process_peak_rss_bytes'] != ready['owner_peak_rss_bytes'] + ready['parent_peak_rss_bytes']
            or ready.get('rss_scope') != 'sum_of_parent_and_owner_startup_peaks'
            or type(owner_time) not in (int, float) or not math.isfinite(owner_time)
            or not 0 <= owner_time <= ready['restore_ms']):
        raise ValueError('recovery_process_measurement_invalid')
    databases = ready["sql"]["databases"]
    names = parent["database_names"]
    if (not databases or set(names) != set(databases) or len(set(names.values())) != len(names)
            or any(not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts for name in names.values())
            or ready["sql"].get("vm_interval") != 100):
        raise ValueError("recovery_sql_measurement_invalid")
    for stats in databases.values():
        if any(type(stats.get(key)) is not int or stats[key] < 0 for key in ("rows", "payload_bytes", "vm_steps_sampled")):
            raise ValueError("recovery_sql_counter_invalid")
    if any(type(count) is not int or count < 0 for count in ready["calls"].values()):
        raise ValueError("recovery_decode_counter_invalid")
    if sum(stats["rows"] for stats in databases.values()) <= 0 or not any(
            count > 0 for name, count in ready["calls"].items() if name.startswith("decode:")):
        raise ValueError("recovery_startup_measurements_empty")
    for value in (ready["restore_ms"], ready["process_peak_rss_bytes"], child["verification_ms"], *ready["phase_ms"].values()):
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("recovery_timing_invalid")
    caches = ready["caches"]
    if (set(caches["graph"]) != {"_nodes", "_relations", "_idempotency", "_checkpoints", "_branch_markers"}
            or set(caches["gameplay"]) != {"_events", "_transactions", "_outbox"}
            or any(type(value) is not int or value != 0 for name in ("graph", "gameplay") for value in caches[name].values())
            or any(caches[name] != 0 for name in ("session_events", "light_memory_events", "heavy_normalizer_events"))
            or any(type(caches[name]) is not int or not 0 <= caches[name] <= 2 for name in ("population_receipts", "population_fingerprints"))
            or not isinstance(ready["publisher_record_cache"], list) or len(ready["publisher_record_cache"]) != 1
            or type(ready["publisher_record_cache"][0]) is not int or not 0 <= ready["publisher_record_cache"][0] <= 2):
        raise ValueError("recovery_history_cache_not_bounded")
    elapsed = (parent["marker_ns"] - parent["started_ns"]) / 1_000_000
    if ready["restore_ms"] > elapsed + 1:
        raise ValueError("recovery_restore_outside_parent_interval")
    return dict(ready={**ready, "spawn_to_ready_ms": elapsed,
                      "sql": {**ready["sql"], "databases": {names[path]: stats for path, stats in databases.items()}}},
                verification_ms=child["verification_ms"], **compare_oracles(child["oracle"], expected))


def compare_oracles(actual: dict, expected: dict) -> dict[str, object]:
    # 当前 fixture 在 ready 前后不允许 pending 状态转移；数量相同也必须比较身份和状态摘要。
    return {"oracle_matches": actual == expected,
            "oracle_differences": [key for key in expected if actual.get(key) != expected[key]],
            "pending_before": expected["pending"], "pending_after": actual["pending"]}


def resource_bounds(cases: dict[int, list[dict]]) -> dict[str, object]:
    """固定 N/tail 的历史规模对照；模型入口和返回行不得随已完成历史增长。"""
    def maximum(history, field):
        return max(sum(stats[field] for stats in sample["ready"]["sql"]["databases"].values())
                   for sample in cases[history])

    small, large = min(cases), max(cases)
    rows = {history: maximum(history, "rows") for history in cases}
    payload = {history: maximum(history, "payload_bytes") for history in cases}
    vm_steps = {history: maximum(history, "vm_steps_sampled") for history in cases}
    # 固定 N/tail 只容许索引深度小幅增长及每库一次采样量化误差，不能放过 SQL 内部扫描。
    vm_sampling_allowance = max(sample["ready"]["sql"]["vm_interval"] * len(sample["ready"]["sql"]["databases"])
                                for sample in cases[small])
    vm_limit = max(vm_steps[small] * 1.5, vm_steps[small] + vm_sampling_allowance)
    decodes = {history: max(sum(count for key, count in sample["ready"]["calls"].items() if key.startswith("decode:"))
                           for sample in samples) for history, samples in cases.items()}
    forbidden = ("legacy_session_file_reads", "CharacterAgentSessionStore.list_events",
                 "CharacterAgentMemoryStore.write_event", "CharacterGraphMemoryStore.write_event",
                 "CharacterAgentRuntime._update_memory_scene_knowledge")
    full_history_calls = {history: {name: max(sample["ready"]["calls"].get(name, 0) for sample in samples)
                                   for name in forbidden} for history, samples in cases.items()}
    # 相同形状的 tick/revision 可以多一位数字；返回行/模型数没有此豁免。
    byte_ratio = payload[large] / max(1, payload[small])
    marker = {history: {field: max(sample["ready"]["calls"].get(f"session_marker_{field}", 0)
                                  for sample in samples) for field in ("reads", "bytes")}
              for history, samples in cases.items()}
    passed = (large != small and rows[large] <= rows[small] and decodes[large] <= decodes[small]
              and vm_steps[large] <= vm_limit
              and marker[large]["reads"] <= marker[small]["reads"]
              and marker[large]["bytes"] <= max(1, marker[small]["bytes"]) * 1.1
              and byte_ratio <= 1.1 and not any(count for counts in full_history_calls.values() for count in counts.values()))
    return {"passed": passed, "sql_rows": rows, "sql_payload_bytes": payload, "decode_entry_calls": decodes,
            "sql_vm_steps_sampled": vm_steps, "sql_vm_step_limit": vm_limit,
            "sql_vm_step_ratio_tolerance": 1.5, "sql_vm_sampling_allowance": vm_sampling_allowance,
            "sql_vm_tolerance_reason": "max(small * 1.5, small + one vm_interval per baseline database); fixed-tail index depth and sampling quantization only",
            "full_history_calls": full_history_calls, "session_marker": marker, "sql_payload_byte_ratio": byte_ratio,
            "payload_byte_tolerance": 1.1,
            "payload_byte_tolerance_reason": "fixed-shape tick/revision digits and marker database-path length; no row/model/read-count allowance"}


def _summary(cases: dict[int, list[dict]], *, population: int, tail: int, repeats: int) -> dict:
    p95 = {history: percentile([sample["ready"]["spawn_to_ready_ms"] for sample in samples]) for history, samples in cases.items()}
    ratio = p95[max(p95)] / p95[min(p95)]
    bounds = resource_bounds(cases)
    diagnostic_passed = all(sample["oracle_matches"] and sample["ready"]["replayed_windows"] == [tail]
                 for samples in cases.values() for sample in samples) and max(p95.values()) <= 15000 and ratio <= 1.5 and bounds["passed"]
    formal = population == 1000 and sorted(cases) == [1000, 10000] and repeats >= 5 and tail == 8
    return dict(passed=diagnostic_passed and formal, diagnostic_passed=diagnostic_passed, cases=cases,
                p95_ms=p95, p95_ratio=ratio, resource_bounds=bounds, formal_acceptance_configuration=formal,
                thresholds=dict(ready_p95_ms=15000, history_p95_ratio=1.5),
                godot_status="godot_unverified", os_page_cache="uncontrolled; process cold, not disk cold")


def _validate_fixture(manifest: dict, oracle: dict, roster: dict, *, identity: dict,
                      population: int, history: int, tail: int) -> None:
    from app.population_continuity.roster import PopulationRoster
    from app.population_continuity.recovery import PopulationRecoveryState

    if (any(manifest.get(key) != value for key, value in identity.items()) or manifest.get("schema_version") != 2
            or manifest.get("implementation_digest") != implementation_digest(ROOT)
            or (manifest.get("population"), manifest.get("prefix_windows"), manifest.get("tail_windows")) != (population, history, tail)
            or manifest.get("active_private_history_actors") != ["char_a", "char_b"]
            or manifest.get("runtime_profile") != "production" or manifest.get("window_size") != 86400):
        raise ValueError("recovery_fixture_identity_invalid")
    from scripts.verification.population_process_qos import require_restored_qos
    generation = manifest.get('generation', {})
    if generation.get('completed') is not True or generation.get('error') is not None:
        raise ValueError('recovery_fixture_generation_failed')
    require_restored_qos(generation.get('process_qos'))
    actors = PopulationRoster.model_validate(roster).actor_ids
    state = PopulationRecoveryState.model_validate_json(json.dumps(oracle["population"], allow_nan=False))
    if (len(actors) != population or {actor.actor_id for actor in state.actors} != set(actors)
            or state.confirmed_tick != (history + tail) * 86400 or oracle.get("confirmed_tick") != state.confirmed_tick
            or set(oracle) != {"population", "confirmed_tick", "actors", "authority_digest", "authority_events", "pending",
                                   "stream_heads", "behavior_turns", "inventory", "old_cadence"}
            or set(oracle["actors"]) != {"char_a", "char_b"} or oracle["authority_events"] <= history
            or not oracle["stream_heads"] or len(oracle["behavior_turns"]) != 4
            or manifest["pending_before"] != oracle["pending"] or oracle["old_cadence"].get("committed") is not True):
        raise ValueError("recovery_fixture_oracle_invalid")
    actor_fields = {"session_count", "session_digest", "session_head", "dynamic", "need", "goal", "goal_history",
                    "unresolved_tensions", "supervision", "agenda", "continuity", "continuity_revision", "seed_projection",
                    "candidates_digest", "old_continuity_receipt", "working_memory", "memory_bundle_digest", "knowledge"}
    for actor, value in oracle["actors"].items():
        if (set(value) != actor_fields or value["session_count"] < history + tail or not value["session_head"]
                or value["session_count"] != manifest["actor_session_counts"][actor]
                or any(re.fullmatch(r"sha256:[0-9a-f]{64}", value[key]) is None
                       for key in ("session_digest", "candidates_digest", "memory_bundle_digest"))):
            raise ValueError("recovery_actor_oracle_invalid")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", oracle["authority_digest"]) is None:
        raise ValueError("recovery_authority_digest_invalid")
    counts = manifest["graph_history_rows"]
    if (set(counts) != {"graph_nodes", "graph_relations", "graph_idempotency", "character_session_events",
                       "character_session_receipts", "character_session_candidates", "character_session_ask_trace"}
            or any(type(value) is not int or value < 0 for value in counts.values())
            or counts["graph_nodes"] < history + tail or counts["character_session_events"] < 2 * (history + tail)):
        raise ValueError("recovery_fixture_history_counts_invalid")


def ask_audit_name(actor_id: str, *, owner: bool = False) -> str:
    return f"{'result.owner-' if owner else ''}ask-{actor_id}.jsonl"


def verify_ask_oracle(directory: Path, oracle: dict, *, owner: bool = False):
    from scripts.verification.population_ask_audit import verify_audit
    for actor in ('char_a', 'char_b'):
        if verify_audit(directory / ask_audit_name(actor, owner=owner), actor) != oracle['actors'][actor]['knowledge']:
            raise ValueError('recovery_ask_audit_mismatch')


def _raw_paths(histories: list[int], samples: list[dict]) -> list[str]:
    # 明确列出原始 JSON/log；从不扫描大数据库、WAL、SHM。
    return ["report.json", *[f"generation-{history}.log" for history in histories],
            *[f"fixtures/{history}/{name}" for history in histories for name in ("manifest.json", "oracle.json", "roster.json", "ask-char_a.jsonl", "ask-char_b.jsonl")],
            *[f"samples/{sample['history']}-{sample['repeat']}/{name}" for sample in samples
              for name in ("result.json", "result.owner-ready.json", "result.owner-result.json", "parent.json", "stdout.log", "stderr.log", "collector-qos.json", "result.owner-qos.json", "result.parent-qos.json", "result.owner-ask-char_a.jsonl", "result.owner-ask-char_b.jsonl")]]


def verify_artifacts(directory: Path, *, expected_commit: str, require_formal: bool = True) -> dict:
    def load(name):
        value = read_json((directory / name).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("recovery_evidence_object_required")
        return value

    manifest = load("manifest.json")
    identity = _source_identity()
    if (identity["base_commit"] != expected_commit or any(manifest.get(key) != value for key, value in identity.items())
            or manifest.get("schema_version") != 2 or manifest.get("profile") != "population-long-session-recovery"
            or manifest.get("errors") != [] or manifest.get("status") not in {"passed", "smoke_checked"}):
        raise ValueError("recovery_evidence_identity_or_status_invalid")
    config = manifest["configuration"]
    population, histories, tail, repeats = (config[name] for name in ("population", "histories", "tail", "repeats"))
    if (type(population) is not int or population < 2 or type(tail) is not int or not 0 < tail <= 16
            or type(repeats) is not int or repeats < 1 or not isinstance(histories, list) or len(histories) != 2
            or any(type(h) is not int or h < 16 for h in histories) or histories != sorted(set(histories))):
        raise ValueError("recovery_configuration_invalid")
    samples = [dict(history=h, repeat=r) for r in range(repeats) for h in (histories if r % 2 == 0 else reversed(histories))]
    if manifest["samples"] != samples:
        raise ValueError("recovery_sample_coverage_invalid")
    from scripts.verification.population_ask_audit import file_hash
    artifacts = {name: file_hash(directory / name) for name in _raw_paths(histories, samples)}
    if artifacts != manifest["raw_artifacts"]:
        raise ValueError("recovery_raw_artifact_mismatch")
    expected, fixtures = {}, {}
    for history in histories:
        fixture = load(f"fixtures/{history}/manifest.json")
        fixtures[history] = fixture
        roster_path = directory / f"fixtures/{history}/roster.json"
        if fixture["roster_sha256"] != file_digest(roster_path.read_bytes()):
            raise ValueError("recovery_roster_digest_mismatch")
        expected[history] = load(f"fixtures/{history}/oracle.json")
        verify_ask_oracle(directory / f"fixtures/{history}", expected[history])
        _validate_fixture(fixture, expected[history], load(f"fixtures/{history}/roster.json"), identity=identity,
                          population=population, history=history, tail=tail)
    if any(fixtures[histories[1]]["graph_history_rows"][name] <= fixtures[histories[0]]["graph_history_rows"][name]
           for name in ("graph_nodes", "graph_relations", "character_session_events",
                        "character_session_candidates", "character_session_receipts")):
        raise ValueError("recovery_history_prefix_did_not_grow")
    cases = {history: [] for history in histories}
    parent_starts = set()
    prior_exit = 0
    for sample in samples:
        relative = f"samples/{sample['history']}-{sample['repeat']}"
        parent = load(relative + "/parent.json")
        if parent["started_ns"] in parent_starts:
            raise ValueError("recovery_reused_process_sample")
        parent_starts.add(parent["started_ns"])
        if parent["started_ns"] < prior_exit:
            raise ValueError("recovery_samples_overlap")
        prior_exit = parent["exit_ns"]
        marker_lines = [line for line in (directory / relative / "stdout.log").read_text(encoding="utf-8").splitlines()
                        if line.startswith("POPULATION_READY ")]
        if marker_lines != [parent["marker"]]:
            raise ValueError("recovery_stdout_marker_mismatch")
        child = load(relative + "/result.json")
        merged = _merge_owner_result(read_json(parent['marker'].removeprefix('POPULATION_READY ')),
            load(relative + '/result.owner-ready.json'), load(relative + '/result.owner-result.json'))
        merged['runtime_process'] = child['runtime_process']
        if merged != child:
            raise ValueError('recovery_owner_merge_mismatch')
        verify_ask_oracle(directory / relative, merged["oracle"], owner=True)
        result = _measurement(merged, parent, expected[sample["history"]])
        cases[sample["history"]].append(result)
    report = _summary(cases, population=population, tail=tail, repeats=repeats)
    if read_json(json.dumps(report)) != load("report.json"):
        raise ValueError("recovery_recomputed_report_mismatch")
    if not report["diagnostic_passed"] or require_formal and not report["passed"]:
        raise ValueError("recovery_threshold_or_formal_configuration_failed")
    return dict(**report, base_commit=expected_commit)


def run_gate(args) -> bool:
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    identity = _source_identity()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    evidence = output / f"evidence-{run_id}"
    evidence.mkdir()
    config = dict(population=args.population, histories=sorted(args.histories), tail=args.tail_windows, repeats=args.repeats)
    manifest = dict(**identity, schema_version=2, profile="population-long-session-recovery", configuration=config,
                    started_at=datetime.now(timezone.utc).isoformat(), status="incomplete", samples=[], errors=[],
                    environment=dict(python=platform.python_version(), sqlite=sqlite3.sqlite_version, os=platform.platform()),
                    godot_status="godot_unverified")
    write_json(evidence / "manifest.json", manifest)
    report = dict(passed=False, error="recovery_run_incomplete")
    try:
        if len(set(args.histories)) != 2:
            raise ValueError("recovery_requires_two_distinct_histories")
        for history in config["histories"]:
            fixture = output / f"fixture-{history}"
            fixture_evidence = evidence / f"fixtures/{history}"
            fixture_evidence.mkdir(parents=True)
            try:
                with (evidence / f"generation-{history}.log").open("w", encoding="utf-8") as log:
                    if not fixture.exists():
                        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--generate-child", str(fixture),
                                        "--population", str(args.population), "--histories", str(history),
                                        "--tail-windows", str(args.tail_windows)], check=True, stdout=log, stderr=subprocess.STDOUT)
                    else:
                        log.write("reuse fixture only after exact source/configuration verification\n")
            finally:
                for name in ("manifest.json", "oracle.json", "roster.json", "ask-char_a.jsonl", "ask-char_b.jsonl"):
                    if (fixture / name).is_file():
                        shutil.copy2(fixture / name, fixture_evidence / name)
            verify_ask_oracle(fixture, read_json((fixture / "oracle.json").read_text(encoding="utf-8")))
            fixture_manifest = read_json((fixture / "manifest.json").read_text(encoding="utf-8"))
            _validate_fixture(fixture_manifest, read_json((fixture / "oracle.json").read_text(encoding="utf-8")),
                              read_json((fixture / "roster.json").read_text(encoding="utf-8")), identity=identity,
                              population=args.population, history=history, tail=args.tail_windows)
        cases = {history: [] for history in config["histories"]}
        for repeat in range(args.repeats):
            for history in config["histories"] if repeat % 2 == 0 else reversed(config["histories"]):
                directory = output / f"run-{history}-{repeat}-{run_id}"
                shutil.copytree(output / f"fixture-{history}", directory)
                sample = dict(history=history, repeat=repeat)
                manifest["samples"].append(sample)
                raw = evidence / f"samples/{history}-{repeat}"
                raw.mkdir(parents=True)
                try:
                    result = asyncio.run(measure_process(directory, directory / "result.json"))
                finally:
                    for name in ("result.json", "result.owner-ready.json", "result.owner-result.json", "parent.json", "stdout.log", "stderr.log", "collector-qos.json", "result.owner-qos.json", "result.parent-qos.json", "result.owner-ask-char_a.jsonl", "result.owner-ask-char_b.jsonl"):
                        if (directory / name).is_file():
                            shutil.copy2(directory / name, raw / name)
                cases[history].append(result)
                print(f"restore {history}/{repeat}: {result['ready']['spawn_to_ready_ms']:.1f}ms oracle={result['oracle_matches']}", flush=True)
        if _source_identity() != identity:
            raise ValueError("recovery_source_changed_during_run")
        report = _summary(cases, population=args.population, tail=args.tail_windows, repeats=args.repeats)
        manifest["status"] = "passed" if report["passed"] else "smoke_checked" if report["diagnostic_passed"] else "failed"
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        manifest.update(status="failed", errors=[f"{type(exc).__name__}: {exc}"])
        report = dict(passed=False, error=manifest["errors"][0])
    finally:
        write_json(evidence / "report.json", report)
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        from scripts.verification.population_ask_audit import file_hash
        manifest["raw_artifacts"] = {name: file_hash(evidence / name)
                                     for name in _raw_paths(config["histories"], manifest["samples"]) if (evidence / name).is_file()}
        write_json(evidence / "manifest.json", manifest)
        write_json(output / "report.json", {**report, "manifest": str(evidence / "manifest.json")})
    return report["passed"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ready-child", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--generate-child", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--population", type=int, default=1000)
    parser.add_argument("--histories", type=int, nargs="+", default=[1000, 10000])
    parser.add_argument("--tail-windows", type=int, default=8)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path, default=ROOT / ".harness/verification/population-long-session-recovery")
    parser.add_argument("--verify-artifacts", type=Path)
    parser.add_argument("--require-fresh-commit")
    maintenance = parser.add_mutually_exclusive_group()
    maintenance.add_argument("--audit-store", type=Path)
    maintenance.add_argument("--rebuild-checkpoint", type=Path)
    parser.add_argument("--roster", type=Path, help="离线维护使用的同一局 PopulationRoster 文件")
    args = parser.parse_args()
    if args.verify_artifacts:
        if not args.require_fresh_commit:
            parser.error("--verify-artifacts requires --require-fresh-commit")
        print(json.dumps(verify_artifacts(args.verify_artifacts, expected_commit=args.require_fresh_commit)))
        return 0
    if args.population < 2 or args.repeats < 1 or not 0 < args.tail_windows <= 16 or any(history < 16 for history in args.histories):
        parser.error("population >= 2; histories >= 16; repeats >= 1; tail in [1,16]")
    if args.audit_store or args.rebuild_checkpoint:
        from app import main as runtime_main
        from app.population_continuity.roster import load_population_roster

        destination = args.output / ("maintenance-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
        result = maintain_archive(args.audit_store or args.rebuild_checkpoint,
                                  mode=runtime_main._bakery_population_mode(),
                                  roster=load_population_roster(args.roster or runtime_main.settings.population_roster_path),
                                  output=destination, rebuild=bool(args.rebuild_checkpoint))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.ready_child:
        asyncio.run(ready_child(args.ready_child))
        return 0
    if args.generate_child:
        if len(args.histories) != 1:
            parser.error("generate child requires exactly one history")
        generate_fixture(args.generate_child, population=args.population, history=args.histories[0], tail=args.tail_windows)
        return 0
    return 0 if run_gate(args) else 1


if __name__ == "__main__":
    raise SystemExit(main())
