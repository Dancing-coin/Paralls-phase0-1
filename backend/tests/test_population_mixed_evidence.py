"""离线门禁的合成反例；这些记录不用于宣称真实性能或模型验收。"""
from copy import deepcopy

import pytest

from scripts.verification import population_mixed_evidence as evidence
from scripts.verification.population_mixed_load import MixedLoadSchedule


def trace(seconds=30, mode="one_x"):
    config = dict(population=100, seed=31, seconds=seconds, mode=mode, provider_mode="live")
    actors = ["char_a", "char_b", "char_c", *[f"resident_{i:05d}" for i in range(97)]]
    schedule = MixedLoadSchedule(100, 31, mode)
    period = schedule.window_ms / 1000
    due = {}
    for event in schedule.events(seconds):
        if event.kind in {"regular_due", "due_peak"}:
            indices = event.actor_indices[:28] if event.kind == "regular_due" else event.actor_indices
            rows = []
            for index in indices:
                key = f"{event.transaction_id}:actor-slot:{index}"
                rows.append(dict(key=key, actor_id=actors[index], window_ref="window:" + key,
                    due_tick=event.window_index, schedule_event_id="event:schedule:" + key + ":4",
                    closed_event_id="event:close:" + key + ":1"))
            due.setdefault(event.window_index, []).append(dict(key=event.transaction_id, kind=event.kind, rows=rows))
    rows = [dict(type="driver_clock_origin", at=100., monotonic=50.)]
    for tick in range(1, seconds * 1000 // schedule.window_ms + 1):
        start = 100 + tick * period
        finish = start + period * .4
        rows.append(dict(type="window", expected_at=start, started_at=start, cadence_started_at=start + period * .1,
            driver_started_at=50.+tick*period, driver_finished_at=50.+tick*period+period*.4,
            finished_at=finish, target_tick=tick, previous_tick=tick-1, fixture_ms=period*100,
            cadence_ms=period*300, backlog=0, advance_lag_windows=.4, fixtures=due[tick],
            result=dict(published_cadence_ids=[f"cadence:world:bakery-district:{tick-1}"], deferred_windows=[],
                rejected_windows=[], b0_advanced_count=100, due_item_count=28, deferred_item_count=0, rejected_item_count=0),
            sample=dict(at=finish+.001, confirmed_tick=tick, rss_bytes=100_000_000, cpu_seconds=float(tick),
                storage_bytes={"graph.sqlite3":4096, "graph.sqlite3-wal":4096*tick},
                execution=dict(state="running", queue_depth=1, queue_wait_ms=0., service_ms=0., failure=None),
                caches=dict(graph={key:0 for key in ("_nodes", "_relations", "_idempotency", "_checkpoints", "_branch_markers")},
                    gameplay={key:0 for key in ("_events", "_transactions", "_outbox")}, session_events=0,
                    light_memory_events=0, heavy_normalizer_events=0, population_receipts=min(tick,2),
                    population_fingerprints=min(tick,2), cadence=1, projection=1, preview=1, publisher_records=min(tick,2),
                    authority_bus=min(tick,2) + min(tick,32), authority_bus_types={
                        "population_cadence_event": min(tick,2), "siming.fairness_snapshot": min(tick,32)}))))
    return rows, config, actors


def test_window_replay_checks_raw_times_fixtures_and_all_samples():
    rows, config, actors = trace()
    result = evidence.replay_windows(rows, config, actors)
    assert result["measured_windows"] == 30 and result["drain_windows"] == 0
    assert result["performance_passed"] and result["cache_bounds_passed"]
    assert result["metrics"]["cadence_p95_ms"] == pytest.approx(300)
    for mutate in (
        lambda row: row.update(target_tick=True),
        lambda row: row.update(cadence_ms=0),
        lambda row: row.update(finished_at=float("nan")),
        lambda row: row.update(backlog=1),
        lambda row: row["fixtures"][0]["rows"][0].update(actor_id="char_a"),
        lambda row: row["sample"].update(confirmed_tick=2),
    ):
        bad = deepcopy(rows)
        mutate(bad[1])
        with pytest.raises(ValueError):
            evidence.replay_windows(bad, config, actors)
    with pytest.raises(ValueError, match="coverage"):
        evidence.replay_windows(rows[:-1], config, actors)

    bad = deepcopy(rows)
    bad[1]["sample"]["caches"]["authority_bus"] += 1
    with pytest.raises(ValueError, match="cache_value"):
        evidence.replay_windows(bad, config, actors)


def test_bad_performance_and_cache_growth_are_reported_not_hidden():
    rows, config, actors = trace()
    for row in rows[1:]:
        row.update(finished_at=row["started_at"]+.95, cadence_ms=850., advance_lag_windows=.95)
        row['driver_finished_at'] = row['driver_started_at'] + .95
        row["sample"]["at"] = row["finished_at"]+.001
    rows[1]["sample"]["caches"]["graph"]["_nodes"] = 1
    result = evidence.replay_windows(rows, config, actors)
    assert not result["performance_passed"] and not result["cache_bounds_passed"]
    assert result["metrics"]["cadence_p95_ms"] == pytest.approx(850)
    accelerated, config, actors = trace(seconds=3, mode="ten_x")
    result = evidence.replay_windows(accelerated, config, actors)
    assert result["measured_windows"] == 30 and result["budget_ms"] == 80


def test_extra_real_drain_windows_do_not_enter_steady_measurements():
    rows, config, actors = trace()
    drain = deepcopy(rows[-1])
    drain.update(target_tick=31, previous_tick=30, expected_at=131., started_at=131.,
        driver_started_at=81., driver_finished_at=83.,
        cadence_started_at=131., finished_at=133., fixture_ms=0., cadence_ms=2000.,
        advance_lag_windows=2., backlog=2, fixtures=[])
    drain["sample"].update(confirmed_tick=31, at=133.001, cpu_seconds=31.)
    drain["result"]["published_cadence_ids"] = ["cadence:world:bakery-district:30"]
    rows.append(drain)
    result = evidence.replay_windows(rows, config, actors)
    assert result["drain_windows"] == 1 and result["performance_passed"]
    assert result["metrics"]["cadence_p95_ms"] == pytest.approx(300)
    assert result["drain_max_lag_windows"] == pytest.approx(2)


def test_windows_cannot_finish_before_actual_driver_deadlines():
    rows, config, actors = trace()
    for index, row in enumerate(rows[1:]):
        start = 100. + index * .01
        row.update(started_at=start, cadence_started_at=start+.001, finished_at=start+.003,
            driver_started_at=start-50., driver_finished_at=start+.003-50.,
            fixture_ms=1., cadence_ms=2., backlog=0, advance_lag_windows=0.)
        row['sample']['at'] = start+.004
    with pytest.raises(ValueError, match='deadline'):
        evidence.replay_windows(rows, config, actors)


def test_windows_use_driver_clock_not_perf_counter_resolution_mapping():
    rows, config, actors = trace()
    for row in rows[1:]:
        for key in ('started_at', 'cadence_started_at', 'finished_at'):
            row[key] -= .003
        row['sample']['at'] -= .003
    assert evidence.replay_windows(rows, config, actors)['performance_passed']


def test_request_replay_requires_full_schedule_and_observes_failures():
    config = dict(population=100, seed=31, mode="one_x", seconds=60)
    report = dict(origin=100., load_end=160., finished_at=161., peak_in_flight=8)
    events = [row for row in MixedLoadSchedule(100, 31, "one_x").events(60)
        if row.kind in {"health", "ws_read", "fact", "interaction", "character_model", "siming_model", "owner_contention"}]
    report["requests"] = [dict(key=event.transaction_id, kind=event.kind, ordinal=event.ordinal,
        expected_at=100+event.at_ms/1000, offered_at=100+event.at_ms/1000,
        issued_at=100+event.at_ms/1000, finished_at=100+event.at_ms/1000+.1,
        status="handler_finished", result={}) for event in events]
    report.update(offered=len(events), dispatched=len(events), failed=0)
    assert evidence.replay_requests(report, config, side="client")["complete_traffic"]
    for mutate in (
        lambda value: value["requests"].pop(),
        lambda value: value["requests"][0].update(expected_at=101.),
        lambda value: value.update(offered=True),
        lambda value: value["requests"][1].update(key=value["requests"][0]["key"]),
        lambda value: value.update(peak_in_flight=1),
    ):
        bad = deepcopy(report)
        mutate(bad)
        with pytest.raises(ValueError):
            evidence.replay_requests(bad, config, side="client")
    report["requests"][0].update(status="drain_timeout")
    report["failed"] = 1
    result = evidence.replay_requests(report, config, side="client")
    assert not result["complete_traffic"] and result["failed"] == 1
    report["requests"][0].update(status="handler_failed", error="ValueError")
    assert evidence.replay_requests(report, config, side="client")["failed"] == 1


def test_provider_counts_are_actual_network_success_and_distinct_scheduled_tasks():
    requests, rows = [], []
    for ordinal in range(1, 4):
        for family in ("character", "siming"):
            start = 100 + ordinal * 60
            key = f"request:{family}:{ordinal}"
            requests.append(dict(key=key, kind=family+"_model", ordinal=ordinal, issued_at=start,
                status="handler_finished", result=dict(response_at=start+3, status="completed", source_event_id=key)))
            rows.append(dict(type="provider_result", ordinal=len(rows)+1, family=family,
                stage="dialogue_generation" if family == "character" else "candidate", thread_id=8, process_id=200,
                started_at=start+1, finished_at=start+2, request_sha256=f"{len(rows)+1:064x}",
                source_event_ids=[] if family == "character" else [key], validated=True,
                transport_attempted=True, transport_succeeded=True, fallback_used=False,
                fault_key=None, error=None, qualified_success=True, output_sha256="a"*64,
                provider_kind="http", model="model", endpoint_host="localhost"))
    server = dict(provider_peak_active=2, provider_active=0, pending_timeout=None, owner_threads=[[200, 4]], owner_pid=200)
    result = evidence.replay_providers(rows, requests, server)
    assert result["first_three_live_tasks_passed"] and result["isolated"]
    assert result["live_tasks"] == dict(character=3, siming=3)
    wrong_process = deepcopy(rows)
    wrong_process[0]["process_id"] = 100
    assert not evidence.replay_providers(wrong_process, requests, server)["isolated"]
    assert not evidence.replay_providers(rows, requests, dict(server, owner_threads=[[200, 8]]))["isolated"]
    failed = deepcopy(rows)
    failed[0].update(transport_succeeded=False, error="HTTPError", qualified_success=False)
    result = evidence.replay_providers(failed, requests, server)
    assert not result["first_three_live_tasks_passed"] and result["live_tasks"]["character"] == 2
    failed[0]["qualified_success"] = True
    with pytest.raises(ValueError):
        evidence.replay_providers(failed, requests, server)
    # 多个 B2 L2 stage 不能冒充一个新的固定 dialogue 任务。
    stages = deepcopy(rows)
    stages[0]["stage"] = "l2_reasoning"
    assert evidence.replay_providers(stages, requests, server)["live_tasks"]["character"] == 2


def test_transport_proof_rejects_ack_without_correlated_fact_and_duplicate_result():
    terminal = dict(message_type="spatial_access_runtime_state_snapshot", event_type=None,
        actor_id="char_b", updated_at=123, current_zone_id="zone_focus")
    records = [dict(key="fact:1", type="sent", at=100.1, producer_ts=123, source_type="raw_fact_event"),
        dict(key="fact:1", type="accepted", at=100.2, accepted=True, source_type="raw_fact_event"),
        dict(key="fact:1", type="response", at=100.3, **terminal)]
    requests = [dict(key="fact:1", kind="fact", status="handler_finished", expected_at=100., issued_at=100.,
        finished_at=100.4, result=dict(accepted_at=100.2, response_at=100.3, **terminal))]
    result = evidence.replay_responses(records, requests)
    assert result["fact_responses"] == 1 and result["metrics"]["fact_p95_ms"] == pytest.approx(300)
    for bad in (records[:-1], [*records, records[-1]], [*records[:-1], {**records[-1], "updated_at":124}]):
        with pytest.raises(ValueError):
            evidence.replay_responses(bad, requests)


def test_transport_proof_reuses_actual_full_and_delta_validation():
    import json
    from test_population_mixed_transport import _mixed_packets
    packets = _mixed_packets(False)
    rows = [dict(key="read:1", type="mirror_packet", at=100.1, raw_text=json.dumps(packets[0])),
        dict(key="read:1", type="accepted", at=100.2, accepted=True, source_type="gameplay_mirror_snapshot_request"),
        dict(key="read:1", type="mirror_packet", at=100.3, raw_text=json.dumps(packets[1])),
        dict(key="read:1", type="snapshot", at=100.3, message=packets[1])]
    requests = [dict(key="read:1", kind="ws_read", status="handler_finished", issued_at=100.,
        expected_at=100., finished_at=100.4, result=dict(accepted_at=100.2, response_at=100.3,
            actor_ref="character:char_a", checksum=packets[1]["payload"]["target_snapshot_checksum"], confirmed_tick=7))]
    assert evidence.replay_responses(rows, requests)["mirror_responses"] == 1
    bad = deepcopy(rows)
    message = json.loads(bad[2]["raw_text"])
    message["payload"]["base_snapshot_checksum"] = "sha256:" + "0"*64
    bad[2]["raw_text"] = json.dumps(message)
    with pytest.raises(ValueError):
        evidence.replay_responses(bad, requests)


def test_ws_fault_replay_requires_a_new_applied_packet_after_pause():
    import json
    from test_population_mixed_transport import _mixed_packets
    from scripts.verification.population_mixed_mirror import MixedMirrorReceiver
    first, second = _mixed_packets(False)
    receiver = MixedMirrorReceiver({"character:char_a"}, epoch=1)
    def packet(message, at):
        raw = json.dumps(message)
        return dict(key="slow", type="fault_mirror_packet", at=at, epoch=1, raw_text=raw, decision=receiver.receive(raw))
    rows = [dict(key="slow", type="fault_bound", at=1., epoch=1, actor_refs=["character:char_a"], max_queue=1),
        packet(first, 1.1), dict(key="slow", type="fault_pause", at=2.),
        dict(key="slow", type="fault_resume", at=7.), packet(second, 7.1)]
    tasks = [dict(key="slow", kind="slow_consumer", status="handler_finished", result=dict(pause_started_at=2., epoch=1)),
        dict(key="resume", kind="resume_consumer", status="handler_finished", issued_at=7., finished_at=7.3,
            result=dict(epoch=1, sequence=2, confirmed_ticks={"character:char_a":7}, resumed_at=7., pause_started_at=2.,
                recovered_at=7.2, healthy_cutoff=7, previous_epoch=1))]
    healthy = {"resume:healthy":dict(confirmed_tick=7, response_at=7.05)}
    result = evidence.replay_ws_faults(rows, tasks, ["char_a"], healthy)
    assert result["pause_seconds"] == [5.]
    old = deepcopy(tasks)
    old[1]["result"]["sequence"] = 1
    with pytest.raises(ValueError, match="fresh"):
        evidence.replay_ws_faults(rows[:-1], old, ["char_a"], healthy)
    bad = deepcopy(rows)
    bad[-1]["decision"]["applied"] = False
    with pytest.raises(ValueError):
        evidence.replay_ws_faults(bad, tasks, ["char_a"], healthy)
    closed = dict(key='slow', type='fault_controlled_close', at=7.05, epoch=1,
        reason_code='mirror_delivery_unrecoverable', route='gameplay_mirror_transport')
    with pytest.raises(ValueError, match='closed'):
        evidence.replay_ws_faults(rows[:-1]+[closed, rows[-1]], tasks, ['char_a'], healthy)
    with pytest.raises(ValueError, match='closed'):
        evidence.replay_ws_faults(rows+[dict(closed, at=7.15)], tasks, ['char_a'], healthy)
    with pytest.raises(ValueError, match='closed'):
        evidence.replay_ws_faults(rows+[dict(closed, at=7.15), dict(closed, at=7.3)], tasks, ['char_a'], healthy)
    fresh = deepcopy(first)
    fresh['payload']['connection_epoch'] = 2
    new_receiver = MixedMirrorReceiver({'character:char_a'}, epoch=2)
    raw = json.dumps(fresh)
    new_rows = rows[:-1] + [closed,
        dict(key='slow', type='fault_bound', at=7.06, epoch=2, actor_refs=['character:char_a'], max_queue=1),
        dict(key='slow', type='fault_mirror_packet', at=7.1, epoch=2, raw_text=raw, decision=new_receiver.receive(raw))]
    new_tasks = deepcopy(tasks)
    new_tasks[1]['result'].update(epoch=2, sequence=1)
    assert evidence.replay_ws_faults(new_rows, new_tasks, ['char_a'], healthy)['pause_seconds'] == [5.]
