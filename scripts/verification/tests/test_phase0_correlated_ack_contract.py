from pathlib import Path


SCRIPTS_ROOT = Path(__file__).resolve().parents[2]


def test_player_intent_mapper_generates_collision_safe_request_ids() -> None:
    source = (SCRIPTS_ROOT / "player" / "PlayerIntentMapper.gd").read_text(encoding="utf-8")
    player_input_source = source.split("func emit_visual_fact_event", 1)[0]

    assert "var request_sequence := 0" in player_input_source
    assert "request_sequence += 1" in source
    assert '"player_input:%s:%s:%s:%s"' in source
    assert "[player_actor_id, intent_type, producer_ts, request_sequence]" in source
    assert player_input_source.count('"request_id": request_id') == 4
    assert player_input_source.count('"producer_ts": producer_ts') == 4
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
