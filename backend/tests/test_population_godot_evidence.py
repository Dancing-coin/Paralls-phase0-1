import csv
from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.verification.verify_population_godot_runtime import digest, validate_frames, validate_messages


def _frames(path, *, population=100, frame_us=20000, mutate=None):
    rows = []
    for index in range(1, 3001):
        rows.append(dict(frame_index=index, elapsed_us=index * frame_us, wall_frame_ms=frame_us / 1000,
                         process_ms=2, render_cpu_ms=1, render_gpu_ms=1,
                         near=32, far=min(160, population) - 32, invisible=max(0, population - 160),
                         active_marker_count=min(160, population), confirmed_tick=1 + index // 50))
    if mutate:
        mutate(rows)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.mark.parametrize("population", [100, 1000, 10000])
def test_raw_frame_gate_checks_each_tier_without_treating_invisible_as_missing(tmp_path, population):
    result = validate_frames(_frames(tmp_path / "frames.csv", population=population), population)
    assert result["frame_count"] == 3000
    assert result["duration_seconds"] == 60
    assert result["wall_frame_ms"]["p95"] == 20
    assert result["stutter_count"] == 0


@pytest.mark.parametrize("mutation, error", [
    (lambda rows: rows[8].update(wall_frame_ms="nan"), "frame_number_invalid"),
    (lambda rows: rows[8].update(near=33), "lod_count_mismatch"),
    (lambda rows: rows[8].update(elapsed_us=0), "frame_time_invalid"),
    (lambda rows: rows.pop(8), "frame_sequence_invalid"),
    (lambda rows: rows.pop(), "frame_duration_short"),
    (lambda rows: [row.update(render_gpu_ms=0) for row in rows], "gpu_measurement_missing"),
])
def test_bad_raw_samples_fail_instead_of_being_filtered_out(tmp_path, mutation, error):
    path = _frames(tmp_path / "frames.csv", mutate=mutation)
    with pytest.raises(ValueError, match=error):
        validate_frames(path, 100)


def test_slow_real_frames_fail_the_33_3ms_gate(tmp_path):
    with pytest.raises(ValueError, match="frame_p95_budget_exceeded"):
        validate_frames(_frames(tmp_path / "frames.csv", frame_us=40000), 100)


def _trace(directory, mutate=None):
    # 此处仅是门禁的合成反例fixture，不是Godot实机证据。
    vectors = json.loads((Path(__file__).resolve().parents[2] / "scripts/verification/fixtures/population-mirror-vectors.json").read_text(encoding="utf-8"))
    messages, observations = [], []
    refs = {f"character:resident_{index:03}" for index in range(100)}
    update = 0

    def add(actor, epoch, sequence, tick, *, applied=True, screenshot=None):
        nonlocal update
        projection = deepcopy(vectors["base"])
        projection["actor_ref"] = actor
        projection["facade_revision"] = f"facade:{actor}:{tick}"
        public = projection["groups"]["population_public"]["payload"]
        public.update(actor_id=actor.removeprefix("character:"), confirmed_tick=tick)
        body = {key: projection[key] for key in json.loads(projection["canonical_snapshot_json"])}
        projection["canonical_snapshot_json"] = json.dumps(body, sort_keys=True, separators=(",", ":"))
        projection["snapshot_checksum"] = digest(projection["canonical_snapshot_json"].encode())
        payload = dict(delivery_kind="snapshot", connection_epoch=epoch, delivery_sequence=sequence,
                       actor_ref=actor, facade_revision=projection["facade_revision"],
                       projection_schema=projection["projection_kind"], source_revision_vector={}, payload=projection)
        raw = json.dumps(dict(message_type="gameplay_mirror_delivery", payload=payload))
        messages.append(dict(elapsed_us=(len(messages) + 1) * 1000, packet_bytes=len(raw.encode()), raw_text=raw))
        if applied:
            update += 1
            observation = dict(wire=dict(connection_epoch=epoch, delivery_sequence=sequence, actor_ref=actor),
                               actor_ref=actor, facade_revision=projection["facade_revision"], confirmed_tick=tick,
                               marker_update=update, stage="sampling", elapsed_us=messages[-1]["elapsed_us"] + 10)
            observations.append(observation)
            if screenshot:
                observations.append({**observation, "screenshot": screenshot})

    for index, actor in enumerate(sorted(refs), 1):
        add(actor, 1, index, 1, screenshot="before.png" if index == 100 else None)
    add(sorted(refs)[0], 1, 102, 2, applied=False)
    for index, actor in enumerate(sorted(refs), 103):
        add(actor, 1, index, 2, screenshot="after.png" if index == 202 else None)
    for index, actor in enumerate(sorted(refs), 1):
        add(actor, 2, index, 3)
    if mutate:
        mutate(messages, observations)
    for name, rows in (("messages", messages), ("observations", observations)):
        (directory / f"{name}.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return refs


def test_wire_gate_recomputes_actual_bytes_and_requires_real_recovery_trace(tmp_path):
    refs = _trace(tmp_path)
    result = validate_messages(tmp_path, refs)
    assert result["matched_marker_updates"] == 300
    assert result["gap_count"] == 1 and result["connection_epochs"] == [1, 2]
    assert result["application_packet_bytes"]["snapshot"] > 0


@pytest.mark.parametrize("mutation, error", [
    (lambda messages, _: messages[0].update(packet_bytes=1), "packet_bytes_mismatch"),
    (lambda _, observations: observations[0].update(confirmed_tick=9), "marker_anchor_mismatch"),
    (lambda messages, _: messages.pop(), "unmatched_marker_observation"),
    (lambda _, observations: observations[100].update(marker_update=9999), "screenshot_anchor_mismatch"),
    (lambda messages, _: messages[0].update(raw_text=messages[0]["raw_text"].replace("sha256:", "broken:")), "wire_checksum_invalid"),
])
def test_self_reported_success_cannot_replace_raw_protocol_evidence(tmp_path, mutation, error):
    refs = _trace(tmp_path, mutate=mutation)
    with pytest.raises(ValueError, match=error):
        validate_messages(tmp_path, refs)


def _append_delta(messages, observations, *, corrupted=None):
    base_delivery = json.loads(messages[-100]["raw_text"])["payload"]
    base = base_delivery["payload"]
    target = json.loads(base["canonical_snapshot_json"])
    target["facade_revision"] += ":next"
    target["groups"]["population_public"]["payload"]["confirmed_tick"] = 4
    canonical = json.dumps(target, sort_keys=True, separators=(",", ":"))
    projection = {**deepcopy(base), "facade_revision": target["facade_revision"],
                  "groups": target["groups"], "canonical_snapshot_json": canonical,
                  "base_facade_revision": base["facade_revision"], "base_snapshot_checksum": base["snapshot_checksum"],
                  "target_snapshot_checksum": digest(canonical.encode()), "removed_group_ids": []}
    projection.pop("snapshot_checksum")
    delivery = {**deepcopy(base_delivery), "delivery_kind": "delta", "delivery_sequence": 101,
                "facade_revision": target["facade_revision"], "payload": projection,
                **{name: projection[name] for name in ("base_facade_revision", "base_snapshot_checksum", "target_snapshot_checksum")}}
    if corrupted:
        delivery[corrupted] = "corrupted-outer-anchor"
    raw = json.dumps(dict(message_type="gameplay_mirror_delivery", payload=delivery))
    elapsed = messages[-1]["elapsed_us"] + 1000
    messages.append(dict(elapsed_us=elapsed, packet_bytes=len(raw.encode()), raw_text=raw))
    observations.append(dict(wire=dict(connection_epoch=2, delivery_sequence=101, actor_ref=delivery["actor_ref"]),
                             actor_ref=delivery["actor_ref"], facade_revision=target["facade_revision"],
                             confirmed_tick=4, marker_update=301, elapsed_us=elapsed + 10, stage="sampling"))


def test_applied_delta_with_matching_inner_outer_anchors_is_accepted(tmp_path):
    refs = _trace(tmp_path, mutate=_append_delta)
    assert validate_messages(tmp_path, refs)["matched_marker_updates"] == 301


@pytest.mark.parametrize("field", ["base_facade_revision", "base_snapshot_checksum", "target_snapshot_checksum"])
def test_applied_delta_rejects_only_corrupted_outer_anchor(tmp_path, field):
    refs = _trace(tmp_path, mutate=lambda messages, observations: _append_delta(messages, observations, corrupted=field))
    with pytest.raises(ValueError, match="wire_anchor_mismatch"):
        validate_messages(tmp_path, refs)


def test_duplicate_raw_packet_without_extra_marker_is_counted_but_not_applied_twice(tmp_path):
    baseline = tmp_path / "base"
    baseline.mkdir()
    expected = validate_messages(baseline, _trace(baseline))
    duplicate_bytes = []
    def duplicate(messages, observations):
        duplicate_bytes.append(messages[0]["packet_bytes"])
        messages.insert(1, deepcopy(messages[0]))
    refs = _trace(tmp_path, mutate=duplicate)
    actual = validate_messages(tmp_path, refs)
    assert actual["matched_marker_updates"] == expected["matched_marker_updates"] == 300
    assert actual["gap_count"] == expected["gap_count"] == 1
    assert actual["application_packet_bytes"]["snapshot"] == expected["application_packet_bytes"]["snapshot"] + duplicate_bytes[0]


def test_reconnected_marker_cannot_be_reordered_before_initial_packet(tmp_path):
    def reorder(messages, observations):
        observations[0], observations[-1] = observations[-1], observations[0]
        anchors = {}
        update = 0
        for index, row in enumerate(observations):
            row["elapsed_us"] = 400000 + index
            if "screenshot" not in row:
                update += 1
                row["marker_update"] = update
                anchors[tuple(row["wire"].values())] = update
        for row in observations:
            if "screenshot" in row:
                row["marker_update"] = anchors[tuple(row["wire"].values())]
    refs = _trace(tmp_path, mutate=reorder)
    with pytest.raises(ValueError, match="marker_wire_order_invalid"):
        validate_messages(tmp_path, refs)


@pytest.mark.parametrize('target', ['messages', 'observations'])
@pytest.mark.parametrize('elapsed', [-1, True, 1.5, '1000', None, float('inf')])
def test_trace_elapsed_requires_finite_nonnegative_integer(tmp_path, target, elapsed):
    def mutate(messages, observations):
        (messages if target == 'messages' else observations)[0]['elapsed_us'] = elapsed
    refs = _trace(tmp_path, mutate=mutate)
    with pytest.raises(ValueError, match='trace_time_invalid|nonfinite_json'):
        validate_messages(tmp_path, refs)


@pytest.mark.parametrize('target', ['messages', 'observations'])
def test_trace_elapsed_cannot_move_backwards(tmp_path, target):
    def mutate(messages, observations):
        rows = messages if target == 'messages' else observations
        rows[1]['elapsed_us'] = rows[0]['elapsed_us'] - 1
    refs = _trace(tmp_path, mutate=mutate)
    with pytest.raises(ValueError, match='trace_time_invalid'):
        validate_messages(tmp_path, refs)


def test_marker_cannot_precede_its_received_packet(tmp_path):
    refs = _trace(tmp_path, mutate=lambda messages, observations: messages[0].update(elapsed_us=observations[0]['elapsed_us'] + 1))
    with pytest.raises(ValueError, match='marker_precedes_packet'):
        validate_messages(tmp_path, refs)


def test_duplicate_wire_key_cannot_claim_second_marker_application(tmp_path):
    def mutate(messages, observations):
        messages.insert(1, deepcopy(messages[0]))
        observations.insert(1, deepcopy(observations[0]))
    refs = _trace(tmp_path, mutate=mutate)
    with pytest.raises(ValueError, match='marker_observation_invalid'):
        validate_messages(tmp_path, refs)


def test_observation_delay_and_equal_timestamps_are_allowed(tmp_path):
    def mutate(messages, observations):
        for observation in observations:
            observation['elapsed_us'] += 1_000_000
    refs = _trace(tmp_path, mutate=mutate)
    assert validate_messages(tmp_path, refs)['matched_marker_updates'] == 300


def test_resync_control_counts_bytes_without_consuming_sequence_then_full_recovers(tmp_path):
    control = {}
    def mutate(messages, observations):
        actor = json.loads(messages[0]['raw_text'])['payload']['actor_ref']
        raw = json.dumps({'message_type':'gameplay_mirror_resync_required',
                          'payload':{'actor_ref':actor, 'reason_code':'mirror_backpressure'}})
        control['bytes'] = len(raw.encode())
        messages.insert(100, dict(elapsed_us=100500, packet_bytes=control['bytes'], raw_text=raw))
        _append_delta(messages, observations)
    refs = _trace(tmp_path, mutate=mutate)
    result = validate_messages(tmp_path, refs)
    assert result['application_packet_bytes']['gameplay_mirror_resync_required'] == control['bytes']
    assert result['matched_marker_updates'] == 301 and result['gap_count'] == 1


@pytest.mark.parametrize('payload', [[], {'actor_ref':'character:unknown', 'reason_code':'mirror_backpressure'},
                                     {'actor_ref':'character:resident_000', 'reason_code':'unknown'}])
def test_resync_control_rejects_unknown_or_malformed_payload(tmp_path, payload):
    def mutate(messages, observations):
        raw = json.dumps({'message_type':'gameplay_mirror_resync_required', 'payload':payload})
        messages.insert(100, dict(elapsed_us=100500, packet_bytes=len(raw.encode()), raw_text=raw))
    refs = _trace(tmp_path, mutate=mutate)
    with pytest.raises(ValueError, match='resync_control_invalid'):
        validate_messages(tmp_path, refs)


def test_resync_control_requires_new_full_base_before_applied_delta(tmp_path):
    def mutate(messages, observations):
        _append_delta(messages, observations)
        raw = json.dumps({'message_type':'gameplay_mirror_resync_required',
                          'payload':{'actor_ref':'character:resident_000', 'reason_code':'mirror_backpressure'}})
        messages.insert(-1, dict(elapsed_us=messages[-2]['elapsed_us'] + 500, packet_bytes=len(raw.encode()), raw_text=raw))
    refs = _trace(tmp_path, mutate=mutate)
    with pytest.raises(ValueError, match='applied_delta_base_invalid'):
        validate_messages(tmp_path, refs)


def test_resync_control_does_not_clear_another_actors_delta_base(tmp_path):
    def mutate(messages, observations):
        _append_delta(messages, observations)
        raw = json.dumps({'message_type':'gameplay_mirror_resync_required',
                          'payload':{'actor_ref':'character:resident_001', 'reason_code':'mirror_backpressure'}})
        messages.insert(-1, dict(elapsed_us=messages[-2]['elapsed_us'] + 500, packet_bytes=len(raw.encode()), raw_text=raw))
    refs = _trace(tmp_path, mutate=mutate)
    result = validate_messages(tmp_path, refs)
    assert result['applied_delta_count'] == 1 and result['gap_count'] == 1


@pytest.mark.parametrize("fault", [None, "missing", "unrestored", "pid", "extra", "collector_wrong", "collector_missing", "collector_bool", "collector_zero", "collector_string"])
def test_qos_artifact_contract(tmp_path, monkeypatch, fault):
    # 仅控制证据接线；截图/帧专用校验替身不代表实际 Godot 验收。
    from scripts.verification import population_godot_runner as runner
    from scripts.verification import verify_population_godot_runtime as gate
    source = {"source_sha256": "controlled"}
    monkeypatch.setattr(runner, "source_manifest", lambda: source)
    monkeypatch.setattr(gate, "validate_backend_process", lambda *args: None)
    monkeypatch.setattr(gate, "validate_capture", lambda *args: {})
    names = "roster.json backend.log godot.log commands.json backend-ready.json stage.json authority-before.json authority-after.json frame-times.csv messages.jsonl observations.jsonl before.png after.png godot-capture.json lod-before.json lod-after.json result.json processes.json owner-ready.json owner-observed.json backend-observed.json parent-qos.json owner-qos.json".split()
    def write(path, value):
        path.write_text(json.dumps(value), encoding="utf-8")
    def qos(pid):
        return dict(pid=pid, supported=True, before=[1,0,0], applied=[1,1,0], restored=[1,0,0])
    write(tmp_path / "collector-qos.json", qos(10))
    for name in ("dependencies.txt", "godot-import.log"):
        (tmp_path / name).write_text("", encoding="utf-8")
    for n in (100, 1000):
        case = tmp_path / str(n)
        case.mkdir()
        for name in names: write(case / name, {})
        write(case / "parent-qos.json", qos(20))
        write(case / "owner-qos.json", qos(30))
        write(case / "owner-ready.json", {"owner_pid": 30})
        write(case / "processes.json", dict(backend_pid=20, backend_exit_code=0, godot_exit_code=0, clean_backend_shutdown=True))
        write(case / "backend-ready.json", dict(clock_profile="benchmark_1x", population=n, model_mode="local_fixture", compression="disabled"))
        write(case / "commands.json", {"godot": ["--scene", "res://scenes/phase0/PopulationProbe.tscn", "--rendering-method", "forward_plus", "--rendering-driver", "vulkan", "--resolution", "1280x720"]})
    if fault == "missing": (tmp_path / "100/owner-qos.json").unlink()
    if fault == "unrestored": write(tmp_path / "collector-qos.json", {**qos(10), "restored": None})
    if fault == "pid": write(tmp_path / "100/owner-qos.json", qos(99))
    if fault == "extra": write(tmp_path / "extra.json", {})
    manifest = dict(schema_version=1, status="passed", source=source, collector_pid=10,
        environment=dict(python="3.12.14", godot_version="4.6.3.stable"), cases={str(n): {} for n in (100,1000)},
        artifacts={p.relative_to(tmp_path).as_posix(): digest(p.read_bytes()) for p in tmp_path.rglob("*") if p.is_file()})
    if fault == "collector_missing": manifest.pop("collector_pid")
    if fault in {"collector_wrong", "collector_bool", "collector_zero", "collector_string"}:
        manifest["collector_pid"] = {"collector_wrong":11, "collector_bool":True, "collector_zero":0, "collector_string":"10"}[fault]
    write(tmp_path / "manifest.json", manifest)
    if fault:
        with pytest.raises(ValueError, match={"missing":"artifact_missing", "unrestored":"process_qos_lifecycle_invalid", "pid":"process_qos_pid_mismatch", "extra":"unexpected_artifact", **{key:"process_qos_pid_mismatch" for key in ("collector_wrong", "collector_missing", "collector_bool", "collector_zero", "collector_string")}}[fault]):
            gate.verify_artifacts(tmp_path)
    else:
        assert gate.verify_artifacts(tmp_path)["status"] == "passed"
