"""混合负载原始记录离线复算；不启动服务、模型或 Godot。"""
from math import isclose, isfinite
import json
import re
from statistics import median

from scripts.verification.population_benchmark_metrics import percentile
from scripts.verification.population_mixed_load import MixedLoadSchedule


CLIENT_KINDS = {"health", "ws_read", "fact", "interaction", "character_model", "siming_model", "owner_contention",
    "slow_consumer", "resume_consumer", "disconnect", "reconnect"}
SERVER_KINDS = {"siming_model", "provider_timeout", "sqlite_busy", "sqlite_release"}


def number(value, *, integer=False, minimum=0):
    if (type(value) not in ((int,) if integer else (int, float))
            or not isfinite(value) or value < minimum):
        raise ValueError("mixed_raw_number_invalid")
    return value


def equal_number(actual, expected):
    if not isclose(number(actual), expected, rel_tol=0, abs_tol=1e-5):
        raise ValueError("mixed_raw_derived_value_mismatch")


def cache_bounds(caches):
    limits = dict(session_events=0, light_memory_events=0, heavy_normalizer_events=0,
        population_receipts=2, population_fingerprints=2, cadence=1, projection=1, preview=1, publisher_records=2,
        activation_receipts=32)
    nested = dict(graph={"_nodes", "_relations", "_idempotency", "_checkpoints", "_branch_markers"},
        gameplay={"_events", "_transactions", "_outbox"},
        activation_history={"state", "source_revision_vector", "applied_event_ids"})
    if (set(caches) != limits.keys() | nested.keys() | {"authority_bus", "authority_bus_types"}
            or any(set(caches[key]) != fields for key, fields in nested.items())
            or not isinstance(caches["authority_bus_types"], dict)
            or any(not isinstance(kind, str) or not kind for kind in caches["authority_bus_types"])):
        raise ValueError("mixed_cache_shape_invalid")
    values = [(number(caches[key], integer=True), limit) for key, limit in limits.items()]
    values.extend((number(value, integer=True), 0) for key in nested for value in caches[key].values())
    history = {kind: number(value, integer=True) for kind, value in caches["authority_bus_types"].items()}
    authority_bus = number(caches["authority_bus"], integer=True)
    if authority_bus != sum(history.values()):
        raise ValueError("mixed_cache_value_invalid")
    return (all(value <= limit for value, limit in values)
        and history.get("population_cadence_event", 0) <= 2
        and all(value <= 32 for value in history.values()))


def replay_requests(report, config, *, side):
    """重新生成固定到达率与身份。handler_finished 只算完成处理，不据此认定提交。"""
    kinds = {"client": CLIENT_KINDS, "server": SERVER_KINDS}[side]
    origin = number(report["origin"], minimum=1e-9)
    schedule = MixedLoadSchedule(config["population"], config["seed"], config["mode"])
    events = [event for event in schedule.events(config["seconds"]) if event.kind in kinds]
    equal_number(report["load_end"], origin + config["seconds"])
    finished = number(report["finished_at"], minimum=report["load_end"])
    rows = report["requests"]
    if len(rows) != len(events) or number(report["offered"], integer=True) != len(events):
        raise ValueError("mixed_request_coverage_invalid")
    dispatched = failed = 0
    active_changes, by_kind = [], {}
    for row, event in zip(rows, events):
        if ((row["key"], row["kind"], row["ordinal"]) != (event.transaction_id, event.kind, event.ordinal)
                or type(row["ordinal"]) is not int):
            raise ValueError("mixed_request_identity_invalid")
        expected = origin + event.at_ms / 1000
        equal_number(row["expected_at"], expected)
        offered = number(row["offered_at"], minimum=expected-1e-7)
        if offered > finished:
            raise ValueError("mixed_request_after_run_finished")
        status = row["status"]
        if status not in {"handler_finished", "handler_failed", "cancelled", "capacity_exhausted", "drain_timeout"}:
            raise ValueError("mixed_request_terminal_missing")
        if status == "capacity_exhausted":
            if "issued_at" in row:
                raise ValueError("mixed_request_capacity_claim_invalid")
        else:
            issued = number(row["issued_at"], minimum=offered)
            completed = number(row["finished_at"], minimum=issued)
            if completed > finished or (status == "handler_finished" and not isinstance(row.get("result"), dict)):
                raise ValueError("mixed_request_result_invalid")
            dispatched += 1
            active_changes.extend(((issued, 1), (completed, -1)))
        failed += status != "handler_finished"
        by_kind[row["kind"]] = by_kind.get(row["kind"], 0) + 1
    active = observed_peak = 0
    for _, delta in sorted(active_changes):
        active += delta
        observed_peak = max(observed_peak, active)
    peak = number(report["peak_in_flight"], integer=True)
    if (not observed_peak <= peak <= 128 or number(report["failed"], integer=True) != failed
            or number(report["dispatched"], integer=True) != dispatched):
        raise ValueError("mixed_request_summary_mismatch")
    return dict(complete_traffic=failed == 0, offered=len(rows), dispatched=dispatched, failed=failed,
        by_kind=by_kind, peak_in_flight=peak)


def replay_providers(rows, requests, server):
    """证明原接口调用，不把本地fallback、多个认知stage或ACK统计成三个真实任务。"""
    calls = [row for row in rows if row["type"] == "provider_result"]
    ordinals = [number(row["ordinal"], integer=True, minimum=1) for row in calls]
    if sorted(ordinals) != list(range(1, len(calls)+1)):
        raise ValueError("mixed_provider_call_coverage_invalid")
    active_changes, qualified, threads = [], [], set()
    for row in calls:
        start = number(row["started_at"], minimum=1e-9)
        finish = number(row["finished_at"], minimum=start)
        threads.add((number(row["process_id"], integer=True, minimum=1), number(row["thread_id"], integer=True, minimum=1)))
        if row["family"] not in {"character", "siming"} or not isinstance(row["source_event_ids"], list):
            raise ValueError("mixed_provider_identity_invalid")
        for name in ("validated", "transport_attempted", "transport_succeeded", "fallback_used", "qualified_success"):
            if type(row[name]) is not bool:
                raise ValueError("mixed_provider_boolean_invalid")
        if re.fullmatch(r"[0-9a-f]{64}", row["request_sha256"]) is None:
            raise ValueError("mixed_provider_request_digest_invalid")
        success = row["validated"] and row["transport_attempted"] and row["transport_succeeded"] and not row["fallback_used"] and row["fault_key"] is None and row["error"] is None
        if row["qualified_success"] != success or (success and (re.fullmatch(r"[0-9a-f]{64}", row.get("output_sha256", "")) is None
                or any(not isinstance(row.get(key), str) or not row[key] for key in ("provider_kind", "model", "endpoint_host")))):
            raise ValueError("mixed_provider_success_claim_invalid")
        active_changes.extend(((start, 1), (finish, -1)))
        if success:
            qualified.append(row)
    active = peak = 0
    for _, delta in sorted(active_changes):
        active += delta
        peak = max(peak, active)
    if (peak != number(server["provider_peak_active"], integer=True)
            or number(server["provider_active"], integer=True) != 0):
        raise ValueError("mixed_provider_concurrency_mismatch")
    by_family, first_three = {}, True
    for family in ("character", "siming"):
        tasks = [row for row in requests if row["kind"] == family+"_model"]
        used, good = set(), []
        for task in tasks:
            matches = []
            if task["status"] == "handler_finished":
                result = task["result"]
                matches = [row for row in qualified if row["family"] == family and row["ordinal"] not in used
                    and (row["stage"] == "dialogue_generation" and result.get("status") == "completed"
                        and task["issued_at"] <= row["started_at"] <= row["finished_at"] <= result["response_at"]
                        if family == "character" else result.get("source_event_id") in row["source_event_ids"])]
            if matches:
                used.add(matches[0]["ordinal"])
            good.append(bool(matches))
        by_family[family] = sum(good)
        first_three = len(good) >= 3 and all(good[:3]) and first_three
    return dict(calls=len(calls), qualified_calls=len(qualified), live_tasks=by_family,
        first_three_live_tasks_passed=first_three, peak_active=peak,
        isolated=peak <= 4 and all(pid == server["owner_pid"] for pid, _ in threads)
            and not threads.intersection(map(tuple, server["owner_threads"])),
        pending_timeout=server["pending_timeout"])


def replay_responses(records, requests):
    """逐包复用生产投影校验，消费后丢弃大包；ACK和领域结果分别计时。"""
    from scripts.verification.verify_population_transport_cost import WireEvidence
    from scripts.verification.population_mixed_transport import contention_winner

    by_key, wires, snapshots = {}, {}, {}
    for row in records:
        key, category = row["key"], row["type"]
        number(row["at"])
        if category.startswith("fault_"):
            continue  # 故障连接由独立的 MixedMirrorReceiver 回放，不混入普通 read。
        if category == "mirror_packet":
            message = json.loads(row["raw_text"])
            for name in ("connection_epoch", "delivery_sequence"):
                number(message["payload"][name], integer=True, minimum=1)
            if key not in wires:
                wires[key] = WireEvidence({"character:char_a"}, strict_public_windows=False)
            wire = wires[key]
            wire.receive(row["raw_text"])
            continue
        if category == "snapshot":
            wire = wires.pop(key, None)
            if wire is None or "character:char_a" not in wire.snapshots:
                raise ValueError("mixed_snapshot_original_packets_missing")
            snapshot = wire.snapshots["character:char_a"]
            packet = row["message"]
            kind = packet["payload"]["delivery_kind"]
            if packet["message_type"] != "gameplay_mirror_delivery" or wire.latest_payloads[kind] != packet["payload"]:
                raise ValueError("mixed_snapshot_terminal_packet_changed")
            if key in snapshots:
                raise ValueError("mixed_snapshot_terminal_duplicate")
            snapshots[key] = dict(response_at=row["at"], actor_ref="character:char_a", checksum=snapshot.snapshot_checksum,
                confirmed_tick=snapshot.groups["population_public"].payload["confirmed_tick"])
            continue
        if category not in {"sent", "accepted", "response", "health_response", "contention"}:
            raise ValueError("mixed_transport_record_type_invalid")
        group = by_key.setdefault(key, {})
        if category in group:
            raise ValueError("mixed_transport_response_duplicate")
        group[category] = row

    def one(key, category):
        try:
            return by_key[key][category]
        except KeyError as error:
            raise ValueError("mixed_transport_original_response_missing") from error

    def accepted(key, source):
        value = one(key, "accepted")
        if value.get("accepted") is not True or value["source_type"] != source:
            raise ValueError("mixed_transport_ack_invalid")
        return value["at"]

    def exchange(key, source):
        sent, response = one(key, "sent"), one(key, "response")
        accept = accepted(key, source)
        if sent["source_type"] != source or sent["at"] > min(accept, response["at"]):
            raise ValueError("mixed_transport_exchange_order_invalid")
        result = {name:value for name, value in response.items() if name not in {"key", "type", "at"}}
        return dict(accepted_at=accept, response_at=response["at"], **result), number(sent["producer_ts"], integer=True)

    def interaction(key, actor, target):
        result, timestamp = exchange(key, "player_input")
        if (result.get("message_type") != "world_result" or result.get("event_type") not in {"action_resolution_result", "constraint_state_result"}
                or result.get("actor_id") != actor or result.get("target_object_id") != target
                or result.get("request_ref") != f"interact:{timestamp}:{target}"):
            raise ValueError("mixed_interaction_correlation_invalid")
        return result

    def snapshot(key):
        if key not in snapshots:
            raise ValueError("mixed_snapshot_response_missing")
        return dict(accepted_at=accepted(key, "gameplay_mirror_snapshot_request"), **snapshots[key])

    values, counts = dict(health=[], accepted=[], fact=[]), dict(fact_responses=0, mirror_responses=0, contentions=0)
    for task in requests:
        if task["status"] != "handler_finished":
            continue
        key, kind = task["key"], task["kind"]
        if kind in {"slow_consumer", "resume_consumer", "disconnect", "reconnect"}:
            continue
        if kind == "health":
            row = one(key, "health_response")
            result = dict(response_at=row["at"], status=row["status"])
            if result["status"] != "ok":
                raise ValueError("mixed_health_response_failed")
        elif kind == "ws_read":
            result = snapshot(key)
            counts["mirror_responses"] += 1
        elif kind == "owner_contention":
            for actor in ("char_a", "char_c"):
                moved, _ = exchange(key+":move:"+actor, "player_input")
                if moved.get("route") != "local_motion" or moved.get("request_id") != key+":move:"+actor:
                    raise ValueError("mixed_contention_move_invalid")
            contenders = [interaction(key+":use:"+actor, actor, "obj_worktable") for actor in ("char_a", "char_c")]
            winner = contention_winner(contenders)
            release = interaction(key+":release:"+winner, winner, "obj_worktable")
            if release.get("resolution_status") != "accepted" or release.get("settlement_status") != "accepted":
                raise ValueError("mixed_contention_release_invalid")
            result = dict(winner=winner, contenders=contenders, release=release)
            observed = one(key, "contention")
            if result != {name:value for name, value in observed.items() if name not in {"key", "type", "at"}}:
                raise ValueError("mixed_contention_summary_changed")
            counts["contentions"] += 1
        elif kind == "interaction":
            result = interaction(key, "char_c", "obj_letter")
        elif kind == "fact":
            result, timestamp = exchange(key, "raw_fact_event")
            if (result.get("message_type") != "spatial_access_runtime_state_snapshot" or result.get("updated_at") != timestamp
                    or result.get("actor_id") != "char_b" or result.get("current_zone_id") != "zone_focus"):
                raise ValueError("mixed_fact_correlation_invalid")
            counts["fact_responses"] += 1
        elif kind == "character_model":
            result, _ = exchange(key, "player_input")
            if (result.get("message_type") != "dialogue_stream_end" or result.get("request_id") != key
                    or result.get("status") not in {"completed", "requeued", "cancelled"}):
                raise ValueError("mixed_character_terminal_invalid")
        elif kind == "siming_model":
            result, timestamp = exchange(key, "visual_fact_event")
            if result.get("message_type") != "ack" or result.get("route") != "authority_visual_fact":
                raise ValueError("mixed_siming_input_ack_invalid")
            result.update(producer_ts=timestamp, correlation_id=key,
                source_event_id=f"visual_fact:{timestamp}:char_c:light_level_drop", input_accepted_only=True)
        else:
            raise ValueError("mixed_transport_request_kind_invalid")
        if result != task["result"]:
            raise ValueError("mixed_transport_raw_result_mismatch")
        for field in ("accepted_at", "response_at"):
            if field in result and not task["issued_at"] <= result[field] <= task["finished_at"]:
                raise ValueError("mixed_transport_time_outside_request")
        if kind == "health":
            values["health"].append((result["response_at"]-task["expected_at"])*1000)
        if kind == "fact":
            values["fact"].append((result["response_at"]-task["expected_at"])*1000)
        if "accepted_at" in result:
            values["accepted"].append((result["accepted_at"]-task["expected_at"])*1000)
    return dict(**counts, metrics={name+"_p95_ms":percentile(samples) if samples else None for name, samples in values.items()},
        healthy_snapshots={key:snapshot(key) for key in snapshots if key.endswith(":healthy")})


def replay_ws_faults(records, requests, actors, healthy_snapshots):
    """故障原包复用相同接收状态机；同 tick 的暂停前缓存不能证明恢复。"""
    from scripts.verification.population_mixed_mirror import MixedMirrorReceiver

    scopes = {"character:"+actor for actor in actors[:100]}
    sessions, pauses, resumes, disconnects = {}, {}, {}, {}
    current, last_epoch, resync = None, 0, []
    for row in records:
        category, key = row["type"], row["key"]
        if not category.startswith("fault_"):
            continue
        at = number(row["at"])
        if category == "fault_bound":
            epoch = number(row["epoch"], integer=True, minimum=1)
            if epoch <= last_epoch or row["actor_refs"] != sorted(scopes) or row["max_queue"] != 1:
                raise ValueError("mixed_fault_binding_invalid")
            current = dict(receiver=MixedMirrorReceiver(scopes, epoch=epoch), bound_at=at, last_applied_at=None, closed_at=None)
            sessions[epoch], last_epoch = current, epoch
        elif current is None:
            raise ValueError("mixed_fault_packet_without_binding")
        elif category == "fault_mirror_packet":
            if current['closed_at'] is not None:
                raise ValueError('mixed_fault_epoch_closed')
            if row["epoch"] != last_epoch:
                raise ValueError("mixed_fault_packet_epoch_changed")
            decision = current["receiver"].receive(row["raw_text"])
            if decision != row["decision"]:
                raise ValueError("mixed_fault_receiver_decision_changed")
            if decision["applied"]:
                current["last_applied_at"] = at
            resync.extend((key, actor) for actor in decision["request_actor_refs"])
        elif category == "fault_resync_request":
            if not resync or (key, row["actor_ref"]) != resync.pop(0):
                raise ValueError("mixed_fault_resync_not_requested")
        elif category == "fault_controlled_close":
            if current['closed_at'] is not None:
                raise ValueError('mixed_fault_epoch_already_closed')
            if (row["epoch"] != last_epoch or row["reason_code"] != "mirror_delivery_unrecoverable"
                    or row["route"] != "gameplay_mirror_transport"):
                raise ValueError("mixed_fault_close_invalid")
            current['closed_at'] = at
        elif category in {"fault_pause", "fault_resume", "fault_disconnect"}:
            mapping = {"fault_pause":pauses, "fault_resume":resumes, "fault_disconnect":disconnects}[category]
            if key in mapping:
                raise ValueError("mixed_fault_control_duplicate")
            mapping[key] = dict(at=at, epoch=last_epoch)
        else:
            raise ValueError("mixed_fault_record_type_invalid")
    if resync:
        raise ValueError("mixed_fault_resync_not_sent")
    pause_seconds, disconnect_seconds, recoveries = [], [], []
    slow = disconnected = None
    for task in requests:
        kind, key = task["kind"], task["key"]
        if kind not in {"slow_consumer", "resume_consumer", "disconnect", "reconnect"} or task["status"] != "handler_finished":
            continue
        result = task["result"]
        if kind == "slow_consumer":
            slow = key
            if pauses.get(key) != dict(at=result["pause_started_at"], epoch=result["epoch"]):
                raise ValueError("mixed_pause_original_control_missing")
            continue
        if kind == "disconnect":
            disconnected = key
            if disconnects.get(key) != dict(at=result["disconnected_at"], epoch=result["epoch"]):
                raise ValueError("mixed_disconnect_original_control_missing")
            continue
        recovery_at = number(result["recovered_at"], minimum=task["issued_at"])
        if recovery_at > task["finished_at"]:
            raise ValueError("mixed_fault_recovery_outside_request")
        epoch = number(result["epoch"], integer=True, minimum=1)
        session = sessions[epoch]
        if session['closed_at'] is not None and recovery_at >= session['closed_at']:
            raise ValueError('mixed_fault_recovery_epoch_closed')
        receiver, fresh = session["receiver"], session["last_applied_at"]
        health = healthy_snapshots.get(key+":healthy")
        if (health is None or health["confirmed_tick"] != result["healthy_cutoff"]
                or health["response_at"] > recovery_at):
            raise ValueError("mixed_fault_healthy_cutoff_invalid")
        actual_ticks = {actor:snapshot.groups["population_public"].payload["confirmed_tick"]
            for actor, snapshot in receiver.wire.snapshots.items()}
        if (receiver.awaiting or set(actual_ticks) != scopes or actual_ticks != result["confirmed_ticks"]
                or any(tick < result["healthy_cutoff"] for tick in actual_ticks.values())
                or number(result["sequence"], integer=True, minimum=1) != receiver.wire.sequence):
            raise ValueError("mixed_fault_recovery_projection_invalid")
        if kind == "resume_consumer":
            pause, resume = pauses[slow], resumes[slow]
            duration = resume["at"]-pause["at"]
            if (duration < 5 or result["pause_started_at"] != pause["at"] or result["resumed_at"] != resume["at"]
                    or result["previous_epoch"] != pause["epoch"] or epoch < pause["epoch"]):
                raise ValueError("mixed_fault_pause_duration_invalid")
            start = resume["at"]
            pause_seconds.append(duration)
        else:
            before = disconnects[disconnected]
            duration = session["bound_at"]-before["at"]
            if (duration < 2 or result["disconnected_at"] != before["at"]
                    or result["previous_epoch"] != before["epoch"] or epoch <= before["epoch"]):
                raise ValueError("mixed_fault_disconnect_duration_invalid")
            start = before["at"]
            disconnect_seconds.append(duration)
        if fresh is None or not start <= fresh <= recovery_at:
            raise ValueError("mixed_fault_fresh_recovery_packet_missing")
        recoveries.append(recovery_at-start)
    return dict(pause_seconds=pause_seconds, disconnect_seconds=disconnect_seconds, recovery_seconds=recoveries)


def replay_windows(rows, config, actors):
    """按真实墙钟重新计算，不相信缓存的耗时/backlog，也不把 B0 due 计数冒充 B1 完成。"""
    schedule = MixedLoadSchedule(config["population"], config["seed"], config["mode"])
    seconds = number(config["seconds"], integer=True, minimum=1)
    if len(actors) != config["population"] or len(set(actors)) != len(actors):
        raise ValueError("mixed_roster_invalid")
    period, total = schedule.window_ms / 1000, seconds * 1000 // schedule.window_ms
    origins = [row for row in rows if row["type"] == "driver_clock_origin"]
    if len(origins) != 1:
        raise ValueError("mixed_driver_origin_missing_or_duplicate")
    origin = number(origins[0]["at"], minimum=1e-9)
    driver_origin = number(origins[0]["monotonic"], minimum=1e-9)
    last_driver_finish = driver_origin
    due = {}
    for event in schedule.events(seconds):
        if event.kind in {"regular_due", "due_peak"}:
            due.setdefault(event.window_index, []).append(event)
    windows = [row for row in rows if row["type"] == "window"]
    cursor, last_finish, last_cpu, cache_passed = 0, origin, 0., True
    published, measured, drain = set(), [], []
    for row in windows:
        tick = number(row["target_tick"], integer=True, minimum=1)
        if number(row["previous_tick"], integer=True) != cursor or tick != cursor + 1:
            raise ValueError("mixed_window_coverage_invalid")
        start, cadence, finish = (number(row[key]) for key in ("started_at", "cadence_started_at", "finished_at"))
        sample, result = row["sample"], row["result"]
        if not last_finish <= start <= cadence <= finish <= number(sample["at"]):
            raise ValueError("mixed_window_time_order_invalid")
        equal_number(row["expected_at"], origin + tick * period)
        # 原driver同一monotonic核到期；perf_counter只量工作耗时，不混用Windows时钟。
        driver_start, driver_finish = (number(row[key]) for key in ('driver_started_at', 'driver_finished_at'))
        if not max(last_driver_finish, driver_origin + tick * period) <= driver_start <= driver_finish:
            raise ValueError('mixed_window_driver_deadline_invalid')
        last_driver_finish = driver_finish
        equal_number(row["fixture_ms"], (cadence-start)*1000)
        equal_number(row["cadence_ms"], (finish-cadence)*1000)
        confirmed = number(sample["confirmed_tick"], integer=True)
        if confirmed not in {cursor, tick}:
            raise ValueError("mixed_window_confirmation_invalid")
        lag = max(0., (driver_finish-driver_origin)/period-confirmed)
        backlog = max(0, int((driver_finish-driver_origin)/period)-confirmed)
        if number(row["backlog"], integer=True) != backlog:
            raise ValueError("mixed_raw_backlog_mismatch")
        equal_number(row["advance_lag_windows"], lag)
        ids = result["published_cadence_ids"]
        if (not isinstance(ids, list) or len(ids) != int(confirmed == tick)
                or any(not isinstance(value, str) or not value or value in published for value in ids)
                or number(result["b0_advanced_count"], integer=True) != (len(actors) if confirmed == tick else 0)):
            raise ValueError("mixed_window_publication_invalid")
        published.update(ids)
        for field in ("due_item_count", "deferred_item_count", "rejected_item_count"):
            number(result[field], integer=True)
        fixtures = row["fixtures"]
        expected_due = due.get(tick, [])
        if len(fixtures) != len(expected_due):
            raise ValueError("mixed_fixture_coverage_invalid")
        for fixture, event in zip(fixtures, expected_due):
            indices = event.actor_indices[:28] if event.kind == "regular_due" else event.actor_indices
            expected_rows = []
            for index in indices:
                key = f"{event.transaction_id}:actor-slot:{index}"
                expected_rows.append(dict(key=key, actor_id=actors[index], window_ref="window:" + key,
                    due_tick=tick, schedule_event_id="event:schedule:" + key + ":4", closed_event_id="event:close:" + key + ":1"))
            if fixture != dict(key=event.transaction_id, kind=event.kind, rows=expected_rows):
                raise ValueError("mixed_fixture_recipe_mismatch")
        number(sample["rss_bytes"], integer=True, minimum=1)
        cpu = number(sample["cpu_seconds"])
        if cpu < last_cpu or not sample["storage_bytes"]:
            raise ValueError("mixed_resource_sample_invalid")
        for size in sample["storage_bytes"].values():
            number(size, integer=True)
        execution = sample["execution"]
        if number(execution["queue_depth"], integer=True) > 128 or execution["failure"] is not None:
            raise ValueError("mixed_runtime_queue_or_failure_invalid")
        number(execution["queue_wait_ms"])
        number(execution["service_ms"])
        cache_passed = cache_bounds(sample["caches"]) and cache_passed
        (measured if tick <= total else drain).append(row)
        cursor, last_finish, last_cpu = confirmed, finish, cpu
    if cursor < total or [row["target_tick"] for row in measured if row["sample"]["confirmed_tick"] == row["target_tick"]] != list(range(1, total+1)):
        raise ValueError("mixed_window_coverage_incomplete")

    # SQLite 持锁及其实际追平段单列，保留全部原始样本。恢复超过30个1×窗口不能隐藏在排除区间。
    recovery, recovery_passed = [], True
    for fault in (row for row in rows if row["type"] == "sqlite_busy"):
        acquired, released = number(fault["acquired_at"]), number(fault["released_at"])
        if released < acquired + 2:
            raise ValueError("mixed_sqlite_hold_too_short")
        caught_up = next((row for row in windows if row["finished_at"] >= released
            and row["backlog"] == 0 and row["advance_lag_windows"] <= 1), None)
        recovery_end = caught_up["finished_at"] if caught_up else last_finish
        recovery_passed = caught_up is not None and recovery_end-released <= 30 and recovery_passed
        recovery.append(dict(start=acquired, end=recovery_end, hold_seconds=released-acquired,
            recovery_seconds=recovery_end-released))
    steady = [row for row in measured if not any(row["started_at"] <= fault["end"] and row["finished_at"] >= fault["start"] for fault in recovery)]
    if not steady:
        raise ValueError("mixed_steady_window_samples_missing")
    durations = [row["cadence_ms"] for row in steady]
    backlog = [row["backlog"] for row in steady]
    persistent = any(all(value > 0 for value in backlog[index:index+30]) for index in range(len(backlog)-29))
    max_lag = max(row["advance_lag_windows"] for row in steady)
    growth, rss_passed = None, True
    if seconds >= 7200:
        first = [row["sample"]["rss_bytes"] for row in measured if row["sample"]["at"] <= origin+1800]
        last = [row["sample"]["rss_bytes"] for row in measured if origin+seconds-1800 <= row["sample"]["at"] <= origin+seconds]
        if not first or not last:
            raise ValueError("mixed_rss_wall_coverage_missing")
        initial, final = median(first), median(last)
        growth = dict(first_median_bytes=initial, last_median_bytes=final, growth_bytes=final-initial,
            allowed_bytes=max(32*1024*1024, initial*.1))
        rss_passed = growth["growth_bytes"] <= growth["allowed_bytes"]
    budget = 800 if config["mode"] == "one_x" else 80
    p95 = percentile(durations)
    return dict(measured_windows=total, measured_attempts=len(measured), drain_windows=len(drain),
        metrics=dict(cadence_p95_ms=p95, max_lag_windows=max_lag, final_backlog=measured[-1]["backlog"],
            max_backlog=max(backlog), cpu_seconds=last_cpu, peak_rss_bytes=max(row["sample"]["rss_bytes"] for row in windows)),
        budget_ms=budget, cache_bounds_passed=cache_passed, rss_growth=growth, rss_growth_passed=rss_passed,
        sqlite_recovery=recovery, sqlite_recovery_passed=recovery_passed,
        drain_max_lag_windows=max((row["advance_lag_windows"] for row in drain), default=0),
        performance_passed=p95 <= budget and max_lag <= 1 and not persistent and measured[-1]["backlog"] <= 1)
