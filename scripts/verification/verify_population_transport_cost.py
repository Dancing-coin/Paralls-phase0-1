"""真实 main/owner/Uvicorn/WS 数据搬运对照；基准插桩与未插桩 1× 验收分别记录。"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from contextlib import ExitStack
import cProfile
from dataclasses import asdict, fields
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import secrets
import shutil
import socket
import sqlite3
from statistics import median
import subprocess
import sys
from time import perf_counter
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from app.gameplay.godot_mirror_delivery import GameplayGodotMirrorSyncAdapter, GameplayMirrorOutboundQueue
from app.ws_protocol import GameplayMirrorDeliveryEnvelope
from scripts.verification.population_benchmark_metrics import (
    LoopbackWebSocketByteProxy, TransportMetrics, measure_population_transport, peak_rss_bytes, percentile,
)
from scripts.verification.population_godot_runner import (
    authority_boundary, child_environment, object_digest, source_manifest, write_json,
)
from scripts.verification.verify_population_godot_runtime import digest, read_json


class WireEvidence:
    """只接受授权 actor 的连续 exact-base 投影；保留实际收到的 UTF-8 字节口径。"""

    def __init__(self, actor_refs: set[str], *, strict_public_windows: bool = True) -> None:
        if not actor_refs or len(actor_refs) > 160:
            raise ValueError("invalid_cost_probe_scope")
        self.actor_refs = actor_refs
        self.strict_public_windows = strict_public_windows
        self.snapshots = {}
        self.sequence = self.epoch = 0
        self.bytes_received = 0
        self.bytes_by_kind = Counter()
        self.counts = Counter()
        self.sync = GameplayGodotMirrorSyncAdapter()
        self.latest_payloads = {}
        self.public_windows = {}

    def receive(self, raw: str):
        self.bytes_received += len(raw.encode("utf-8"))
        message = json.loads(raw)
        kind = message["message_type"]
        if kind != "gameplay_mirror_delivery":
            self.bytes_by_kind[kind] += len(raw.encode("utf-8"))
            if kind == "gameplay_mirror_resync_required":
                raise ValueError("cost_probe_resync_required")
            if kind == "ack" and message["payload"].get("accepted") is not True:
                raise ValueError("cost_probe_request_rejected")
            if kind not in {"ack", "websocket_session_bound"}:
                raise ValueError(f"cost_probe_unexpected_packet:{kind}")
            return message
        outer = GameplayMirrorDeliveryEnvelope.model_validate(message["payload"])
        kind = outer.delivery_kind
        if (outer.actor_ref not in self.actor_refs or kind not in {"snapshot", "delta"}
                or outer.delivery_sequence != self.sequence + 1
                or self.epoch not in {0, outer.connection_epoch}):
            raise ValueError("cost_probe_scope_or_cursor_invalid")
        payload = outer.payload
        if kind == "snapshot":
            target = self.sync.snapshot_from_payload(payload)
        else:
            if outer.actor_ref not in self.snapshots:
                raise ValueError("cost_probe_delta_base_missing")
            base = self.snapshots[outer.actor_ref]
            full = {"message_type": "gameplay_runtime_state_projection",
                    "projection_kind": "gameplay_runtime_state.godot.v1",
                    **json.loads(payload["canonical_snapshot_json"]),
                    "canonical_snapshot_json": payload["canonical_snapshot_json"],
                    "snapshot_checksum": payload["target_snapshot_checksum"]}
            target = self.sync.snapshot_from_payload(full)
            delta = self.sync.delta(base, target)
            if self.sync.delta_payload(base, delta) != payload:
                raise ValueError("cost_probe_delta_payload_mismatch")
            if (outer.base_snapshot_checksum != base.snapshot_checksum
                    or outer.base_facade_revision != base.facade_revision
                    or outer.target_snapshot_checksum != target.snapshot_checksum):
                raise ValueError("cost_probe_delta_anchor_mismatch")
        if (outer.actor_ref != target.actor_ref or outer.facade_revision != target.facade_revision
                or outer.source_revision_vector != dict(target.source_revision_vector)
                or outer.projection_schema != payload["projection_kind"]):
            raise ValueError("cost_probe_outer_anchor_mismatch")
        if "population_public" in target.groups:
            tick = target.groups["population_public"].payload["confirmed_tick"]
            key = (outer.actor_ref, tick)
            if (self.strict_public_windows and key in self.public_windows
                    and self.public_windows[key] != target.snapshot_checksum):
                raise ValueError("cost_probe_window_conflict")
            self.public_windows[key] = target.snapshot_checksum
        self.sequence, self.epoch = outer.delivery_sequence, outer.connection_epoch
        self.snapshots[outer.actor_ref] = target
        self.latest_payloads[kind] = message["payload"]
        self.counts[kind] += 1
        self.bytes_by_kind[kind] += len(raw.encode("utf-8"))
        return message

    def public_oracle(self, *, windows: int):
        expected = {(actor, tick) for actor in self.actor_refs for tick in range(windows + 1)}
        if self.public_windows.keys() != expected:
            raise ValueError("cost_probe_public_windows_missing_or_extra")
        return object_digest([[actor, tick, checksum] for (actor, tick), checksum in sorted(self.public_windows.items())])


def _summary(values):
    return {"median": median(values), "p95": percentile(values), "max": max(values),
            "mad": median(abs(value - median(values)) for value in values)}


def compare_runs(before: list[dict], after: list[dict]) -> dict:
    if not before or len(before) != len(after):
        raise ValueError("cost_probe_paired_runs_required")
    before_cost = [median(row["window_ms"]) for row in before]
    after_cost = [median(row["window_ms"]) for row in after]
    b, a = _summary(before_cost), _summary(after_cost)
    end_before = _summary([median(row["delivery_complete_ms"]) for row in before])
    end_after = _summary([median(row["delivery_complete_ms"]) for row in after])
    before_calls = sum(sum(row["checkpoint_validations"]) for row in before)
    after_calls = sum(sum(row["checkpoint_validations"]) for row in after)
    equal = all(not b["errors"] and not a["errors"] and b["oracle"] == a["oracle"]
                and b["seed_files"] == a["seed_files"] and b["population"] == a["population"]
                and b["windows"] == a["windows"] for b, a in zip(before, after))
    time_improved = b["median"] > 0 and a["median"] <= b["median"] * .9 and b["median"] - a["median"] > max(a["mad"], b["mad"])
    count_improved = before_calls > 0 and after_calls <= before_calls * .8
    end_improved = end_after["median"] <= end_before["median"] * .9 and end_before["median"] - end_after["median"] > max(end_before["mad"], end_after["mad"])
    return {"equivalent": equal, "formal_repeats": len(before) == 5,
            "before_window_ms": b, "after_window_ms": a,
            "before_delivery_complete_ms": end_before, "after_delivery_complete_ms": end_after,
            "checkpoint_validation_reduction": 1 - after_calls / before_calls if before_calls else 0,
            "time_improved": time_improved, "materialization_improved": count_improved,
            "end_to_end_improved": end_improved,
            "improvement_passed": equal and end_improved and (time_improved or count_improved)}


def _files(directory: Path) -> dict:
    return {path.relative_to(directory).as_posix(): digest(path.read_bytes())
            for path in sorted(directory.rglob("*")) if path.is_file()}


def _raw_artifacts(directory: Path) -> dict:
    return {path.relative_to(directory).as_posix(): digest(path.read_bytes())
        for path in sorted(directory.rglob("*")) if path.is_file() and path != directory / "manifest.json"
        and (not {"state", "seed-state"}.intersection(path.relative_to(directory).parts) or path.name == "process.log")}


def verify_artifacts(directory: Path, *, expected_commit: str, require_formal: bool = True) -> dict:
    """从原始窗口与公开包复算成本结论；移动证据目录不需要启动后端或 Godot。"""
    def load(name):
        return read_json((directory / name).read_text(encoding="utf-8"))

    manifest = load("manifest.json")
    if (manifest.get("schema_version") != 1 or manifest.get("base_commit") != expected_commit
            or manifest.get("source") != source_manifest()):
        raise ValueError("cost_evidence_identity_mismatch")
    population, windows, repeats = (manifest[key] for key in ("population", "windows", "repeats"))
    if (population not in (100, 1000, 10000) or type(windows) is not int or windows < 1
            or type(repeats) is not int or repeats < 1):
        raise ValueError("cost_evidence_matrix_invalid")
    formal = population == 1000 and windows == 30 and repeats == 5
    status = "cost_comparison_passed" if formal else "smoke_checked"
    if (manifest.get('clock_profile') != 'manual_window_cost'
            or manifest.get("formal_cost_matrix") is not formal or (require_formal and not formal)):
        raise ValueError("cost_evidence_formal_matrix_required")
    if manifest.get("status") != status:
        raise ValueError("cost_evidence_status_invalid")
    if manifest.get("raw_artifacts") != _raw_artifacts(directory):
        raise ValueError("cost_evidence_artifact_digest_mismatch")
    actors = load("roster.json")["actor_ids"]
    if len(actors) != population or len(set(actors)) != population:
        raise ValueError("cost_evidence_roster_invalid")
    selected = {f"character:{actor}" for actor in actors[:160]}
    rows = {"before": [], "after": [], "full": []}
    for variant, count in (("before", repeats), ("after", repeats), ("full", 1)):
        for ordinal in range(count):
            folder = variant if variant == "full" else f"{variant}-{ordinal}"
            for name in ("result.json", "public-messages.jsonl", "process.log",
                    "owner-ready.json", "owner-result.json", "parent-observed.json"):
                if f"{folder}/{name}" not in manifest["raw_artifacts"]:
                    raise ValueError("cost_evidence_raw_artifact_missing")
            row = load(f"{folder}/result.json")
            if (row["variant"] != variant or row["population"] != population or row["windows"] != windows
                    or row["errors"]):
                raise ValueError("cost_evidence_run_invalid")
            raw_result = merge_process_evidence(load(f"{folder}/owner-ready.json"),
                load(f"{folder}/owner-result.json"), load(f"{folder}/parent-observed.json"))
            confirmations = load(f"{folder}/owner-result.json")["delivery_confirmations"]
            for tick, confirmation in enumerate(confirmations, 1):
                relative = f"{folder}/{_delivery_ack_path(Path(), tick).name}"
                if relative not in manifest["raw_artifacts"] or load(relative) != confirmation:
                    raise ValueError("cost_evidence_delivery_artifact_invalid")
            if raw_result != row:
                raise ValueError("cost_evidence_process_merge_mismatch")
            authority = row["oracle"]["authority"]
            digest_fields = {"receipt_digest", "checkpoint_digest", "character_revision_digest",
                "population_state_digest", "gameplay_events_digest", "gameplay_replay_digest",
                "hot_revision_digest", "stream_revision_digest", "owner_receipt_digest"}
            counts = {"confirmed_tick": windows, "population": population, "advanced_count": population}
            if (not isinstance(authority, dict) or set(authority) != digest_fields | set(counts) | {"authority_head"}
                    or any(type(authority.get(key)) is not int or authority[key] != expected for key, expected in counts.items())
                    or type(authority.get("authority_head")) is not int or authority["authority_head"] < 0
                    or any(not isinstance(authority.get(key), str)
                        or not authority[key].startswith("" if key == "gameplay_replay_digest" else "sha256:")
                        or len(authority[key]) != (64 if key == "gameplay_replay_digest" else 71)
                        or any(char not in "0123456789abcdef" for char in authority[key][-64:]) for key in digest_fields)):
                raise ValueError("cost_evidence_authority_invalid")
            for key in ("window_ms", "delivery_complete_ms", "checkpoint_validations", "checkpoint_validate_ms", "sqlite_calls_ms"):
                values = row[key]
                if len(values) != windows or any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 for value in values):
                    raise ValueError("cost_evidence_window_samples_invalid")
            if type(row["process_peak_rss_bytes"]) is not int or row["process_peak_rss_bytes"] <= 0:
                raise ValueError("cost_evidence_rss_missing")
            segments = row["reconstruction_segments"]
            if {(item["scope"], item["audience"]) for item in segments} != {("internal", "backend"), ("public", "godot")}:
                raise ValueError("cost_evidence_segments_missing")
            for segment in segments:
                if set(segment) != {field.name for field in fields(TransportMetrics)}:
                    raise ValueError("cost_evidence_segment_schema_invalid")
                for key in ("materialize_ms", "validate_ms", "json_encode_ms", "json_decode_ms", "hash_ms", "alloc_bytes", "encoded_bytes", "field_count", "boundary_model_count"):
                    value = segment[key]
                    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                        raise ValueError("cost_evidence_segment_value_invalid")
            wire = WireEvidence(selected)
            with (directory / folder / "public-messages.jsonl").open(encoding="utf-8") as stream:
                for line in stream:
                    packet = read_json(line)
                    if packet["packet_bytes"] != len(packet["raw_text"].encode("utf-8")):
                        raise ValueError("cost_evidence_packet_bytes_mismatch")
                    if wire.receive(packet["raw_text"])["message_type"] != "gameplay_mirror_delivery":
                        raise ValueError("cost_evidence_public_packet_required")
            network = row["network"]
            if (wire.public_oracle(windows=windows) != row["oracle"]["public"]
                    or dict(wire.counts) != network["delivery_counts"]
                    or any(network["server_bytes_by_kind"].get(kind) != value for kind, value in wire.bytes_by_kind.items())
                    or (variant == "full" and wire.counts["delta"] != 0)
                    or (variant != "full" and wire.counts["delta"] == 0)):
                raise ValueError("cost_evidence_wire_oracle_mismatch")
            if (network["compression"] != "disabled" or network["tcp_ip_header_bytes_measured"] is not False
                    or network["resync_count"] != 0 or network["loop_queue_peak_items"] > 160):
                raise ValueError("cost_evidence_transport_invalid")
            for key in ("handshake", "ws_frame", "application"):
                total_key = "application_payload_bytes" if key == "application" else key + "_bytes"
                values = network[key + "_bytes_by_direction"]
                if (set(values) != {"client_to_backend", "backend_to_client"}
                        or any(type(value) is not int or value <= 0 for value in values.values())
                        or network[total_key] != sum(values.values())):
                    raise ValueError("cost_evidence_transport_bytes_mismatch")
            received = network["application_bytes_by_direction"]["backend_to_client"]
            if (not set(network["server_bytes_by_kind"]).issubset({"snapshot", "delta", "ack", "websocket_session_bound"})
                    or any(type(value) is not int or value < 0 for value in network["server_bytes_by_kind"].values())
                    or received != sum(network["server_bytes_by_kind"].values()) or received < wire.bytes_received
                    or any(network["ws_frame_bytes_by_direction"][key] < value for key, value in network["application_bytes_by_direction"].items())):
                raise ValueError("cost_evidence_application_bytes_mismatch")
            before, after = row["sqlite_file_bytes_before"], row["sqlite_file_bytes_after"]
            if (not before or not after or any(type(value) is not int or value < 0 for value in (*before.values(), *after.values()))
                    or row["sqlite_file_size_delta"] != {name:after.get(name, 0)-before.get(name, 0) for name in before.keys() | after.keys()}):
                raise ValueError("cost_evidence_sqlite_delta_mismatch")
            rows[variant].append(row)
    for variant in ("before", "after"):
        if load(f"transport-{variant}.json") != {"runs": rows[variant]}:
            raise ValueError("cost_evidence_run_summary_mismatch")
    comparison = compare_runs(rows["before"], rows["after"])
    all_rows = [row for group in rows.values() for row in group]
    if (comparison != manifest["comparison"] or not comparison["improvement_passed"]
            or any(row["oracle"] != all_rows[0]["oracle"] or row["seed_files"] != all_rows[0]["seed_files"] for row in all_rows)
            or rows["full"][0]["network"] != manifest["full_transport"]):
        raise ValueError("cost_evidence_comparison_mismatch")
    return dict(status=status, base_commit=expected_commit, formal_cost_matrix=formal, comparison=comparison,
                unprofiled_1x_short_gate="not_run", closure_status="incomplete", godot_status="godot_unverified")


def _sqlite_files(directory: Path) -> dict:
    # 文件大小和 SQLite page/WAL 是逻辑/文件计量，不是 OS 物理写入字节。
    files = {}
    for path in directory.rglob("*"):
        # 自有存档租约不是SQLite；Windows持锁时不能另开handle读取首字节。
        if not path.is_file() or path.name.endswith(".runtime.lock"):
            continue
        with path.open("rb") as handle:
            is_sqlite = handle.read(16) == b"SQLite format 3\x00"
        if is_sqlite:
            for member in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
                if member.is_file():
                    files[member.relative_to(directory).as_posix()] = member.stat().st_size
    return files


def _configure(state: Path, roster: Path):
    from app import config
    actors = json.loads(roster.read_text(encoding="utf-8"))["actor_ids"]
    secret = secrets.token_urlsafe(32)
    config.settings = config.Settings(
        heavenly_graph_path=str(state / "graph.sqlite3"), population_roster_path=str(roster),
        population_runtime_profile="benchmark_1x", character_model_provider_kind="local", siming_llm_mode="disabled",
        gameplay_mirror_launcher_bootstrap_secret=secret,
        gameplay_mirror_trusted_local_launch_profiles=[config.GameplayMirrorTrustedLocalLaunchProfileSettings(
            profile_ref="population-cost-probe", principal_ref="population-cost-probe",
            allowed_actor_refs=tuple(f"character:{actor}" for actor in actors), credential_ttl_seconds=300)],
    )
    from app import main
    return main, actors, secret


def cost_seed_child(commands, controls, results, notifications, settings_json):
    from app import main
    from app.services.runtime_process import runtime_child_main
    with patch.object(main, "start_population_runtime", lambda: None):
        runtime_child_main(commands, controls, results, notifications, settings_json)


async def _seed(state: Path, roster: Path) -> None:
    from app.services import runtime_process
    main, _, _ = _configure(state, roster)
    with patch.object(runtime_process, "CHILD_TARGET", cost_seed_child):
        async with main.app.router.lifespan_context(main.app):
            host = main.app.state.runtime_process
            if host.process.pid == os.getpid():
                raise RuntimeError("cost_probe_seed_owner_invalid")
        if host.process.exitcode != 0:
            raise RuntimeError("cost_probe_seed_shutdown_failed")


async def _owner_file(directory, name, process):
    from scripts.verification.verify_population_mixed_soak import read_control
    async with asyncio.timeout(90):
        while not (directory / name).exists():
            if not process.is_alive():
                raise RuntimeError("cost_probe_owner_exited")
            await asyncio.sleep(.02)
    result = await read_control(directory / name, loader=read_json)
    if result.get("errors"):
        raise RuntimeError("cost_probe_owner_failed")
    return result


def cost_owner_child(commands, controls, results, notifications, settings_json):
    """只在原 child 插桩；原自主 driver 与 owner 负责所有模拟和权威读取。"""
    from app import main
    from app.population_continuity import presentation
    from app.services.runtime_process import runtime_child_main
    directory = Path(os.environ["PARALLS_COST_PROBE_DIRECTORY"])
    options = read_json((directory / "probe-config.json").read_text(encoding="utf-8"))
    variant, windows = options["variant"], options["windows"]
    observed = dict(owner_pid=os.getpid(), variant=variant, windows=windows, errors=[],
        window_started=[], delivery_confirmations=[], window_ms=[], checkpoint_validations=[], checkpoint_validate_ms=[], sqlite_calls_ms=[])
    count = 0
    validation_elapsed = 0.0
    queue_peak_bytes = queue_peak_count = 0
    queue_sizes = {}
    task = None
    original_parse = presentation.parse_population_checkpoint
    original_pop = GameplayMirrorOutboundQueue.pop_next
    original_startup = main._start_population_runtime_on_startup
    original_shutdown = main._stop_population_runtime_on_shutdown

    def checked(*args, **kwargs):
        nonlocal count, validation_elapsed
        started = perf_counter()
        try:
            return original_parse(*args, **kwargs)
        finally:
            count += 1
            validation_elapsed += (perf_counter() - started) * 1000

    def old_actor_view(source):
        view = presentation.build_population_actor_view(source.mirror.world, actor_id=source.actor_id)
        return view if source.base_source is None else presentation.combine_godot_views(source.base_source(), view)

    def measured_pop(queue):
        nonlocal queue_peak_bytes, queue_peak_count, queue_sizes
        pending = [*queue._projections, *queue._controls, *queue._dirty_by_actor.values()]
        current = {}
        for item in pending:
            identity = id(item)
            cached = queue_sizes.get(identity)
            if cached is None or cached[0] is not item:
                values = item.get("_initial_batch", [item])
                cached = (item, sum(len(json.dumps({key: entry for key, entry in value.items() if not key.startswith("_")},
                    ensure_ascii=False, separators=(",", ":")).encode("utf-8")) for value in values))
            current[identity] = cached
        queue_sizes = current
        queue_peak_count = max(queue_peak_count, len(pending))
        queue_peak_bytes = max(queue_peak_bytes, sum(value[1] for value in current.values()))
        return original_pop(queue)

    async def observe():
        try:
            driver = main._population_runtime_driver
            if (driver is None or driver.current_tick != 0 or driver.window_size != 1
                    or driver.wall_period_seconds != 1):
                raise ValueError("cost_probe_initial_driver_invalid")
            observed["population"] = len(driver.world_runtime.roster.actor_ids)
            tick = driver.tick
            observed["sqlite_file_bytes_before"] = _sqlite_files(directory / "state")

            def measured_tick(target):
                nonlocal count, validation_elapsed
                count = 0
                validation_elapsed = 0
                profiler = cProfile.Profile()
                started = perf_counter()
                observed["window_started"].append(started)
                profiler.enable()
                try:
                    result = tick(target)
                finally:
                    profiler.disable()
                observed["window_ms"].append((perf_counter() - started) * 1000)
                observed["checkpoint_validations"].append(count)
                observed["checkpoint_validate_ms"].append(validation_elapsed)
                observed["sqlite_calls_ms"].append(sum(entry.totaltime * 1000 for entry in profiler.getstats()
                    if isinstance(entry.code, str) and "sqlite3." in entry.code))
                if result.rejected_windows or not result.published_cadence_ids:
                    raise ValueError("cost_probe_window_rejected")
                return result

            await asyncio.wrap_future(main.runtime_execution.submit(lambda: setattr(driver, "tick", measured_tick)))
            write_json(directory / "owner-ready.json", dict(owner_pid=os.getpid(), population=observed["population"],
                variant=variant, windows=windows, initial_tick=0, clock_profile="manual_window_cost"))
            async with asyncio.timeout(windows * 15 + 60):
                while not (directory / "start").exists():
                    await asyncio.sleep(.02)
                # 插桩成本实验逐窗推进；实际1×连续时钟由独立service门禁证明。
                for target in range(1, windows + 1):
                    await asyncio.wrap_future(main.runtime_execution.submit(lambda target=target: driver.tick(target)))
                    while True:
                        path = _delivery_ack_path(directory, target)
                        if path.exists():
                            from scripts.verification.verify_population_mixed_soak import read_control
                            acknowledgement = await read_control(path)
                            if acknowledgement.get('tick') == target:
                                if (acknowledgement.get('actor_count') != min(160, observed['population'])
                                        or type(acknowledgement.get('received_at')) not in (int, float)
                                        or not math.isfinite(acknowledgement['received_at'])
                                        or acknowledgement['received_at'] < observed['window_started'][-1]):
                                    raise ValueError('cost_delivery_confirmation_invalid')
                                observed['delivery_confirmations'].append(acknowledgement)
                                break
                            if acknowledgement.get('tick') != target:
                                raise ValueError('cost_delivery_confirmation_tick_invalid')
                        await asyncio.sleep(.005)
                while not (directory / "finish").exists():
                    await asyncio.sleep(.02)
            boundary = await asyncio.wrap_future(main.runtime_execution.submit(lambda: authority_boundary(main)))
            observed["authority"] = {key: value for key, value in boundary["authority"].items()
                if key not in {"driver_id", "world_id"}}
            observed["sqlite_file_bytes_after"] = _sqlite_files(directory / "state")
            command = await asyncio.wrap_future(main.runtime_execution.submit(lambda: driver.world_runtime.build_population_cadence(
                window_start=driver.current_tick, window_end=driver.current_tick + 1)))
            observed["internal_segment"] = asdict(measure_population_transport(
                lambda: type(command).model_validate_json(command.model_dump_json()), scope="internal", audience="backend"))
            observed.update(queue_peak_bytes=queue_peak_bytes, queue_peak_count=queue_peak_count,
                peak_rss_bytes=peak_rss_bytes())
            if len(observed["window_ms"]) != windows or observed["authority"]["confirmed_tick"] != windows:
                raise ValueError("cost_probe_window_count_mismatch")
        except BaseException as error:
            observed["errors"].append(type(error).__name__)
        finally:
            write_json(directory / "owner-result.json", observed)

    async def startup():
        nonlocal task
        await original_startup()
        task = asyncio.create_task(observe())

    async def shutdown():
        try:
            if task is not None and not task.done():
                task.cancel()
            if task is not None:
                await task
        finally:
            await original_shutdown()

    with ExitStack() as stack:
        stack.enter_context(patch.object(presentation, "parse_population_checkpoint", checked))
        stack.enter_context(patch.object(GameplayMirrorOutboundQueue, "pop_next", measured_pop))
        if variant == "before":
            stack.enter_context(patch.object(presentation._PopulationActorSource, "__call__", old_actor_view))
        stack.enter_context(patch.object(main, "start_population_runtime", lambda: None))
        stack.enter_context(patch.object(main, "_start_population_runtime_on_startup", startup))
        stack.enter_context(patch.object(main, "_stop_population_runtime_on_shutdown", shutdown))
        try:
            runtime_child_main(commands, controls, results, notifications, settings_json)
        finally:
            from app.services.process_qos import process_qos_snapshot
            write_json(directory / 'owner-qos.json', process_qos_snapshot())


def merge_process_evidence(ready, owner, parent):
    """同一系统 perf_counter 跨进程可比；从实际起窗和收包校验时刻重算。"""
    for key in ("parent_pid", "owner_pid"):
        if type(parent.get(key)) is not int or parent[key] <= 0:
            raise ValueError("cost_evidence_process_identity_invalid")
    if (parent["parent_pid"] == parent["owner_pid"] or owner.get("owner_pid") != parent["owner_pid"]
            or type(parent.get("child_exit_code")) is not int or parent["child_exit_code"] != 0
            or parent.get("errors") != [] or owner.get("errors") != []
            or parent.get("asgi_lifecycle") != dict(startup_failed=False, shutdown_failed=False, error_occurred=False)):
        raise ValueError("cost_evidence_process_failed")
    if any(value is not False for value in parent["asgi_lifecycle"].values()):
        raise ValueError("cost_evidence_process_failed")
    expected = {key: parent[key] for key in ("owner_pid", "population", "variant", "windows")}
    if (ready != dict(expected, initial_tick=0, clock_profile="manual_window_cost")
            or any(owner.get(key) != value for key, value in expected.items())):
        raise ValueError("cost_evidence_owner_identity_mismatch")
    starts, received = owner["window_started"], parent["delivery_received_at"]
    if (len(starts) != parent["windows"] or len(received) != len(starts)
            or any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0
                for value in [*starts, *received])
            or any(b <= a for values in (starts, received) for a, b in zip(values, values[1:]))
            or any(end < start for start, end in zip(starts, received))
            or any(start < end for start, end in zip(starts[1:], received[:-1]))
            or owner.get('delivery_confirmations') != [dict(tick=index + 1, received_at=end,
                actor_count=min(160, parent['population'])) for index, end in enumerate(received)]):
        raise ValueError("cost_evidence_process_clock_invalid")
    peaks = [parent["peak_rss_bytes"], owner["peak_rss_bytes"]]
    if any(type(value) is not int or value <= 0 for value in peaks):
        raise ValueError("cost_evidence_process_rss_invalid")
    before, after = owner["sqlite_file_bytes_before"], owner["sqlite_file_bytes_after"]
    return {**{key: parent[key] for key in ("variant", "population", "windows", "seed_files")},
        "oracle": {"authority": owner["authority"], "public": parent["public_oracle"]},
        **{key: owner[key] for key in ("window_ms", "checkpoint_validations", "checkpoint_validate_ms", "sqlite_calls_ms")},
        "delivery_complete_ms": [(end - start) * 1000 for start, end in zip(starts, received)],
        "sqlite_file_bytes_before": before, "sqlite_file_bytes_after": after,
        "sqlite_file_size_delta": {key: after.get(key, 0) - before.get(key, 0) for key in before.keys() | after.keys()},
        "network": {**parent["network"], "loop_queue_peak_encoded_payload_bytes": owner["queue_peak_bytes"],
            "loop_queue_peak_items": owner["queue_peak_count"],
            "queue_byte_scope": "pending child loop queue JSON before delta encoding, sampled before each dequeue; not TCP buffered bytes"},
        "reconstruction_segments": [owner["internal_segment"], *parent["reconstruction_segments"]],
        "process_peak_rss_bytes": sum(peaks), "parent_peak_rss_bytes": peaks[0], "owner_peak_rss_bytes": peaks[1],
        "rss_scope": "sum_of_parent_and_owner_process_peaks",
        "runtime_process": {key: parent[key] for key in ("parent_pid", "owner_pid", "child_exit_code")},
        "measurement_scope": "manually paced profiled child owner windows after complete real parent loopback TCP delivery; reconstruction segments separate; no physical disk IO claim",
        "errors": []}


def _delivery_ack_path(directory: Path, tick: int) -> Path:
    return directory / f'delivery-ack-{tick}.json'


async def run_child(directory: Path, *, variant: str, windows: int, roster: Path) -> dict:
    from websockets.asyncio.client import connect
    import uvicorn
    from app.services import runtime_process
    from scripts.launch_trusted_local_gameplay_mirror import request_enrollment
    seed_files = _files(directory / "state")
    main, actors, secret = _configure(directory / "state", roster)
    selected = {f"character:{actor}" for actor in actors[:160]}
    wire = WireEvidence(selected)
    received_ticks, delivery_received_at = {}, []
    sent_bytes = sent_count = 0
    parent = dict(parent_pid=os.getpid(), owner_pid=None, errors=[], variant=variant, windows=windows,
        population=len(actors), seed_files=seed_files)
    write_json(directory / "probe-config.json", dict(variant=variant, windows=windows))
    with patch.dict(os.environ, {"PARALLS_COST_PROBE_DIRECTORY": str(directory)}), \
            patch.object(runtime_process, "CHILD_TARGET", cost_owner_child), socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        listener.setblocking(False)
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(main.app, ws=main.RUNTIME_WEBSOCKET_PROTOCOL, host="127.0.0.1", port=port,
            ws_per_message_deflate=False, access_log=False, log_level="warning"))
        serving = asyncio.create_task(server.serve(sockets=[listener]))
        host = None
        try:
            while not server.started:
                if serving.done():
                    await serving
                    raise RuntimeError("cost_probe_startup_failed")
                await asyncio.sleep(.02)
            host = main.app.state.runtime_process
            parent["owner_pid"] = host.process.pid
            ready = await _owner_file(directory, "owner-ready.json", host.process)
            if ready != dict(owner_pid=host.process.pid, population=len(actors), variant=variant,
                    windows=windows, initial_tick=0, clock_profile="manual_window_cost"):
                raise ValueError("cost_probe_initial_driver_invalid")
            enrollment = await asyncio.to_thread(request_enrollment, backend_http_url=f"http://127.0.0.1:{port}",
                launch_profile_ref="population-cost-probe", launcher_secret=secret)
            async with LoopbackWebSocketByteProxy(port) as proxy:
                async with connect(f"ws://127.0.0.1:{proxy.port}/ws", compression=None, max_size=8 * 1024 * 1024) as client:
                    async def send(message):
                        nonlocal sent_bytes, sent_count
                        raw = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
                        await client.send(raw)
                        sent_bytes += len(raw.encode("utf-8"))
                        sent_count += 1

                    with (directory / "public-messages.jsonl").open("w", encoding="utf-8") as trace:
                        async def receive():
                            raw = await asyncio.wait_for(client.recv(), 30)
                            message = wire.receive(raw)
                            if message["message_type"] == "gameplay_mirror_delivery":
                                trace.write(json.dumps({"raw_text": raw, "packet_bytes": len(raw.encode("utf-8"))}, ensure_ascii=False) + "\n")
                                target = wire.snapshots[message["payload"]["actor_ref"]]
                                received_ticks[target.actor_ref] = target.groups["population_public"].payload["confirmed_tick"]
                                completed = min(received_ticks.values()) if len(received_ticks) == len(selected) else 0
                                if completed > len(delivery_received_at):
                                    if completed != len(delivery_received_at) + 1:
                                        raise ValueError("cost_probe_delivery_window_gap")
                                    received_at = perf_counter()
                                    delivery_received_at.append(received_at)
                                    write_json(_delivery_ack_path(directory, completed), dict(
                                        tick=completed, received_at=received_at, actor_count=len(received_ticks)))
                            return message

                        payload = enrollment.model_dump(mode="json")
                        payload.update(protocol_version=2, capability_offer=dict(protocol_version=2,
                            supports_snapshot=True, supports_delta=variant != "full", supports_receipt=False,
                            projection_schemas=["gameplay_runtime_state.godot.v1"]))
                        await send(dict(message_type="websocket_session_bind", payload=payload))
                        while (await receive())["message_type"] != "websocket_session_bound":
                            pass
                        for actor in sorted(selected):
                            await send(dict(message_type="gameplay_mirror_subscribe", payload=dict(actor_ref=actor)))
                            while actor not in wire.snapshots:
                                await receive()
                        (directory / "start").touch()
                        async with asyncio.timeout(windows * 15 + 30):
                            while not all(snapshot.groups["population_public"].payload["confirmed_tick"] >= windows
                                          for snapshot in wire.snapshots.values()):
                                await receive()
                await proxy.wait_closed_connections()
                network = proxy.measurements()
            (directory / "finish").touch()
            owner = await _owner_file(directory, "owner-result.json", host.process)
            parent.update(delivery_received_at=delivery_received_at, public_oracle=wire.public_oracle(windows=windows),
                network={**network, "application_payload_bytes": sent_bytes + wire.bytes_received,
                    "application_bytes_by_direction": {"client_to_backend": sent_bytes, "backend_to_client": wire.bytes_received},
                    "server_bytes_by_kind": dict(wire.bytes_by_kind), "delivery_counts": dict(wire.counts),
                    "client_send_count": sent_count, "resync_count": 0},
                reconstruction_segments=[asdict(measure_population_transport(
                    lambda value=value: GameplayMirrorDeliveryEnvelope.model_validate(value), scope="public", audience="godot"))
                    for value in wire.latest_payloads.values()])
        except BaseException as error:
            parent["errors"].append(type(error).__name__)
            raise
        finally:
            server.should_exit = True
            try:
                await asyncio.wait_for(serving, 40)
            except BaseException as error:
                parent["errors"].append(type(error).__name__)
                raise
            finally:
                lifecycle = getattr(server, "lifespan", None)
                parent["asgi_lifecycle"] = {name: getattr(lifecycle, name, None) for name in
                    ("startup_failed", "shutdown_failed", "error_occurred")}
                parent["child_exit_code"] = host.process.exitcode if host is not None else None
                parent["peak_rss_bytes"] = peak_rss_bytes()
                write_json(directory / 'parent-qos.json', main.app.state.process_qos)
                write_json(directory / "parent-observed.json", parent)
    result = merge_process_evidence(ready, owner, parent)
    write_json(directory / "result.json", result)
    return result


def _collect(directory: Path, *, population: int, windows: int, repeats: int, identity: dict) -> dict:
    started_at, source, revision = identity["started_at"], identity["source"], identity["base_commit"]
    roster = directory / "roster.json"
    write_json(roster, {"actor_ids": ["char_a", "char_b", *(f"resident_{index:05d}" for index in range(population - 2))]})
    seed = directory / "seed-state"
    seed.mkdir()
    def child(mode: str, output: Path):
        command = [sys.executable, str(Path(__file__).resolve()), "--child", mode, "--output", str(output),
                   "--roster", str(roster), "--windows", str(windows)]
        with (output / "process.log").open("w", encoding="utf-8") as log:
            completed = subprocess.run(command, cwd=ROOT, env=child_environment(), stdout=log, stderr=subprocess.STDOUT,
                                       timeout=windows * 15 + 120, check=False)
        if completed.returncode:
            raise RuntimeError(f"cost_probe_child_failed:{mode}:{output}")
    child("seed", seed)
    # 日志不是 DB 的一部分，复制时从身份集合排除且保留原始 seed 日志。
    seed_files = {name: checksum for name, checksum in _files(seed).items() if name != "process.log"}
    results = {"before": [], "after": []}
    for ordinal in range(repeats):
        for variant in ("before", "after"):
            output = directory / f"{variant}-{ordinal}"
            output.mkdir()
            shutil.copytree(seed, output / "state", ignore=shutil.ignore_patterns("process.log"))
            if _files(output / "state") != seed_files:
                raise ValueError("cost_probe_seed_copy_mismatch")
            child(variant, output)
            results[variant].append(json.loads((output / "result.json").read_text(encoding="utf-8")))
    full_output = directory / "full"
    full_output.mkdir()
    shutil.copytree(seed, full_output / "state", ignore=shutil.ignore_patterns("process.log"))
    child("full", full_output)
    full = json.loads((full_output / "result.json").read_text(encoding="utf-8"))
    comparison = compare_runs(results["before"], results["after"])
    if source_manifest() != source or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != revision:
        raise ValueError("cost_probe_source_changed")
    passed = comparison["equivalent"] and comparison["improvement_passed"] and full["oracle"] == results["after"][0]["oracle"]
    report = {"schema_version": 1, "base_commit": revision, "source": source,
        "started_at": started_at, "finished_at": datetime.now(timezone.utc).isoformat(),
        "environment": {"python": platform.python_version(), "sqlite": sqlite3.sqlite_version, "os": platform.platform(), "cpu": platform.processor()},
        "population": population, "windows": windows, "repeats": repeats, "seed": 0,
        "model_responses": "identical empty provider transcript: B0 workload with local Character/disabled Siming",
        "baseline": "current code with pre-optimization per-actor confirmation validation; not an old checkout",
        "comparison": comparison, "full_transport": full["network"],
        "godot_status": "godot_unverified", "unprofiled_1x_short_gate": "not_run",
        "clock_profile": "manual_window_cost",
        "formal_cost_matrix": population == 1000 and windows == 30 and repeats == 5,
        "status": ("cost_comparison_passed" if population == 1000 and windows == 30 and repeats == 5 else "smoke_checked") if passed else "failed",
        "closure_status": "incomplete"}
    write_json(directory / "transport-before.json", {"runs": results["before"]})
    write_json(directory / "transport-after.json", {"runs": results["after"]})
    (directory / "transport-comparison.md").write_text(
        "# 真实传输对照\n\n| 指标 | before | after |\n|---|---:|---:|\n" +
        "\n".join(f"| {name} | {comparison['before_' + field]['median']:.3f} | {comparison['after_' + field]['median']:.3f} |"
                  for name, field in (("owner 窗口 ms", "window_ms"), ("最后一份投影校验完成 ms", "delivery_complete_ms"))) +
        "\n\nowner 启用 cProfile，客户端校验也计入端到端；未插桩 1× 短验收另跑。"
        "逐窗等全部订阅角色真实收包后再推进，非实时1×证明。分段字段为重建微基准，不与网络/窗口指标相加。Godot 未运行。\n", encoding="utf-8")
    return report


def collect(directory: Path, *, population: int, windows: int, repeats: int):
    if population not in {100, 1000, 10000} or windows < 1 or repeats < 1:
        raise ValueError("invalid_cost_probe_matrix")
    directory.mkdir(parents=True, exist_ok=False)
    from scripts.verification.population_process_qos import recorded_high_qos
    try:
        with recorded_high_qos(directory / 'collector-qos.json'):
            result = _collect_with_policy(directory, population=population, windows=windows, repeats=repeats)
        return result
    finally:
        path = directory / 'manifest.json'
        if path.exists():
            manifest = json.loads(path.read_text(encoding='utf-8'))
            if sys.exc_info()[0] is not None:
                manifest.update(passed=False, status='failed')
                manifest.setdefault('errors', []).append('collection_scope:' + sys.exc_info()[0].__name__)
            manifest['raw_artifacts'] = _raw_artifacts(directory)
            write_json(path, manifest)
            if 'result' in locals():
                result.update(manifest)


def _collect_with_policy(directory: Path, *, population: int, windows: int, repeats: int) -> dict:
    if population not in {100, 1000, 10000} or windows < 1 or repeats < 1:
        raise ValueError("invalid_cost_probe_matrix")
    report = {"schema_version": 1, "clock_profile": "manual_window_cost", "status": "running", "closure_status": "incomplete",
              "godot_status": "godot_unverified", "started_at": datetime.now(timezone.utc).isoformat(),
              "source": source_manifest(),
              "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
    write_json(directory / "manifest.json", report)
    try:
        report = _collect(directory, population=population, windows=windows, repeats=repeats, identity=report)
        return report
    except BaseException as exc:
        report.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["raw_artifacts"] = _raw_artifacts(directory)
        write_json(directory / "manifest.json", report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-artifacts", type=Path)
    parser.add_argument("--require-fresh-commit")
    parser.add_argument("--population", type=int, default=1000)
    parser.add_argument("--windows", type=int, default=30)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--child", choices=("seed", "before", "after", "full"), help=argparse.SUPPRESS)
    parser.add_argument("--roster", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.verify_artifacts:
        if not args.require_fresh_commit or args.output or args.child:
            parser.error("verification requires --require-fresh-commit and excludes --output/--child")
        report = verify_artifacts(args.verify_artifacts.resolve(), expected_commit=args.require_fresh_commit)
        print(json.dumps(report, ensure_ascii=False))
        return 0
    if args.output is None:
        parser.error("collection requires --output")
    if args.child == "seed":
        asyncio.run(_seed(args.output, args.roster))
    elif args.child:
        asyncio.run(run_child(args.output, variant=args.child, windows=args.windows, roster=args.roster))
    else:
        report = collect(args.output.resolve(), population=args.population, windows=args.windows, repeats=args.repeats)
        print(json.dumps({"status": report["status"], "closure_status": report["closure_status"]}))
        return 0 if report["status"] in {"cost_comparison_passed", "smoke_checked"} else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
