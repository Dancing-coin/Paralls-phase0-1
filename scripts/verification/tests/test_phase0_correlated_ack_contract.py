from pathlib import Path


SCRIPTS_ROOT = Path(__file__).resolve().parents[2]


def test_player_intent_mapper_generates_collision_safe_request_ids() -> None:
    source = (SCRIPTS_ROOT / "player" / "PlayerIntentMapper.gd").read_text(encoding="utf-8")
    player_input_source = source.split("func emit_visual_fact_event", 1)[0]

    assert "var request_sequence := 0" in player_input_source
    assert "request_sequence += 1" in source
    assert '"player_input:%s:%s:%s:%s"' in source
    assert "[player_actor_id, intent_type, producer_ts, request_sequence]" in source
    assert player_input_source.count('"request_id": request_id') == 7
    assert player_input_source.count('"producer_ts": producer_ts') == 7
    assert "\"producer_ts\": Time.get_ticks_msec()" not in player_input_source


def test_main_demo_tracks_acknowledgements_by_request_id() -> None:
    source = (SCRIPTS_ROOT / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")

    assert "var acknowledged_request_ids: Dictionary = {}" in source
    assert 'var request_id := str(payload.get("request_id", ""))' in source
    assert "acknowledged_request_ids[request_id] = payload.duplicate(true)" in source
    assert "func _wait_for_request_ack(request_id: String, timeout_ms: int) -> bool:" in source
    assert "acknowledged_request_ids.has(request_id)" in source
    assert "pending_failed_move_ack_seen" not in source
    assert "pending_failed_interaction_ack_seen" not in source
    assert 'if str(payload.get("route", "")) == "local_motion":' not in source
    assert 'if str(payload.get("route", "")) == "esm_service":' not in source


def test_main_demo_final_interaction_uses_quiescence_and_correlation_scoped_result() -> None:
    source = (SCRIPTS_ROOT / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")

    assert "@export var autotest_request_timeout_ms := 10000" in source
    assert "@export var autotest_transport_quiet_window_ms := 500" in source
    assert "@export var autotest_transport_quiet_timeout_ms := 10000" in source
    assert "var autotest_transport_quiescent := false" in source
    assert "matched_success_object_result" in source
    assert "matched_success_environment_result" in source
    assert "func _wait_for_backend_quiet(quiet_window_ms: int, timeout_ms: int) -> bool:" in source
    assert 'pending_failed_interaction_correlation_id = "interact:%s" % failed_interaction_request.get("producer_ts", 0)' in source
    assert 'str(payload.get("correlation_id", "")) == pending_failed_interaction_correlation_id' in source
    assert 'await _fail_autotest("far_move_ack_timeout", far_move_request)' in source
    assert 'await _fail_autotest("failed_interaction_ack_timeout", failed_interaction_request)' in source
    assert 'await _fail_autotest("failed_interaction_result_timeout", failed_interaction_request)' in source
    assert '_emit_move_intent_request(autotest_final_position, "locomotion")' not in source


def test_main_demo_timeout_path_cannot_log_failed_interaction_success() -> None:
    source = (SCRIPTS_ROOT / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    run_section = source.split("func _run_autotest_inputs() -> void:", 1)[1].split(
        "func _wait_for_request_ack", 1
    )[0]

    failure_index = run_section.index('await _fail_autotest("failed_interaction_result_timeout", failed_interaction_request)')
    success_index = run_section.index('_bus_log("phase0_autotest_stage:failed_interaction_resolved")')
    assert "return" in run_section[failure_index:success_index]
    assert 'await _begin_autotest_shutdown("phase0_autotest_complete")' in run_section[success_index:]


def test_main_demo_rejects_empty_result_correlations_and_resets_match_state() -> None:
    source = (SCRIPTS_ROOT / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    world_result_section = source.split("func _on_world_result_received(payload: Dictionary) -> void:", 1)[1].split(
        "func _on_debug_event_logged", 1
    )[0]
    run_section = source.split("func _run_autotest_inputs() -> void:", 1)[1].split(
        "func _wait_for_request_ack", 1
    )[0]

    assert world_result_section.count('and pending_success_interaction_correlation_id != ""') == 3
    assert 'and pending_failed_interaction_correlation_id != ""' in world_result_section
    assert (
        'var success_interaction_request := _emit_interaction_request("obj_letter", "inspect")\n'
        '\tmatched_success_interaction_result = false\n'
        '\tmatched_success_object_result = false\n'
        '\tmatched_success_environment_result = false\n'
        '\tpending_success_interaction_correlation_id = "interact:%s" % success_interaction_request.get("producer_ts", 0)'
    ) in run_section
    assert (
        'var failed_interaction_request := _emit_interaction_request_without_near_object_fact("obj_letter", "inspect")\n'
        '\tmatched_failed_interaction_result = false\n'
        '\tpending_failed_interaction_correlation_id = "interact:%s" % failed_interaction_request.get("producer_ts", 0)'
    ) in run_section


def test_main_demo_wait_helpers_use_explicit_integer_deadlines() -> None:
    source = (SCRIPTS_ROOT / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    helper_block = source.split("func _wait_for_request_ack", 1)[1].split("func _fail_autotest", 1)[0]
    typed_deadline = "var deadline: int = Time.get_ticks_msec() + max(timeout_ms, 1)"

    assert helper_block.count(typed_deadline) == 4
    assert "var deadline :=" not in helper_block


def test_main_demo_uses_exact_barriers_before_near_and_far_moves() -> None:
    source = (SCRIPTS_ROOT / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    run_section = source.split("func _run_autotest_inputs() -> void:", 1)[1].split(
        "func _set_autotest_actor_local_perception_enabled", 1
    )[0]

    focus_index = run_section.index("_force_focus_target(interactive_object)")
    pre_barrier_index = run_section.index(
        'await _drain_backend_transport("pre_interaction_barrier_ack_timeout")'
    )
    near_move_index = run_section.index(
        'var near_move_request := _emit_move_intent_request(autotest_interact_position, "locomotion")'
    )
    success_wait_index = run_section.index(
        "await _wait_for_successful_interaction_result(autotest_request_timeout_ms)"
    )
    quiescence_index = run_section.index("autotest_transport_quiescent = true")
    post_barrier_index = run_section.index(
        'await _drain_backend_transport("post_success_barrier_ack_timeout")'
    )
    far_move_index = run_section.index(
        'var far_move_request := _emit_move_intent_request(autotest_failed_interact_position, "locomotion")'
    )

    assert focus_index < pre_barrier_index < near_move_index
    assert near_move_index < success_wait_index < quiescence_index < post_barrier_index < far_move_index
    assert "return" in run_section[pre_barrier_index:near_move_index]
    assert "return" in run_section[post_barrier_index:far_move_index]
    assert "await _wait_for_backend_quiet" not in run_section


def test_main_demo_transport_drain_waits_for_exact_ack_then_quiet_window() -> None:
    source = (SCRIPTS_ROOT / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    emit_section = source.split("func _emit_transport_barrier_request() -> Dictionary:", 1)[1].split(
        "func _drain_backend_transport", 1
    )[0]
    drain_section = source.split(
        "func _drain_backend_transport(barrier_failure_stage: String) -> bool:", 1
    )[1].split("func _wait_for_request_ack", 1)[0]

    assert 'bridge.has_method("send_transport_barrier")' in emit_section
    assert "return bridge.send_transport_barrier()" in emit_section
    assert "var barrier_request := _emit_transport_barrier_request()" in drain_section
    assert (
        'await _wait_for_request_ack(str(barrier_request.get("request_id", "")), autotest_request_timeout_ms)'
        in drain_section
    )
    assert 'await _fail_autotest(barrier_failure_stage, barrier_request)' in drain_section
    assert "last_backend_activity_ms = Time.get_ticks_msec()" in drain_section
    assert (
        "await _wait_for_backend_quiet(autotest_transport_quiet_window_ms, autotest_transport_quiet_timeout_ms)"
        in drain_section
    )
    assert 'await _fail_autotest("transport_not_quiet", barrier_request)' in drain_section


def test_main_demo_bounds_periodic_sampling_before_local_probes() -> None:
    source = (SCRIPTS_ROOT / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    run_section = source.split("func _run_autotest_inputs() -> void:", 1)[1].split(
        "func _wait_for_request_ack", 1
    )[0]

    begin_index = run_section.index('_bus_log("phase0_autotest_begin")')
    focus_override_index = run_section.index("focus_override_active = true")
    sampling_pause_index = run_section.index("suspend_near_object_visual_fact = true")
    spatial_pause_index = run_section.index("suspend_spatial_access_fact = true")
    first_probe_index = run_section.index("await _probe_floor_coverage()")
    success_wait_index = run_section.index(
        "await _wait_for_successful_interaction_result(autotest_request_timeout_ms)"
    )
    full_quiescence_index = run_section.index("autotest_transport_quiescent = true")

    assert begin_index < focus_override_index < sampling_pause_index < spatial_pause_index < first_probe_index
    assert run_section.count("suspend_near_object_visual_fact = true") == 2
    assert run_section.count("suspend_spatial_access_fact = true") == 2
    assert success_wait_index < full_quiescence_index


def test_character_replica_exposes_default_on_actor_local_perception_gate() -> None:
    source = (SCRIPTS_ROOT / "character" / "CharacterReplica.gd").read_text(encoding="utf-8")
    sample_section = source.split("func _sample_actor_local_perception() -> void:", 1)[1].split(
        "func _first_visible_actor_target", 1
    )[0]

    assert "var actor_local_perception_enabled := true" in source
    assert "func set_actor_local_perception_enabled(is_enabled: bool) -> void:" in source
    assert "actor_local_perception_enabled = is_enabled" in source
    assert sample_section.startswith("\n\tif not actor_local_perception_enabled:\n\t\treturn\n")


def test_main_demo_disables_replica_local_perception_before_autotest_probes() -> None:
    source = (SCRIPTS_ROOT / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    helper_signature = "func _set_autotest_actor_local_perception_enabled(is_enabled: bool) -> void:"

    assert helper_signature in source
    run_section = source.split("func _run_autotest_inputs() -> void:", 1)[1].split(
        "func _wait_for_request_ack", 1
    )[0]
    helper_section = source.split(helper_signature, 1)[1].split("func ", 1)[0]

    disable_index = run_section.index("_set_autotest_actor_local_perception_enabled(false)")
    first_probe_index = run_section.index("await _probe_floor_coverage()")
    assert disable_index < first_probe_index
    assert '[character_a, character_b, get_node_or_null("PlayerCharacter/CharacterReplica")]' in helper_section
    assert 'has_method("set_actor_local_perception_enabled")' in helper_section
    assert "replica.set_actor_local_perception_enabled(is_enabled)" in helper_section
    assert "set_process(false)" not in helper_section


def test_backend_bridge_generates_connection_local_transport_barriers() -> None:
    source = (SCRIPTS_ROOT / "autoload" / "BackendBridge.gd").read_text(encoding="utf-8")
    connect_section = source.split("func connect_to_backend(url: String) -> int:", 1)[1].split(
        "func send_envelope", 1
    )[0]
    barrier_section = source.split("func send_transport_barrier() -> Dictionary:", 1)[1].split(
        "func close_backend_connection", 1
    )[0]

    assert "var transport_barrier_sequence := 0" in source
    assert "if ws.get_ready_state() == WebSocketPeer.STATE_CONNECTING and last_requested_url == url:" in connect_section
    assert "return OK" in connect_section
    assert "transport_barrier_sequence = 0" in connect_section
    assert "transport_barrier_sequence += 1" in barrier_section
    assert '"transport_barrier:%s:%s"' in barrier_section
    assert "[producer_ts, transport_barrier_sequence]" in barrier_section
    assert '"message_type": "transport_barrier"' in barrier_section
    assert '"request_id": request_id' in barrier_section
    assert '"producer_ts": producer_ts' in barrier_section
    assert "return {}" in barrier_section
    assert 'return {"request_id": request_id, "producer_ts": producer_ts}' in barrier_section


def test_strict_phase0_selects_runtime_only_without_changing_normal_or_focus_urls() -> None:
    source = (SCRIPTS_ROOT / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    connect_section = source.split("func _connect_backend() -> void:", 1)[1].split(
        "func submit_dialogue", 1
    )[0]
    resolver_section = source.split("func _resolve_backend_url() -> String:", 1)[1].split(
        "func submit_dialogue", 1
    )[0]

    assert "var connection_url := _resolve_backend_url()" in connect_section
    assert "bridge.connect_to_backend(connection_url)" in connect_section
    assert 'var runtime_backend_url := OS.get_environment("PARALLS_BACKEND_WS_URL").strip_edges()' in source
    assert "if not runtime_backend_url.is_empty():" in source
    assert "backend_url = runtime_backend_url" in source
    assert "if not autotest_enabled or focus_autotest_enabled:" in resolver_section
    assert "return backend_url" in resolver_section
    assert 'var separator: String = "&" if backend_url.contains("?") else "?"' in resolver_section
    assert 'return "%s%sstream_mode=runtime_only" % [backend_url, separator]' in resolver_section
