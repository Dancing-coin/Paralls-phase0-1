"""外机人口渲染采集与原始证据门禁；不把静态脚本或headless结果升级为通过。"""
from __future__ import annotations

import csv
from hashlib import sha256
import json
import math
import re
from pathlib import Path
import sys
import struct
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.verification.population_benchmark_metrics import percentile


def read_json(text: str):
    def reject_constant(value):
        raise ValueError("nonfinite_json")
    return json.loads(text, parse_constant=reject_constant)


def json_lines(path: Path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            yield read_json(line)


def digest(data: bytes) -> str:
    return "sha256:" + sha256(data).hexdigest()


def validate_frames(path: Path, population: int) -> dict:
    """保留并检查每一帧；禁止丢弃慢帧、非有限值或缺失行后计算百分位。"""
    if population not in (100, 1000, 10000):
        raise ValueError("population_tier_invalid")
    timings = {key: [] for key in ("wall_frame_ms", "process_ms", "render_cpu_ms", "render_gpu_ms")}
    expected_counts = dict(near=32, far=min(160, population) - 32,
                           invisible=max(0, population - 160), active_marker_count=min(160, population))
    previous_us = count = 0
    with path.open(encoding="utf-8", newline="") as stream:
        for count, row in enumerate(csv.DictReader(stream), start=1):
            if int(row["frame_index"]) != count:
                raise ValueError("frame_sequence_invalid")
            elapsed_us = int(row["elapsed_us"])
            if elapsed_us <= previous_us:
                raise ValueError("frame_time_invalid")
            for key, values in timings.items():
                value = float(row[key])
                if not math.isfinite(value) or value < 0:
                    raise ValueError("frame_number_invalid")
                values.append(value)
            if abs(timings["wall_frame_ms"][-1] - (elapsed_us - previous_us) / 1000) > .01:
                raise ValueError("frame_time_invalid")
            if any(int(row[key]) != value for key, value in expected_counts.items()):
                raise ValueError("lod_count_mismatch")
            if int(row["confirmed_tick"]) < 0:
                raise ValueError("confirmed_tick_invalid")
            previous_us = elapsed_us
    if count < 2 or previous_us < 60_000_000:
        raise ValueError("frame_duration_short")
    if not any(timings["render_gpu_ms"]):
        raise ValueError("gpu_measurement_missing")
    if not any(timings["render_cpu_ms"]) or not any(timings["process_ms"]):
        raise ValueError("cpu_measurement_missing")
    statistics = {key: dict(p50=percentile(values, .5), p95=percentile(values, .95),
                           p99=percentile(values, .99), max=max(values)) for key, values in timings.items()}
    if statistics["wall_frame_ms"]["p95"] > 33.3:
        raise ValueError("frame_p95_budget_exceeded")
    stutter = sum(value > 33.3 for value in timings["wall_frame_ms"])
    return dict(frame_count=count, duration_seconds=previous_us / 1_000_000,
                stutter_count=stutter, stutter_ratio=stutter / count, **statistics)


def _checked_elapsed_us(row: dict, previous: int) -> int:
    elapsed = row.get("elapsed_us")
    if type(elapsed) is not int or elapsed < 0 or elapsed < previous:
        raise ValueError("trace_time_invalid")
    return elapsed


def validate_messages(directory: Path, actor_refs: set[str]) -> dict:
    """从原包重算字节和hash，并将每次实际显示更新连回已验证的wire切点。"""
    observations = list(json_lines(directory / "observations.jsonl"))
    applied = {}
    previous_update = 0
    screenshots = {}
    previous_observation_us = 0
    for observation in observations:
        previous_observation_us = _checked_elapsed_us(observation, previous_observation_us)
        wire = observation["wire"]
        key = (wire["connection_epoch"], wire["delivery_sequence"], wire["actor_ref"])
        if "screenshot" in observation:
            name = observation["screenshot"]
            if name not in ("before.png", "after.png") or name in screenshots:
                raise ValueError("screenshot_observation_invalid")
            screenshots[name] = observation
            continue
        if key in applied or observation["actor_ref"] != key[2] or observation["marker_update"] <= previous_update:
            raise ValueError("marker_observation_invalid")
        previous_update = observation["marker_update"]
        applied[key] = observation
    epoch = sequence = gap_count = applied_delta_count = 0
    bases, byte_counts, matched, full_after_gap, reconnect_full = {}, {}, {}, set(), set()
    last_gap_epoch = 0
    previous_message_us = previous_matched_update = 0
    epochs = set()
    for row in json_lines(directory / "messages.jsonl"):
        previous_message_us = _checked_elapsed_us(row, previous_message_us)
        raw = row["raw_text"]
        if type(row["packet_bytes"]) is not int or len(raw.encode("utf-8")) != row["packet_bytes"]:
            raise ValueError("packet_bytes_mismatch")
        message = read_json(raw)
        if message["message_type"] == "gameplay_mirror_resync_required":
            control = message.get("payload", {})
            if (set(control) != {"actor_ref", "reason_code"} or control["actor_ref"] not in actor_refs
                    or control["reason_code"] != "mirror_backpressure"):
                raise ValueError("resync_control_invalid")
            byte_counts["gameplay_mirror_resync_required"] = byte_counts.get("gameplay_mirror_resync_required", 0) + row["packet_bytes"]
            bases.pop(control["actor_ref"], None)
            continue  # actor 控制消息没有 epoch/sequence，不消费连接 cursor。
        if message["message_type"] != "gameplay_mirror_delivery":
            raise ValueError("unexpected_population_packet")
        delivery = message["payload"]
        kind = delivery["delivery_kind"]
        if kind not in ("snapshot", "delta"):
            raise ValueError("unexpected_population_delivery")
        byte_counts[kind] = byte_counts.get(kind, 0) + row["packet_bytes"]
        next_epoch, next_sequence, actor = (delivery[name] for name in ("connection_epoch", "delivery_sequence", "actor_ref"))
        if type(next_epoch) is not int or type(next_sequence) is not int or next_epoch < epoch or next_epoch < 1 or next_sequence < 1 or actor not in actor_refs:
            raise ValueError("wire_scope_or_epoch_invalid")
        if next_epoch != epoch:
            epoch, sequence = next_epoch, 0
            epochs.add(epoch)
            bases.clear()
        if next_sequence <= sequence:
            continue  # 已消费序号仅计真实收包字节，不应用、不推进 cursor，也不产生 gap。
        key = (epoch, next_sequence, actor)
        gap = next_sequence != sequence + 1
        sequence = next_sequence
        if gap:
            gap_count += 1
            last_gap_epoch = epoch
            full_after_gap.clear()
            bases.clear()
            if key in applied:
                raise ValueError("gap_content_was_applied")
            continue  # bridge明确丢弃gap-bearing内容；后续full才能恢复base。
        projection = delivery["payload"]
        canonical = projection["canonical_snapshot_json"]
        checksum = projection["snapshot_checksum" if kind == "snapshot" else "target_snapshot_checksum"]
        if digest(canonical.encode("utf-8")) != checksum:
            raise ValueError("wire_checksum_invalid")
        body = read_json(canonical)
        for name in ("actor_ref", "facade_revision", "source_revision_vector"):
            if delivery[name] != projection[name] or projection[name] != body[name]:
                raise ValueError("wire_anchor_mismatch")
        if delivery["projection_schema"] != projection["projection_kind"] or projection["projection_kind"] != "gameplay_runtime_state.godot.v1":
            raise ValueError("wire_schema_mismatch")
        for name in ("schema_capabilities", "enabled_state_groups"):
            if projection[name] != body[name]:
                raise ValueError("wire_anchor_mismatch")
        if kind == "snapshot" and projection["groups"] != body["groups"]:
            raise ValueError("wire_payload_mismatch")
        if key not in applied:
            continue  # 已退订/待resync消息允许收包，但不得伪造显示更新。
        observation = applied[key]
        if observation["marker_update"] <= previous_matched_update:
            raise ValueError("marker_wire_order_invalid")
        if observation["elapsed_us"] < row["elapsed_us"]:
            raise ValueError("marker_precedes_packet")
        previous_matched_update = observation["marker_update"]
        public = body["groups"]["population_public"]["payload"]
        if public["actor_id"] != actor.removeprefix("character:") or observation["confirmed_tick"] != public["confirmed_tick"] or observation["facade_revision"] != body["facade_revision"]:
            raise ValueError("marker_anchor_mismatch")
        if kind == "delta":
            if any(delivery.get(name) != projection[name] for name in (
                    "base_facade_revision", "base_snapshot_checksum", "target_snapshot_checksum")):
                raise ValueError("wire_anchor_mismatch")
            base = bases.get(actor)
            if base is None or projection["base_snapshot_checksum"] != base[1] or projection["base_facade_revision"] != base[0]["facade_revision"]:
                raise ValueError("applied_delta_base_invalid")
            groups = dict(base[0]["groups"])
            removed = projection["removed_group_ids"]
            if set(removed) & projection["groups"].keys():
                raise ValueError("applied_delta_groups_invalid")
            for group in removed:
                groups.pop(group, None)
            groups.update(projection["groups"])
            if groups != body["groups"]:
                raise ValueError("wire_payload_mismatch")
            applied_delta_count += 1
        else:
            if epoch == last_gap_epoch:
                full_after_gap.add(actor)
            if len(epochs) > 1:
                reconnect_full.add(actor)
        bases[actor] = (body, checksum)
        matched[key] = observation
    visible = min(160, len(actor_refs))
    if len(matched) != len(applied) or not applied:
        raise ValueError("unmatched_marker_observation")
    if not gap_count or len(full_after_gap) < visible or len(epochs) < 2 or len(reconnect_full) < visible:
        raise ValueError("protocol_recovery_evidence_missing")
    if set(screenshots) != {"before.png", "after.png"}:
        raise ValueError("screenshot_evidence_missing")
    for observation in screenshots.values():
        wire = observation["wire"]
        anchor = matched.get((wire["connection_epoch"], wire["delivery_sequence"], wire["actor_ref"]))
        if anchor is None or anchor["marker_update"] != observation["marker_update"] or anchor["confirmed_tick"] != observation["confirmed_tick"] or observation["elapsed_us"] < anchor["elapsed_us"]:
            raise ValueError("screenshot_anchor_mismatch")
    if screenshots["after.png"]["confirmed_tick"] <= screenshots["before.png"]["confirmed_tick"]:
        raise ValueError("visible_tick_did_not_advance")
    return dict(application_packet_bytes=byte_counts, matched_marker_updates=len(matched),
                applied_delta_count=applied_delta_count,
                gap_count=gap_count, connection_epochs=sorted(epochs), screenshots=screenshots)


def validate_png(path: Path) -> str:
    """检查固定分辨率 PNG 的完整容器、CRC、解压长度；不合成或修补截图。"""
    data = path.read_bytes()
    if not 32 < len(data) <= 10_000_000 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("screenshot_png_invalid")
    offset, compressed, expected = 8, bytearray(), 0
    ended = False
    while offset + 12 <= len(data):
        size = struct.unpack_from(">I", data, offset)[0]
        kind, body = data[offset + 4:offset + 8], data[offset + 8:offset + 8 + size]
        if offset + size + 12 > len(data):
            raise ValueError("screenshot_png_invalid")
        crc = struct.unpack_from(">I", data, offset + 8 + size)[0]
        if zlib.crc32(kind + body) != crc:
            raise ValueError("screenshot_png_invalid")
        if offset == 8:
            if kind != b"IHDR" or size != 13:
                raise ValueError("screenshot_png_invalid")
            width, height, depth, color, compression, filters, interlace = struct.unpack(">IIBBBBB", body)
            if (width, height, depth, compression, filters, interlace) != (1280, 720, 8, 0, 0, 0) or color not in (2, 6):
                raise ValueError("screenshot_png_invalid")
            stride = width * (3 if color == 2 else 4) + 1
            expected = height * stride
        elif kind == b"IHDR":
            raise ValueError("screenshot_png_invalid")
        if kind == b"IDAT":
            compressed.extend(body)
        offset += size + 12
        if kind == b"IEND":
            ended = size == 0 and offset == len(data)
            break
    if not ended or not compressed:
        raise ValueError("screenshot_png_invalid")
    inflater = zlib.decompressobj()
    try:
        pixels = inflater.decompress(compressed, expected + 1)
    except zlib.error:
        raise ValueError("screenshot_png_invalid") from None
    if len(pixels) != expected or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail or any(pixels[index] > 4 for index in range(0, expected, stride)):
        raise ValueError("screenshot_png_invalid")
    return digest(data)


def validate_lod_boundary(directory: Path, actor_refs: set[str]) -> dict:
    before, after = [read_json((directory / f"authority-{name}.json").read_text(encoding="utf-8")) for name in ("before", "after")]
    if before["authority"] != after["authority"]:
        raise ValueError("lod_authority_changed")
    authority = before["authority"]
    if (not before.get("scheduling_paused") or not after.get("scheduling_paused") or
            authority["population"] != len(actor_refs) or authority["advanced_count"] != len(actor_refs) or authority["confirmed_tick"] <= 0):
        raise ValueError("lod_authority_invalid")
    required_digests = {"receipt_digest", "checkpoint_digest", "character_revision_digest", "population_state_digest",
                        "gameplay_replay_digest", "gameplay_events_digest", "hot_revision_digest", "stream_revision_digest", "owner_receipt_digest"}
    if (not after.get("resumed_same_driver") or not all(isinstance(authority.get(key), str) and authority[key] for key in required_digests)
            or type(authority.get("authority_head")) is not int or authority["authority_head"] < 1):
        raise ValueError("lod_authority_invalid")
    visible = min(160, len(actor_refs))
    counts = dict(near=32, far=visible - 32, invisible=len(actor_refs) - visible, active_marker_count=visible)
    lod = [read_json((directory / f"lod-{name}.json").read_text(encoding="utf-8")) for name in ("before", "after")]
    for observation, backend in zip(lod, (before, after)):
        members, near = set(observation["members"]), set(observation["near_members"])
        if (len(observation["members"]) != len(members) or len(members) != visible or not members <= actor_refs
                or len(observation["near_members"]) != len(near) or len(near) != 32 or not near <= members
                or observation["counts"] != counts or set(backend["subscriptions"]) != members
                or observation["confirmed_tick"] != authority["confirmed_tick"]):
            raise ValueError("lod_observation_mismatch")
    if len(actor_refs) == 100:
        changed = set(lod[0]["near_members"]) != set(lod[1]["near_members"]) and lod[0]["camera_position"] != lod[1]["camera_position"]
    else:
        changed = set(lod[0]["members"]) != set(lod[1]["members"])
    if not changed:
        raise ValueError("lod_rotation_missing")
    if type(lod[0].get("elapsed_us")) is not int or type(lod[1].get("elapsed_us")) is not int or not 0 < lod[0]["elapsed_us"] < lod[1]["elapsed_us"]:
        raise ValueError("lod_time_invalid")
    return dict(authority_unchanged=True, confirmed_tick=authority["confirmed_tick"], population=len(actor_refs),
                before_members=lod[0]["members"], after_members=lod[1]["members"])


def _validate_capture_timeline(directory: Path, capture: dict, messages: dict) -> None:
    fields = ("ready_elapsed_us", "sample_start_elapsed_us", "sample_end_elapsed_us", "capture_end_elapsed_us")
    if any(type(capture.get(key)) is not int for key in fields):
        raise ValueError("capture_timeline_missing")
    ready, start, end, finished = (capture[key] for key in fields)
    before, after = (messages["screenshots"][name]["elapsed_us"] for name in ("before.png", "after.png"))
    lod = [read_json((directory / f"lod-{name}.json").read_text(encoding="utf-8"))["elapsed_us"]
           for name in ("before", "after")]
    if (not 0 <= ready <= before <= start < end <= after <= lod[0] <= lod[1] <= finished
            or start - ready != capture["warmup_us"] or end - start != capture["sample_duration_us"]):
        raise ValueError("capture_timeline_mismatch")
    for name in ("messages", "observations"):
        if any(row["elapsed_us"] > finished for row in json_lines(directory / f"{name}.jsonl")):
            raise ValueError("capture_timeline_trace_outside")
    # CSV 是相对 sampling-start，marker 是相对 probe-start；线性合并，拒绝拼接另一段 CSV。
    markers = iter(row for row in json_lines(directory / "observations.jsonl") if "screenshot" not in row)
    upcoming = next(markers, None)
    tick = None
    with (directory / "frame-times.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            elapsed = start + int(row["elapsed_us"])
            while upcoming is not None and upcoming["elapsed_us"] <= elapsed:
                tick = upcoming["confirmed_tick"]
                upcoming = next(markers, None)
            if elapsed > end or tick != int(row["confirmed_tick"]):
                raise ValueError("capture_timeline_frame_marker_mismatch")


def validate_capture(directory: Path, population: int) -> dict:
    capture = read_json((directory / "godot-capture.json").read_text(encoding="utf-8"))
    version = capture.get("godot_version", {})
    if (capture.get("status") != "captured" or capture.get("population") != population
            or [version.get(key) for key in ("major", "minor", "patch", "status")] != [4, 6, 3, "stable"]
            or capture.get("renderer") != "forward_plus" or capture.get("driver") != "vulkan"
            or capture.get("resolution") != [1280, 720] or capture.get("vsync") != 0
            or capture.get("scene") != "res://scenes/phase0/PopulationProbe.tscn" or not capture.get("gpu")):
        raise ValueError("render_capture_invalid")
    actors = read_json((directory / "roster.json").read_text(encoding="utf-8"))["actor_ids"]
    refs = {f"character:{actor}" for actor in actors}
    if len(actors) != len(refs) or len(refs) != population:
        raise ValueError("capture_roster_invalid")
    frames = validate_frames(directory / "frame-times.csv", population)
    if (any(type(capture[key]) is not int for key in ("warmup_us", "sample_count", "sample_duration_us"))
            or capture["warmup_us"] < 10_000_000 or capture["sample_count"] != frames["frame_count"]
            or capture["sample_duration_us"] != round(frames["duration_seconds"] * 1_000_000)):
        raise ValueError("capture_sample_mismatch")
    messages = validate_messages(directory, refs)
    if capture["application_packet_bytes"] != messages["application_packet_bytes"] or messages["applied_delta_count"] < 1:
        raise ValueError("capture_packet_mismatch")
    pngs = {name: validate_png(directory / name) for name in ("before.png", "after.png")}
    if len(set(pngs.values())) != 2:
        raise ValueError("visible_screenshot_unchanged")
    for name, tick in (("before.png", capture["first_tick"]), ("after.png", capture["last_tick"])):
        expected_counts = dict(near=32, far=min(160, population) - 32, invisible=max(0, population - 160), active_marker_count=min(160, population))
        if messages["screenshots"][name]["confirmed_tick"] != tick or messages["screenshots"][name].get("counts") != expected_counts or capture.get("counts") != expected_counts:
            raise ValueError("capture_tick_mismatch")
    if any(capture.get(key) is not True for key in ("gap_seen", "resync_recovered", "rotation_complete", "reconnect_complete")):
        raise ValueError("capture_recovery_mismatch")
    _validate_capture_timeline(directory, capture, messages)
    boundary = validate_lod_boundary(directory, refs)
    lod_before = read_json((directory / "lod-before.json").read_text(encoding="utf-8"))
    if lod_before["elapsed_us"] < messages["screenshots"]["after.png"]["elapsed_us"]:
        raise ValueError("lod_precedes_sampling")
    return dict(status="passed", godot_status="runtime_verified", population=population, frames=frames,
                messages=messages, png_sha256=pngs, lod_boundary=boundary,
                ws_frame_bytes=None, ws_frame_bytes_reason="Only WebSocket application packet bytes are measured")


def validate_backend_process(directory: Path, population: int, parent_pid: int) -> None:
    """外机父进程退出成功之外，还要有原 owner 及 ASGI 的正常终态。"""
    ready, owner_ready, owner, parent = [read_json((directory / name).read_text(encoding='utf-8')) for name in
        ('backend-ready.json', 'owner-ready.json', 'owner-observed.json', 'backend-observed.json')]
    child_pid = owner_ready.get('owner_pid')
    boundaries = [read_json((directory / f'authority-{stage}.json').read_text(encoding='utf-8')) for stage in ('before', 'after')]
    lifecycle = parent.get('asgi_lifecycle')
    if (type(parent_pid) is not int or parent_pid <= 0 or type(child_pid) is not int or child_pid <= 0
            or child_pid == parent_pid
            or any(type(row.get('owner_pid')) is not int or row['owner_pid'] != child_pid for row in (ready, owner, parent, *boundaries))
            or any(type(row.get('parent_pid')) is not int or row['parent_pid'] != parent_pid for row in (ready, parent))
            or any(type(row.get('population')) is not int or row['population'] != population
                   or row.get('clock_profile') != 'benchmark_1x' for row in (ready, owner_ready))
            or owner.get('errors') != [] or parent.get('errors') != []
            or type(parent.get('child_exit_code')) is not int or parent['child_exit_code'] != 0
            or not isinstance(lifecycle, dict) or set(lifecycle) != {'startup_failed', 'shutdown_failed', 'error_occurred'}
            or any(value is not False for value in lifecycle.values())):
        raise ValueError('render_backend_process_invalid')


def verify_artifacts(directory: Path) -> dict:
    from scripts.verification.population_godot_runner import source_manifest
    manifest = read_json((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("status") != "passed" or manifest.get("source") != source_manifest():
        raise ValueError("manifest_source_or_status_invalid")
    expected = manifest["artifacts"]
    actual = {path.relative_to(directory).as_posix(): digest(path.read_bytes())
              for path in directory.rglob("*") if path.is_file() and path != directory / "manifest.json"}
    if actual != expected:
        raise ValueError("artifact_digest_mismatch")
    allowed_names = {"roster.json", "backend.log", "godot.log", "commands.json", "backend-ready.json", "stage.json", "authority-before.json",
                     "authority-after.json", "frame-times.csv", "messages.jsonl", "observations.jsonl", "before.png", "after.png",
                     "godot-capture.json", "lod-before.json", "lod-after.json", "result.json", "processes.json",
                     "owner-ready.json", "owner-observed.json", "backend-observed.json", "owner-qos.json", "parent-qos.json"}
    for name in actual:
        parts = Path(name).parts
        if name not in {"godot-import.log", "dependencies.txt", "collector-qos.json"} and not (len(parts) == 2 and parts[0] in {"100", "1000"} and parts[1] in allowed_names):
            raise ValueError("unexpected_artifact")
    from scripts.verification.population_process_qos import require_restored_qos
    collector_qos = read_json((directory / "collector-qos.json").read_text(encoding="utf-8"))
    require_restored_qos(collector_qos)
    collector_pid = manifest.get("collector_pid")
    if type(collector_pid) is not int or collector_pid <= 0 or collector_qos["pid"] != collector_pid:
        raise ValueError("process_qos_pid_mismatch")
    environment = manifest["environment"]
    if environment.get("python") != "3.12.14" or not environment.get("godot_version", "").startswith("4.6.3.stable"):
        raise ValueError("manifest_environment_invalid")
    for population in (100, 1000):
        case = directory / str(population)
        if not all((case / name).is_file() for name in allowed_names):
            raise ValueError("artifact_missing")
        processes = read_json((case / "processes.json").read_text(encoding="utf-8"))
        if processes.get("backend_exit_code") != 0 or processes.get("godot_exit_code") != 0 or processes.get("clean_backend_shutdown") is not True:
            raise ValueError("owned_process_exit_invalid")
        validate_backend_process(case, population, processes.get('backend_pid'))
        owner_ready = read_json((case / "owner-ready.json").read_text(encoding="utf-8"))
        for role, pid in (("parent", processes.get("backend_pid")), ("owner", owner_ready.get("owner_pid"))):
            qos = read_json((case / f"{role}-qos.json").read_text(encoding="utf-8"))
            require_restored_qos(qos)
            if qos["pid"] != pid:
                raise ValueError("process_qos_pid_mismatch")
        ready = read_json((case / "backend-ready.json").read_text(encoding="utf-8"))
        if ready.get("clock_profile") != "benchmark_1x" or ready.get("population") != population or ready.get("model_mode") != "local_fixture" or ready.get("compression") != "disabled":
            raise ValueError("backend_profile_mismatch")
        command = read_json((case / "commands.json").read_text(encoding="utf-8"))["godot"]
        if "--headless" in command or any(flag not in command or command.index(flag) + 1 >= len(command)
                or command[command.index(flag) + 1] != value for flag, value in (
                    ("--scene", "res://scenes/phase0/PopulationProbe.tscn"), ("--rendering-method", "forward_plus"),
                    ("--rendering-driver", "vulkan"), ("--resolution", "1280x720"))):
            raise ValueError("godot_command_mismatch")
        if re.search(r"(?m)^(?:SCRIPT ERROR:|ERROR:|Parse Error:)", (case / "godot.log").read_text(encoding="utf-8")):
            raise ValueError("godot_runtime_log_errors")
    if not (directory / "dependencies.txt").is_file() or re.search(r"(?m)^(?:SCRIPT ERROR:|ERROR:|Parse Error:)", (directory / "godot-import.log").read_text(encoding="utf-8")):
        raise ValueError("godot_import_evidence_invalid")
    cases = {str(population): validate_capture(directory / str(population), population) for population in (100, 1000)}
    if cases != manifest["cases"]:
        raise ValueError("artifact_result_mismatch")
    return dict(status="passed", godot_status="runtime_verified", source_sha256=manifest["source"]["source_sha256"], cases=cases)


def main() -> int:
    import argparse
    import asyncio
    from datetime import datetime, timezone
    from scripts.verification.population_godot_runner import backend_child, collect, write_json
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--collect", type=Path, metavar="NEW_OUTPUT_DIRECTORY")
    group.add_argument("--verify-artifacts", type=Path)
    group.add_argument("--backend-child", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--state-directory", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--godot-exe", type=Path)
    parser.add_argument("--python-exe", type=Path, help="harness 使用的当前 Python，必须与本进程一致")
    args = parser.parse_args()
    if args.python_exe and args.python_exe.resolve() != Path(sys.executable).resolve():
        parser.error("--python-exe must match the current interpreter")
    profile_run = not (args.collect or args.verify_artifacts or args.backend_child)
    if profile_run:
        args.collect = ROOT / ".harness/verification" / ("population-godot-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    if args.backend_child:
        if not args.state_directory:
            parser.error("--state-directory is required for backend child")
        asyncio.run(backend_child(args.backend_child.resolve(), args.state_directory.resolve()))
        return 0
    if args.collect:
        if not args.godot_exe:
            parser.error("--godot-exe is required with --collect")
        result = collect(args.collect.resolve(), args.godot_exe.resolve())
    else:
        try:
            result = verify_artifacts(args.verify_artifacts.resolve())
        except Exception as error:
            result = dict(status="failed", godot_status="godot_unverified", error=f"{type(error).__name__}:{error}")
    if profile_run:
        write_json(ROOT / ".harness/verification/population-godot-runtime-report.json", dict(
            schema_version=1, profile="population-godot-runtime", status=result["status"],
            godot_status=result["godot_status"], manifest=str(args.collect.resolve() / "manifest.json"),
            overall_population_godot_runtime_passed=result["status"] == "passed" and result["godot_status"] == "runtime_verified"))
    print(json.dumps({key: value for key, value in result.items() if key in {"status", "godot_status", "error", "source_sha256"}}, ensure_ascii=False))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
