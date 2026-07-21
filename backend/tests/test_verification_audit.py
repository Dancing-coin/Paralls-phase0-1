from pathlib import Path
import sys

from app.verification_audit import evaluate_phase0_audit, evaluate_phase1_slice_audit

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "verification"))

from common import scan_direct_visual_fact_bypass


def _index_by_id(results: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(entry["id"]): entry for entry in results}


def test_phase0_audit_marks_missing_failed_interaction_and_weak_voice() -> None:
    report = evaluate_phase0_audit(
        pytest_passed=True,
        scene_load_ok=True,
        main_log="""
        [LocalPresentationBus] backend_connected:ws://127.0.0.1:8000/ws
        [LocalPresentationBus] phase0_dialogue_target:char_a
        [LocalPresentationBus] dialogue_applied:char_a
        [LocalPresentationBus] phase0_interact_target:obj_letter
        [LocalPresentationBus] object_state:obj_letter:visible
        [LocalPresentationBus] environment_state:alerted
        [LocalPresentationBus] attention_applied:char_b
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-main.png:0
        """,
        focus_log="""
        [LocalPresentationBus] phase0_focus_autotest_begin
        [LocalPresentationBus] focus_state_applied:char_a
        [LocalPresentationBus] focus_attention:char_a
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-focus.png:0
        """,
        main_screenshot_exists=True,
        focus_screenshot_exists=True,
        interaction_source="world_result = esm_service.resolve_interaction(event, is_in_range=True)",
        esm_service_source="",
        voice_controller_source="func play_stub_voice(_payload: Dictionary) -> void:\n    unit_size = 3.0",
        player_bridge_source="func before_player_shell_move(delta: float) -> void:\n    pass",
        character_replica_source="func consume_player_root_motion_request(delta: float) -> Vector3:\n    return Vector3.ZERO",
    )

    results = _index_by_id(report["results"])

    assert report["overall_strict_phase0_passed"] is False
    assert results["dialogue_loop"]["status"] == "proved"
    assert results["successful_interaction"]["status"] == "proved"
    assert results["failed_interaction"]["status"] == "missing"
    assert results["voice_stub_path"]["status"] == "weak"
    assert results["player_root_motion_chain"]["status"] == "weak"
    assert results["npc_root_motion_patrol"]["status"] == "missing"


def test_phase0_audit_accepts_siming_output_runtime_evidence_without_attention_applied_log() -> None:
    report = evaluate_phase0_audit(
        pytest_passed=True,
        scene_load_ok=True,
        main_log="""
        [LocalPresentationBus] backend_connected:ws://127.0.0.1:8000/ws
        [LocalPresentationBus] phase0_dialogue_target:char_a
        [LocalPresentationBus] dialogue_applied:char_a
        [LocalPresentationBus] phase0_interact_target:obj_letter
        [LocalPresentationBus] object_state:obj_letter:visible
        [LocalPresentationBus] constraint_state_result:distance
        [LocalPresentationBus] environment_state:alerted
        [LocalPresentationBus] backend_message_type:siming_output
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-main.png:0
        """,
        focus_log="""
        [LocalPresentationBus] phase0_focus_autotest_begin
        [LocalPresentationBus] backend_message_type:siming_output
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-focus.png:0
        """,
        main_screenshot_exists=True,
        focus_screenshot_exists=True,
        interaction_source="world_result = esm_service.resolve_interaction(event, is_in_range=False)",
        esm_service_source='thermal_level=field_state.thermal_level\n"thermal_level"',
        voice_controller_source='func play_stub_voice(_payload: Dictionary) -> void:\n    _bus_log("voice_stub_played")',
        player_bridge_source='func before_player_shell_move(delta: float) -> void:\n    _apply_player_root_motion_drive(delta)',
        character_replica_source='func consume_player_root_motion_request(delta: float) -> Vector3:\n    return _consume_role_root_motion_world_delta()',
    )

    results = _index_by_id(report["results"])

    assert results["siming_reaction"]["status"] == "proved"


def test_phase0_audit_accepts_failed_interaction_resolved_marker() -> None:
    report = evaluate_phase0_audit(
        pytest_passed=True,
        scene_load_ok=True,
        main_log="""
        [LocalPresentationBus] backend_connected:ws://127.0.0.1:8000/ws
        [LocalPresentationBus] phase0_dialogue_target:char_a
        [LocalPresentationBus] dialogue_applied:char_a
        [LocalPresentationBus] phase0_interact_target:obj_letter
        [LocalPresentationBus] object_state:obj_letter:visible
        [LocalPresentationBus] phase0_autotest_stage:failed_interaction_resolved
        [LocalPresentationBus] environment_state:alerted
        [LocalPresentationBus] backend_message_type:siming_output
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-main.png:0
        """,
        focus_log="[LocalPresentationBus] phase0_screenshot_saved:D:\\demo-focus.png:0",
        main_screenshot_exists=True,
        focus_screenshot_exists=True,
        interaction_source="world_result = esm_service.resolve_interaction(event, is_in_range=False)",
        esm_service_source='thermal_level=field_state.thermal_level\n"thermal_level"',
        voice_controller_source='func play_stub_voice(_payload: Dictionary) -> void:\n    _bus_log("voice_stub_played")',
        player_bridge_source='func before_player_shell_move(delta: float) -> void:\n    _apply_player_root_motion_drive(delta)',
        character_replica_source='func consume_player_root_motion_request(delta: float) -> Vector3:\n    return _consume_role_root_motion_world_delta()',
    )

    results = _index_by_id(report["results"])

    assert results["failed_interaction"]["status"] == "proved"


def test_phase0_main_demo_autotest_failed_interaction_attempt_moves_to_far_position() -> None:
    project_root = Path(__file__).resolve().parents[2]
    controller_source = (
        project_root / "scripts" / "phase0" / "MainDemoController.gd"
    ).read_text(encoding="utf-8")

    assert '@export var autotest_failed_interact_position := Vector3(0.0, 0.5, 16.0)' in controller_source
    assert "_emit_move_intent_request(autotest_failed_interact_position, \"locomotion\")" in controller_source
    assert "_bus_log(\"phase0_autotest_failed_interaction_attempt\")" in controller_source


def test_phase0_main_demo_failed_interaction_position_stays_distinct_from_observation_vantage() -> None:
    project_root = Path(__file__).resolve().parents[2]
    controller_source = (
        project_root / "scripts" / "phase0" / "MainDemoController.gd"
    ).read_text(encoding="utf-8")

    assert '@export var autotest_final_position := Vector3(0.0, 0.5, 20.0)' in controller_source
    assert '@export var autotest_failed_interact_position := Vector3(0.0, 0.5, 20.0)' not in controller_source


def test_phase0_main_demo_failed_interaction_attempt_does_not_reemit_near_object_fact() -> None:
    project_root = Path(__file__).resolve().parents[2]
    controller_source = (
        project_root / "scripts" / "phase0" / "MainDemoController.gd"
    ).read_text(encoding="utf-8")

    assert "_emit_near_object_visual_fact(target_object_id)" in controller_source
    assert "_emit_interaction_request_without_near_object_fact(" in controller_source
    assert "phase0_autotest_failed_interaction_attempt" in controller_source
    assert "suspend_near_object_visual_fact = true" in controller_source
    assert "suspend_spatial_access_fact = true" in controller_source


def test_phase0_main_demo_failed_interaction_attempt_does_not_force_focus_target_change() -> None:
    project_root = Path(__file__).resolve().parents[2]
    controller_source = (
        project_root / "scripts" / "phase0" / "MainDemoController.gd"
    ).read_text(encoding="utf-8")

    failed_section = controller_source.split('_bus_log("phase0_autotest_failed_interaction_attempt")', 1)[0]
    tail = failed_section.split("_emit_move_intent_request(autotest_failed_interact_position, \"locomotion\")", 1)[-1]
    assert "_force_focus_target(interactive_object)" not in tail


def test_phase0_main_demo_failed_interaction_attempt_waits_for_correlated_constraint_result() -> None:
    project_root = Path(__file__).resolve().parents[2]
    controller_source = (
        project_root / "scripts" / "phase0" / "MainDemoController.gd"
    ).read_text(encoding="utf-8")

    assert "var acknowledged_request_ids: Dictionary = {}" in controller_source
    assert "pending_failed_move_ack_seen" not in controller_source
    assert "pending_failed_interaction_ack_seen" not in controller_source
    assert "pending_failed_interaction_result_seen" not in controller_source
    assert "await _wait_for_request_ack(" in controller_source
    assert "pending_failed_interaction_correlation_id" in controller_source
    assert "matched_failed_interaction_result" in controller_source
    assert "await _wait_for_failed_interaction_result(autotest_request_timeout_ms)" in controller_source


def test_phase0_main_demo_suppresses_free_move_intent_loop_during_focus_autotest() -> None:
    project_root = Path(__file__).resolve().parents[2]
    controller_source = (
        project_root / "scripts" / "phase0" / "MainDemoController.gd"
    ).read_text(encoding="utf-8")

    emit_move_section = controller_source.split("func _emit_move_intent_if_needed() -> void:", 1)[1].split(
        "func _sample_near_object_visual_fact", 1
    )[0]

    assert "if autotest_enabled or focus_autotest_enabled:" in emit_move_section


def test_phase0_autotest_paths_await_screenshot_before_quit_and_guard_reentry() -> None:
    project_root = Path(__file__).resolve().parents[2]
    controller_source = (
        project_root / "scripts" / "phase0" / "MainDemoController.gd"
    ).read_text(encoding="utf-8")

    assert "var autotest_run_started := false" in controller_source
    assert "var autotest_shutdown_in_progress := false" in controller_source
    assert "if autotest_run_started:" in controller_source
    assert "autotest_run_started = true" in controller_source
    assert "await _capture_autotest_screenshot()" in controller_source
    assert '_bus_log("phase0_autotest_stage:floor_coverage_complete")' in controller_source
    assert '_bus_log("phase0_autotest_stage:floor_grid_complete")' in controller_source
    assert '_bus_log("phase0_autotest_stage:locomotion_probe_complete")' in controller_source
    assert '_bus_log("phase0_autotest_stage:npc_patrol_probe_complete")' in controller_source
    assert '_bus_log("phase0_autotest_stage:gait_probe_complete")' in controller_source
    assert '_bus_log("phase0_autotest_stage:jump_probe_complete")' in controller_source
    assert '_bus_log("phase0_autotest_stage:npc_patrol_probe_begin")' in controller_source
    assert 'await _begin_autotest_shutdown("phase0_autotest_complete")' in controller_source
    assert 'await _begin_autotest_shutdown("phase0_focus_autotest_complete")' in controller_source
    assert 'func _begin_autotest_shutdown(reason: String) -> void:' in controller_source
    assert 'autotest_shutdown_in_progress = true' in controller_source
    assert 'bridge.close_backend_connection()' in controller_source
    assert 'call_deferred("_finish_autotest_run", reason)' in controller_source
    assert 'func _finish_autotest_run(reason: String) -> void:' in controller_source
    assert '_bus_log(reason)' in controller_source
    assert "get_tree().quit()" in controller_source


def test_phase0_audit_proves_observatory_runtime_evidence() -> None:
    report = evaluate_phase0_audit(
        pytest_passed=True,
        scene_load_ok=True,
        main_log="""
        [LocalPresentationBus] backend_connected:ws://127.0.0.1:8000/ws
        character_director_observatory_probe:state_payloads_ok=true
        character_director_observatory_probe:panels_populated=true
        character_director_observatory_probe:freeze_roundtrip_ok=true
        character_director_observatory_probe:actor_panel_populated=true
        character_director_observatory_probe:director_cast_world_siming_populated=true
        character_director_observatory_probe:timeline_multi_role_populated=true
        character_director_observatory_probe:ledger_pairwise_populated=true
        [LocalPresentationBus] character_agent_debug_snapshot:{"actor_id":"char_a"}
        [LocalPresentationBus] siming_debug_snapshot:{"selected_path":"visual_fact_path"}
        [LocalPresentationBus] world_outcome_trace:{"request_type":"inspect"}
        [LocalPresentationBus] script_beat_event:{"correlation_id":"corr-1"}
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-main.png:0
        """,
        focus_log="""
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-focus.png:0
        """,
        main_screenshot_exists=True,
        focus_screenshot_exists=True,
        interaction_source="request_ref=world_result.request_ref",
        esm_service_source='"thermal_level"',
        voice_controller_source='func play_stub_voice(_payload: Dictionary) -> void:\n    _bus_log("voice_stub_played")',
        player_bridge_source='func before_player_shell_move(delta: float) -> void:\n    _apply_player_root_motion_drive(delta)',
        character_replica_source='func consume_player_root_motion_request(delta: float) -> Vector3:\n    return _consume_role_root_motion_world_delta()',
    )

    results = _index_by_id(report["results"])

    assert results["observatory_state_payloads"]["status"] == "proved"
    assert results["observatory_panels_populated"]["status"] == "proved"
    assert results["observatory_actor_panel_populated"]["status"] == "proved"
    assert results["observatory_director_workstation_populated"]["status"] == "proved"
    assert results["observatory_timeline_multi_role"]["status"] == "proved"
    assert results["observatory_ledger_pairwise"]["status"] == "proved"
    assert results["observatory_freeze_roundtrip"]["status"] == "proved"


def test_phase0_audit_requires_stronger_siming_ui_presence_in_observatory() -> None:
    report = evaluate_phase0_audit(
        pytest_passed=True,
        scene_load_ok=True,
        main_log="""
        [LocalPresentationBus] backend_connected:ws://127.0.0.1:8000/ws
        [LocalPresentationBus] phase0_dialogue_target:char_a
        [LocalPresentationBus] dialogue_applied:char_a
        [LocalPresentationBus] phase0_interact_target:obj_letter
        [LocalPresentationBus] object_state:obj_letter:visible
        [LocalPresentationBus] constraint_state_result:distance
        [LocalPresentationBus] environment_state:alerted
        [LocalPresentationBus] backend_message_type:siming_output
        [LocalPresentationBus] voice_stub_played
        [LocalPresentationBus] player_root_motion_step:char_c
        [LocalPresentationBus] patrol_root_motion_step:char_a
        [LocalPresentationBus] locomotion_state:stance=stand gait=walk jump=none clip=walk_guard profile=walk rm=active
        [LocalPresentationBus] jump_probe:type=two_foot run=False apex=1.100 distance=0.820
        [LocalPresentationBus] jump_probe:type=single_leg run=True apex=1.240 distance=1.180
        [LocalPresentationBus] locomotion_probe:dx=0.010 dy=0.000 dz=-0.830
        character_director_observatory_probe:state_payloads_ok=true
        character_director_observatory_probe:panels_populated=true
        character_director_observatory_probe:freeze_roundtrip_ok=true
        character_director_observatory_probe:actor_panel_populated=true
        character_director_observatory_probe:director_cast_world_siming_populated=true
        character_director_observatory_probe:selected_actor_siming_summary_populated=true
        character_director_observatory_probe:bottom_strip_siming_populated=true
        character_director_observatory_probe:timeline_multi_role_populated=true
        character_director_observatory_probe:timeline_siming_populated=true
        character_director_observatory_probe:ledger_pairwise_populated=true
        character_director_observatory_probe:ledger_siming_pressure_populated=true
        [LocalPresentationBus] character_agent_debug_snapshot:{"actor_id":"char_a","latest_siming_summary":"催促追问"}
        [LocalPresentationBus] siming_debug_snapshot:{"selected_path":"visual_fact_path","summary":"催促追问"}
        [LocalPresentationBus] world_outcome_trace:{"request_type":"inspect"}
        [LocalPresentationBus] script_beat_event:{"correlation_id":"corr-1","siming_summaries":["催促追问"]}
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-main.png:0
        """,
        focus_log="""
        [LocalPresentationBus] phase0_focus_autotest_begin
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-focus.png:0
        """,
        main_screenshot_exists=True,
        focus_screenshot_exists=True,
        interaction_source="""
        request_ref=world_result.request_ref
        causation_id=world_result.causation_id
        correlation_id=world_result.correlation_id
        """,
        esm_service_source="""
        thermal_level=field_state.thermal_level
        "thermal_level"
        """,
        voice_controller_source='func play_stub_voice(_payload: Dictionary) -> void:\n    _bus_log("voice_stub_played")',
        player_bridge_source='func before_player_shell_move(delta: float) -> void:\n    _apply_player_root_motion_drive(delta)',
        character_replica_source="""
        func consume_player_root_motion_request(delta: float) -> Vector3:
            return _consume_role_root_motion_world_delta()
        func _move_toward_target(target: Vector3, delta: float, clear_on_arrival: bool) -> void:
            _bus_log("patrol_root_motion_step:%s" % actor_id)
        """,
    )

    results = _index_by_id(report["results"])

    assert results["observatory_selected_actor_siming_summary"]["status"] == "proved"
    assert results["observatory_bottom_strip_siming"]["status"] == "proved"
    assert results["observatory_timeline_siming"]["status"] == "proved"
    assert results["observatory_ledger_siming_pressure"]["status"] == "proved"
    assert report["overall_strict_phase0_passed"] is True


def test_character_director_observatory_probe_uses_runtime_backed_siming_evidence_only() -> None:
    project_root = Path(__file__).resolve().parents[2]
    probe_source = (
        project_root / "scripts" / "verification" / "CharacterDirectorObservatoryProbe.gd"
    ).read_text(encoding="utf-8")

    assert '"_format_bottom_strip_row"' in probe_source
    assert 'state.call("get_latest_bottom_strip_entries")' in probe_source
    assert 'state.call("get_dialogue_pair_entries")' in probe_source
    assert '"_build_expanded_payload_lines"' in probe_source
    assert '"_resolve_siming_pressure_context"' in probe_source
    assert 'synthetic_row["siming_summary"]' not in probe_source
    assert "dialogue_pairs[0].duplicate(true)" not in probe_source
    assert '{"type": "司命", "summary": current_runtime_siming_summary}' not in probe_source
    assert '{"type": "司命", "summary": runtime_summary}' not in probe_source
    bottom_strip_block = probe_source.split("var bottom_strip_siming_populated: bool = (", 1)[1].split(
        "var panels_populated: bool = (",
        1,
    )[0]
    assert "formatter_bottom_strip_siming_populated" not in bottom_strip_block
    assert "timeline_siming_populated" not in bottom_strip_block
    assert "if actor_panel_populated and selected_actor_siming_summary_populated:" in probe_source
    assert 'actor_panel.call("_resolve_feedback_summary", selected_payload)' in probe_source
    assert "not selected_actor_siming_summary.is_empty()" in probe_source
    assert probe_source.index("not selected_actor_siming_summary.is_empty()") < probe_source.index(
        "rendered_feedback_summary.find(selected_actor_siming_summary) >= 0"
    )
    assert "rendered_feedback_summary.find(selected_actor_siming_summary) >= 0" in probe_source


def test_backend_interact_route_emits_failed_interaction_diagnostics() -> None:
    project_root = Path(__file__).resolve().parents[2]
    main_source = (project_root / "backend" / "app" / "main.py").read_text(encoding="utf-8")

    assert "phase0_failed_interaction_diag" in main_source
    assert "actor_position" in main_source
    assert "target_object_id" in main_source
    assert "world_result.result_type" in main_source


def test_phase0_audit_proves_character_agent_execution_contract_runtime_evidence() -> None:
    report = evaluate_phase0_audit(
        pytest_passed=True,
        scene_load_ok=True,
        main_log="""
        [LocalPresentationBus] backend_connected:ws://127.0.0.1:8000/ws
        [LocalPresentationBus] phase0_dialogue_target:char_a
        [LocalPresentationBus] dialogue_applied:char_a
        [LocalPresentationBus] phase0_interact_target:obj_letter
        [LocalPresentationBus] object_state:obj_letter:visible
        [LocalPresentationBus] constraint_state_result:distance
        [LocalPresentationBus] environment_state:alerted
        [LocalPresentationBus] attention_applied:char_b
        [LocalPresentationBus] backend_message_raw:{"message_type":"character_agent_execution","payload":{"actor_id":"char_a","actor_control_frames":[{"actor_id":"char_a","controller_source":"agent","control_mode":"agent_controlled","target_ref":"char_a","action":"observe","gait":"walk"}],"presentation_plan":{"actor_id":"char_a","target_ref":"char_a","motion_state":{},"focus_state":{"target_id":"char_a"},"action_state":{"requested_action":"observe","override_state":""},"equipment_state":{},"expression_hint":"execution_bridge","physiology_hint":"stable","speech_state":{"active_command_type":"observe","utterance_request":"observe"}},"action_request_bundle":{"requested_actions":[]}}}
        [LocalPresentationBus] character_agent_execution:{"actor_id":"char_a","actor_control_frames":[{"actor_id":"char_a","controller_source":"agent","control_mode":"agent_controlled","target_ref":"char_a","action":"observe","gait":"walk"}],"presentation_plan":{"actor_id":"char_a","target_ref":"char_a","motion_state":{},"focus_state":{"target_id":"char_a"},"action_state":{"requested_action":"observe","override_state":""},"equipment_state":{},"expression_hint":"execution_bridge","physiology_hint":"stable","speech_state":{"active_command_type":"observe","utterance_request":"observe"}},"action_request_bundle":{"requested_actions":[]}}
        [LocalPresentationBus] voice_stub_played
        [LocalPresentationBus] player_root_motion_step:char_c
        [LocalPresentationBus] patrol_root_motion_step:char_a
        [LocalPresentationBus] locomotion_state:stance=stand gait=walk jump=none clip=walk_guard profile=walk rm=active
        [LocalPresentationBus] jump_probe:type=two_foot run=False apex=1.100 distance=0.820
        [LocalPresentationBus] jump_probe:type=single_leg run=True apex=1.240 distance=1.180
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-main.png:0
        """,
        focus_log="""
        [LocalPresentationBus] phase0_focus_autotest_begin
        [LocalPresentationBus] focus_state_applied:char_a
        [LocalPresentationBus] focus_attention:char_a
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-focus.png:0
        """,
        main_screenshot_exists=True,
        focus_screenshot_exists=True,
        interaction_source="""
        request_ref=world_result.request_ref
        causation_id=world_result.causation_id
        correlation_id=world_result.correlation_id
        """,
        esm_service_source="""
        thermal_level=field_state.thermal_level
        "thermal_level"
        """,
        voice_controller_source="""
        func play_stub_voice(_payload: Dictionary) -> void:
            _bus_log("voice_stub_played")
        """,
        player_bridge_source="""
        func before_player_shell_move(delta: float) -> void:
            _apply_player_root_motion_drive(delta)
        """,
        character_replica_source="""
        func consume_player_root_motion_request(delta: float) -> Vector3:
            return _consume_role_root_motion_world_delta()
        func _move_toward_target(target: Vector3, delta: float, clear_on_arrival: bool) -> void:
            _bus_log("patrol_root_motion_step:%s" % actor_id)
        """,
    )

    results = _index_by_id(report["results"])

    assert results["character_agent_execution_contract"]["status"] == "proved"


def test_phase0_audit_proves_character_agent_execution_consumer_runtime_evidence() -> None:
    report = evaluate_phase0_audit(
        pytest_passed=True,
        scene_load_ok=True,
        main_log="""
        [LocalPresentationBus] backend_connected:ws://127.0.0.1:8000/ws
        [LocalPresentationBus] backend_message_raw:{"message_type":"character_agent_execution","payload":{"actor_id":"char_a","actor_control_frames":[{"actor_id":"char_a","controller_source":"agent","control_mode":"agent_controlled","target_ref":"char_a","action":"observe","gait":"walk"}],"presentation_plan":{"actor_id":"char_a","target_ref":"char_a","motion_state":{},"focus_state":{"target_id":"char_a"},"action_state":{"requested_action":"observe","override_state":""},"equipment_state":{},"expression_hint":"execution_bridge","physiology_hint":"stable","speech_state":{"active_command_type":"observe","utterance_request":"observe"}},"action_request_bundle":{"requested_actions":[]}}}
        [LocalPresentationBus] backend_message_type:character_agent_execution
        [LocalPresentationBus] character_agent_execution:{"actor_id":"char_a","actor_control_frames":[{"actor_id":"char_a","controller_source":"agent","control_mode":"agent_controlled","target_ref":"char_a","action":"observe","gait":"walk"}],"presentation_plan":{"actor_id":"char_a","target_ref":"char_a","motion_state":{},"focus_state":{"target_id":"char_a"},"action_state":{"requested_action":"observe","override_state":""},"equipment_state":{},"expression_hint":"execution_bridge","physiology_hint":"stable","speech_state":{"active_command_type":"observe","utterance_request":"observe"}},"action_request_bundle":{"requested_actions":[]}}
        character_agent_execution_probe:consumer_seen=true
        character_agent_execution_probe:legacy_output_seen=false
        [LocalPresentationBus] phase0_dialogue_target:char_a
        [LocalPresentationBus] dialogue_applied:char_a
        [LocalPresentationBus] phase0_interact_target:obj_letter
        [LocalPresentationBus] object_state:obj_letter:visible
        [LocalPresentationBus] constraint_state_result:distance
        [LocalPresentationBus] environment_state:alerted
        [LocalPresentationBus] attention_applied:char_b
        [LocalPresentationBus] voice_stub_played
        [LocalPresentationBus] player_root_motion_step:char_c
        [LocalPresentationBus] patrol_root_motion_step:char_a
        [LocalPresentationBus] locomotion_state:stance=stand gait=walk jump=none clip=walk_guard profile=walk rm=active
        [LocalPresentationBus] jump_probe:type=two_foot run=False apex=1.100 distance=0.820
        [LocalPresentationBus] jump_probe:type=single_leg run=True apex=1.240 distance=1.180
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-main.png:0
        """,
        focus_log="""
        [LocalPresentationBus] phase0_focus_autotest_begin
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-focus.png:0
        """,
        main_screenshot_exists=True,
        focus_screenshot_exists=True,
        interaction_source="""
        request_ref=world_result.request_ref
        causation_id=world_result.causation_id
        correlation_id=world_result.correlation_id
        """,
        esm_service_source="""
        thermal_level=field_state.thermal_level
        "thermal_level"
        """,
        voice_controller_source="""
        func play_stub_voice(_payload: Dictionary) -> void:
            _bus_log("voice_stub_played")
        """,
        player_bridge_source="""
        func before_player_shell_move(delta: float) -> void:
            _apply_player_root_motion_drive(delta)
        """,
        character_replica_source="""
        func consume_player_root_motion_request(delta: float) -> Vector3:
            return _consume_role_root_motion_world_delta()
        func _move_toward_target(target: Vector3, delta: float, clear_on_arrival: bool) -> void:
            _bus_log("patrol_root_motion_step:%s" % actor_id)
        """,
    )

    results = _index_by_id(report["results"])

    assert results["character_agent_execution_consumer"]["status"] == "proved"


def test_phase0_audit_proves_root_motion_player_and_patrol_evidence() -> None:
    report = evaluate_phase0_audit(
        pytest_passed=True,
        scene_load_ok=True,
        main_log="""
        [LocalPresentationBus] backend_connected:ws://127.0.0.1:8000/ws
        [LocalPresentationBus] phase0_dialogue_target:char_a
        [LocalPresentationBus] dialogue_applied:char_a
        [LocalPresentationBus] phase0_interact_target:obj_letter
        [LocalPresentationBus] object_state:obj_letter:visible
        [LocalPresentationBus] constraint_state_result:distance
        [LocalPresentationBus] environment_state:alerted
        [LocalPresentationBus] attention_applied:char_b
        [LocalPresentationBus] player_root_motion_step:char_c
        [LocalPresentationBus] patrol_root_motion_step:char_a
        [LocalPresentationBus] locomotion_state:stance=stand gait=walk jump=none clip=walk_guard profile=walk rm=active
        [LocalPresentationBus] jump_probe:type=two_foot run=False apex=1.100 distance=0.820
        [LocalPresentationBus] jump_probe:type=single_leg run=True apex=1.240 distance=1.180
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-main.png:0
        """,
        focus_log="""
        [LocalPresentationBus] phase0_focus_autotest_begin
        [LocalPresentationBus] focus_state_applied:char_a
        [LocalPresentationBus] focus_attention:char_a
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-focus.png:0
        """,
        main_screenshot_exists=True,
        focus_screenshot_exists=True,
        interaction_source="world_result = esm_service.resolve_interaction(event, is_in_range=False)",
        esm_service_source="thermal_level=field_state.thermal_level\nfield_delta_summary=[\"light_level\", \"noise_level\", \"thermal_level\", \"smoke_density\", \"visibility_level\"]",
        voice_controller_source="""
        func play_stub_voice(_payload: Dictionary) -> void:
            _bus_log("voice_stub_played")
        """,
        player_bridge_source="""
        func before_player_shell_move(delta: float) -> void:
            _apply_player_root_motion_drive(delta)
        """,
        character_replica_source="""
        func consume_player_root_motion_request(delta: float) -> Vector3:
            return _consume_role_root_motion_world_delta()
        func _move_toward_target(target: Vector3, delta: float, clear_on_arrival: bool) -> void:
            _bus_log("patrol_root_motion_step:%s" % actor_id)
        """,
    )

    results = _index_by_id(report["results"])

    assert results["player_root_motion_chain"]["status"] == "proved"
    assert results["npc_root_motion_patrol"]["status"] == "proved"
    assert results["locomotion_state_ui"]["status"] == "proved"
    assert results["jump_variant_probes"]["status"] == "proved"


def test_phase0_audit_requires_explicit_esm_request_lineage_and_thermal_field_evidence() -> None:
    report = evaluate_phase0_audit(
        pytest_passed=True,
        scene_load_ok=True,
        main_log="""
        [LocalPresentationBus] backend_connected:ws://127.0.0.1:8000/ws
        [LocalPresentationBus] phase0_dialogue_target:char_a
        [LocalPresentationBus] dialogue_applied:char_a
        [LocalPresentationBus] phase0_interact_target:obj_letter
        [LocalPresentationBus] object_state:obj_letter:visible
        [LocalPresentationBus] constraint_state_result:distance
        [LocalPresentationBus] environment_state:alerted
        [LocalPresentationBus] attention_applied:char_b
        [LocalPresentationBus] player_root_motion_step:char_c
        [LocalPresentationBus] patrol_root_motion_step:char_a
        [LocalPresentationBus] locomotion_state:stance=stand gait=walk jump=none clip=walk_guard profile=walk rm=active
        [LocalPresentationBus] jump_probe:type=two_foot run=False apex=1.100 distance=0.820
        [LocalPresentationBus] jump_probe:type=single_leg run=True apex=1.240 distance=1.180
        [LocalPresentationBus] voice_stub_played
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-main.png:0
        """,
        focus_log="""
        [LocalPresentationBus] phase0_focus_autotest_begin
        [LocalPresentationBus] focus_state_applied:char_a
        [LocalPresentationBus] focus_attention:char_a
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-focus.png:0
        """,
        main_screenshot_exists=True,
        focus_screenshot_exists=True,
        interaction_source="""
        messages.append(_as_world_result_envelope(object_state_result.model_dump()))
        messages.append(_as_world_result_envelope(body_state_result.model_dump()))
        messages.append(_as_world_result_envelope(environment_result.model_dump()))
        request_ref=world_result.request_ref
        causation_id=world_result.causation_id
        correlation_id=world_result.correlation_id
        """,
        esm_service_source="""
        thermal_level=field_state.thermal_level
        field_delta_summary=["light_level", "noise_level", "thermal_level", "smoke_density", "visibility_level"]
        """,
        voice_controller_source="""
        func play_stub_voice(_payload: Dictionary) -> void:
            _bus_log("voice_stub_played")
        """,
        player_bridge_source="""
        func before_player_shell_move(delta: float) -> void:
            _apply_player_root_motion_drive(delta)
        """,
        character_replica_source="""
        func consume_player_root_motion_request(delta: float) -> Vector3:
            return _consume_role_root_motion_world_delta()
        func _move_toward_target(target: Vector3, delta: float, clear_on_arrival: bool) -> void:
            _bus_log("patrol_root_motion_step:%s" % actor_id)
        """,
    )

    results = _index_by_id(report["results"])

    assert results["esm_request_lineage"]["status"] == "proved"
    assert results["esm_thermal_field"]["status"] == "proved"


def test_phase0_audit_requires_locomotion_state_ui_evidence() -> None:
    report = evaluate_phase0_audit(
        pytest_passed=True,
        scene_load_ok=True,
        main_log="""
        [LocalPresentationBus] backend_connected:ws://127.0.0.1:8010/ws
        [LocalPresentationBus] phase0_dialogue_target:char_a
        [LocalPresentationBus] dialogue_applied:char_a
        [LocalPresentationBus] phase0_interact_target:obj_letter
        [LocalPresentationBus] object_state:obj_letter:visible
        [LocalPresentationBus] constraint_state_result:distance
        [LocalPresentationBus] environment_state:alerted
        [LocalPresentationBus] attention_applied:char_b
        [LocalPresentationBus] player_root_motion_step:char_c
        [LocalPresentationBus] patrol_root_motion_step:char_a
        [LocalPresentationBus] voice_stub_played
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-main.png:0
        """,
        focus_log="""
        [LocalPresentationBus] phase0_focus_autotest_begin
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-focus.png:0
        """,
        main_screenshot_exists=True,
        focus_screenshot_exists=True,
        interaction_source="world_result = esm_service.resolve_interaction(event, is_in_range=False)",
        esm_service_source="",
        voice_controller_source="""
        func play_stub_voice(_payload: Dictionary) -> void:
            _bus_log("voice_stub_played")
        """,
        player_bridge_source="""
        func before_player_shell_move(delta: float) -> void:
            _apply_player_root_motion_drive(delta)
        """,
        character_replica_source="""
        func consume_player_root_motion_request(delta: float) -> Vector3:
            return _consume_role_root_motion_world_delta()
        func get_locomotion_status() -> Dictionary:
            return {"stance": "stand", "gait": "walk", "jump_type": "none"}
        """,
    )

    results = _index_by_id(report["results"])

    assert results["locomotion_state_ui"]["status"] == "missing"


def test_phase0_audit_requires_jump_variant_probe_evidence() -> None:
    report = evaluate_phase0_audit(
        pytest_passed=True,
        scene_load_ok=True,
        main_log="""
        [LocalPresentationBus] backend_connected:ws://127.0.0.1:8010/ws
        [LocalPresentationBus] phase0_dialogue_target:char_a
        [LocalPresentationBus] dialogue_applied:char_a
        [LocalPresentationBus] phase0_interact_target:obj_letter
        [LocalPresentationBus] object_state:obj_letter:visible
        [LocalPresentationBus] constraint_state_result:distance
        [LocalPresentationBus] environment_state:alerted
        [LocalPresentationBus] attention_applied:char_b
        [LocalPresentationBus] player_root_motion_step:char_c
        [LocalPresentationBus] patrol_root_motion_step:char_a
        [LocalPresentationBus] voice_stub_played
        [LocalPresentationBus] locomotion_state:stance=stand gait=walk jump=none clip=walk_guard profile=walk rm=active
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-main.png:0
        """,
        focus_log="""
        [LocalPresentationBus] phase0_focus_autotest_begin
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-focus.png:0
        """,
        main_screenshot_exists=True,
        focus_screenshot_exists=True,
        interaction_source="world_result = esm_service.resolve_interaction(event, is_in_range=False)",
        esm_service_source="",
        voice_controller_source="""
        func play_stub_voice(_payload: Dictionary) -> void:
            _bus_log("voice_stub_played")
        """,
        player_bridge_source="""
        func trigger_forced_jump(jump_type: String) -> void:
            forced_jump_type = jump_type
        """,
        character_replica_source="""
        func get_locomotion_status() -> Dictionary:
            return {"jump_type": "two_foot"}
        """,
    )

    results = _index_by_id(report["results"])

    assert results["jump_variant_probes"]["status"] == "missing"


def test_phase0_audit_requires_forward_direction_probe_evidence() -> None:
    report = evaluate_phase0_audit(
        pytest_passed=True,
        scene_load_ok=True,
        main_log="""
        [LocalPresentationBus] backend_connected:ws://127.0.0.1:8010/ws
        [LocalPresentationBus] phase0_dialogue_target:char_a
        [LocalPresentationBus] dialogue_applied:char_a
        [LocalPresentationBus] phase0_interact_target:obj_letter
        [LocalPresentationBus] object_state:obj_letter:visible
        [LocalPresentationBus] constraint_state_result:distance
        [LocalPresentationBus] environment_state:alerted
        [LocalPresentationBus] attention_applied:char_b
        [LocalPresentationBus] player_root_motion_step:char_c
        [LocalPresentationBus] patrol_root_motion_step:char_a
        [LocalPresentationBus] voice_stub_played
        [LocalPresentationBus] locomotion_state:stance=stand gait=walk jump=none clip=walk_guard profile=walk rm=active
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-main.png:0
        """,
        focus_log="""
        [LocalPresentationBus] phase0_focus_autotest_begin
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-focus.png:0
        """,
        main_screenshot_exists=True,
        focus_screenshot_exists=True,
        interaction_source="world_result = esm_service.resolve_interaction(event, is_in_range=False)",
        esm_service_source="",
        voice_controller_source="""
        func play_stub_voice(_payload: Dictionary) -> void:
            _bus_log("voice_stub_played")
        """,
        player_bridge_source="""
        func _resolve_player_move_direction() -> Vector3:
            return Vector3(0.0, 0.0, -1.0)
        """,
        character_replica_source="""
        func consume_player_root_motion_request(delta: float) -> Vector3:
            return Vector3(0.0, 0.0, -0.1)
        """,
    )

    results = _index_by_id(report["results"])

    assert results["forward_direction_probe"]["status"] == "missing"


def test_phase1_slice_audit_requires_emitter_and_authority_lane_evidence() -> None:
    report = evaluate_phase1_slice_audit(
        main_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_object
        [LocalPresentationBus] phase0_visual_fact_emitter:spatial_relation:actor_near_object
        [LocalPresentationBus] phase0_visual_fact_emitter:light_level_drop:environment_light_drop
        [LocalPresentationBus] phase0_visual_fact_emitter:visual_evidence_projection:evidence_projection
        [LocalPresentationBus] phase0_auditory_fact_emitter:speaker_active:char_a:normal
        [LocalPresentationBus] phase0_auditory_fact_emitter:auditory_reachability_changed:char_a:clear
        [LocalPresentationBus] phase0_auditory_fact_emitter:ambient_noise_changed:quiet
        [LocalPresentationBus] phase0_role_state_fact_emitter:role_state_transition:speak
        [LocalPresentationBus] phase0_physiology_fact_emitter:breathing_strain_changed:elevated
        [LocalPresentationBus] phase0_tactile_fact_emitter:contact_started:light
        [LocalPresentationBus] phase0_thermal_fact_emitter:thermal_proximity_changed:warm
        [LocalPresentationBus] phase0_olfactory_fact_emitter:odor_state_changed:noticeable
        [LocalPresentationBus] phase0_ack:{"accepted":true,"route":"authority_visual_fact","source_type":"raw_fact_event"}
        [LocalPresentationBus] conversation_candidate_event:{"candidate_object_ids":["obj_letter"]}
        [LocalPresentationBus] character_runtime_state_delta:{"current_attention_source":"visual_fact"}
        [LocalPresentationBus] backend_message_type:siming_output
        """,
        focus_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_actor
        [LocalPresentationBus] phase0_ack:{"accepted":true,"route":"authority_visual_fact","source_type":"raw_fact_event"}
        """,
        direct_send_scan="""
        scripts/player/PlayerIntentMapper.gd:76:func emit_visual_fact_event(...)
        """,
        scene_text='[node name="VisualFactEmitter" type="Node" parent="."]',
        candidate_policy_source='AUDITORY_CANDIDATE_POLICY = "targeted_actor_only"',
    )

    results = _index_by_id(report["results"])

    assert report["overall_phase1_slice_passed"] is False
    assert results["emitter_scene_wired"]["status"] == "proved"
    assert results["no_direct_visual_fact_send_bypass"]["status"] == "proved"
    assert results["auditory_fact_observed"]["status"] == "missing"
    assert results["auditory_candidate_policy_explicit"]["status"] == "proved"
    assert results["role_state_fact_observed"]["status"] == "missing"
    assert results["physiology_fact_observed"]["status"] == "missing"
    assert results["tactile_fact_observed"]["status"] == "missing"
    assert results["thermal_fact_observed"]["status"] == "missing"
    assert results["olfactory_fact_observed"]["status"] == "missing"
    assert results["authority_ack_observed"]["status"] == "missing"
    assert results["environment_visual_fact_observed"]["status"] == "missing"
    assert results["evidence_projection_visual_fact_observed"]["status"] == "missing"


def test_phase1_slice_audit_names_executed_probe_scene() -> None:
    report = evaluate_phase1_slice_audit(
        main_log="",
        focus_log="",
        direct_send_scan="",
        scene_text='[node name="VisualFactEmitter" type="Node" parent="."]',
        scene_label="Phase1SliceRuntimeProbe",
    )

    results = _index_by_id(report["results"])

    assert results["emitter_scene_wired"]["status"] == "proved"
    assert "Phase1SliceRuntimeProbe" in results["emitter_scene_wired"]["title"]
    assert results["emitter_scene_wired"]["evidence"] == ["Phase1SliceRuntimeProbe VisualFactEmitter scene node"]


def test_phase1_slice_audit_rejects_plain_emitter_logs_mixed_with_raw_ack() -> None:
    report = evaluate_phase1_slice_audit(
        main_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_object
        [LocalPresentationBus] phase0_visual_fact_emitter:spatial_relation:actor_near_object
        [LocalPresentationBus] phase0_visual_fact_emitter:light_level_drop:environment_light_drop
        [LocalPresentationBus] phase0_visual_fact_emitter:visual_evidence_projection:evidence_projection
        [LocalPresentationBus] phase0_auditory_fact_emitter:speaker_active:char_a:normal
        [LocalPresentationBus] phase0_auditory_fact_emitter:auditory_reachability_changed:char_a:clear
        [LocalPresentationBus] phase0_auditory_fact_emitter:ambient_noise_changed:quiet
        [LocalPresentationBus] phase0_role_state_fact_emitter:role_state_transition:speak
        [LocalPresentationBus] phase0_physiology_fact_emitter:breathing_strain_changed:elevated
        [LocalPresentationBus] phase0_tactile_fact_emitter:contact_started:light
        [LocalPresentationBus] phase0_thermal_fact_emitter:thermal_proximity_changed:warm
        [LocalPresentationBus] phase0_olfactory_fact_emitter:odor_state_changed:noticeable
        [LocalPresentationBus] phase0_ack:{"accepted":true,"route":"authority_visual_fact","source_type":"raw_fact_event"}
        [LocalPresentationBus] conversation_candidate_event:{"candidate_object_ids":["obj_letter"]}
        [LocalPresentationBus] character_runtime_state_delta:{"current_attention_source":"visual_fact"}
        [LocalPresentationBus] backend_message_type:siming_output
        """,
        focus_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_actor
        [LocalPresentationBus] phase0_ack:{"accepted":true,"route":"authority_visual_fact","source_type":"raw_fact_event"}
        """,
        direct_send_scan="",
        scene_text='[node name="VisualFactEmitter" type="Node" parent="."]',
        candidate_policy_source='AUDITORY_CANDIDATE_POLICY = "targeted_actor_only"',
    )

    results = _index_by_id(report["results"])

    assert report["overall_phase1_slice_passed"] is False
    assert results["authority_ack_observed"]["status"] == "missing"
    assert results["object_visual_fact_observed"]["status"] == "missing"
    assert results["actor_visual_fact_observed"]["status"] == "missing"
    assert results["auditory_fact_observed"]["status"] == "missing"


def test_phase1_slice_audit_accepts_probe_summary_lines() -> None:
    report = evaluate_phase1_slice_audit(
        main_log=(
            'phase1_slice_runtime_probe:main:acks={"authority_auditory_fact":3,'
            '"authority_olfactory_fact":1,"authority_physiology_fact":1,'
            '"authority_role_state_fact":1,"authority_tactile_fact":1,'
            '"authority_thermal_fact":1,"authority_visual_fact":4} '
            'sources={"authority_auditory_fact":{"raw_fact_event":3},'
            '"authority_olfactory_fact":{"raw_fact_event":1},'
            '"authority_physiology_fact":{"raw_fact_event":1},'
            '"authority_role_state_fact":{"raw_fact_event":1},'
            '"authority_tactile_fact":{"raw_fact_event":1},'
            '"authority_thermal_fact":{"raw_fact_event":1},'
            '"authority_visual_fact":{"raw_fact_event":4}} '
            'facts={"authority_auditory_fact":{"raw_fact_event":["speaker_active",'
            '"auditory_reachability_changed","ambient_noise_changed"]},'
            '"authority_olfactory_fact":{"raw_fact_event":["odor_state_changed"]},'
            '"authority_physiology_fact":{"raw_fact_event":["breathing_strain_changed"]},'
            '"authority_role_state_fact":{"raw_fact_event":["role_state_transition"]},'
            '"authority_tactile_fact":{"raw_fact_event":["contact_started"]},'
            '"authority_thermal_fact":{"raw_fact_event":["thermal_proximity_changed"]},'
            '"authority_visual_fact":{"raw_fact_event":["actor_looks_at_object","actor_near_object",'
            '"environment_light_drop","evidence_projection"]}} '
            "deltas=5 candidates=2 siming=3 run=phase1-slice-main"
        ),
        focus_log=(
            'phase1_slice_runtime_probe:focus:acks={"authority_visual_fact":1} '
            'sources={"authority_visual_fact":{"raw_fact_event":1}} '
            'facts={"authority_visual_fact":{"raw_fact_event":["actor_looks_at_actor"]}} '
            "deltas=2 candidates=1 siming=1 run=phase1-slice-focus"
        ),
        direct_send_scan="",
        scene_text='[node name="VisualFactEmitter" type="Node" parent="."]',
        candidate_policy_source='AUDITORY_CANDIDATE_POLICY = "targeted_actor_only"',
    )

    results = _index_by_id(report["results"])

    assert report["overall_phase1_slice_passed"] is True
    assert results["object_visual_fact_observed"]["status"] == "proved"
    assert results["actor_visual_fact_observed"]["status"] == "proved"
    assert results["near_object_visual_fact_observed"]["status"] == "proved"
    assert results["environment_visual_fact_observed"]["status"] == "proved"
    assert results["evidence_projection_visual_fact_observed"]["status"] == "proved"
    assert results["auditory_fact_observed"]["status"] == "proved"
    assert results["role_state_fact_observed"]["status"] == "proved"
    assert results["physiology_fact_observed"]["status"] == "proved"
    assert results["tactile_fact_observed"]["status"] == "proved"
    assert results["thermal_fact_observed"]["status"] == "proved"
    assert results["olfactory_fact_observed"]["status"] == "proved"
    assert results["authority_ack_observed"]["status"] == "proved"
    assert results["runtime_projection_observed"]["status"] == "proved"
    assert results["candidate_and_siming_observed"]["status"] == "proved"


def test_phase1_slice_audit_rejects_aggregate_probe_summary_without_fact_details() -> None:
    report = evaluate_phase1_slice_audit(
        main_log=(
            'phase1_slice_runtime_probe:main:acks={"authority_auditory_fact":3,'
            '"authority_olfactory_fact":1,"authority_physiology_fact":1,'
            '"authority_role_state_fact":1,"authority_tactile_fact":1,'
            '"authority_thermal_fact":1,"authority_visual_fact":4} '
            "deltas=5 candidates=2 siming=3 run=phase1-slice-main"
        ),
        focus_log=(
            'phase1_slice_runtime_probe:focus:acks={"authority_visual_fact":1} '
            "deltas=2 candidates=1 siming=1 run=phase1-slice-focus"
        ),
        direct_send_scan="",
        scene_text='[node name="VisualFactEmitter" type="Node" parent="."]',
        candidate_policy_source='AUDITORY_CANDIDATE_POLICY = "targeted_actor_only"',
    )

    results = _index_by_id(report["results"])

    assert report["overall_phase1_slice_passed"] is False
    assert results["object_visual_fact_observed"]["status"] == "missing"
    assert results["actor_visual_fact_observed"]["status"] == "missing"
    assert results["near_object_visual_fact_observed"]["status"] == "missing"
    assert results["environment_visual_fact_observed"]["status"] == "missing"
    assert results["evidence_projection_visual_fact_observed"]["status"] == "missing"
    assert results["auditory_fact_observed"]["status"] == "missing"
    assert results["authority_ack_observed"]["status"] == "missing"
    assert results["runtime_projection_observed"]["status"] == "proved"
    assert results["candidate_and_siming_observed"]["status"] == "proved"


def test_phase1_slice_audit_rejects_probe_summary_without_raw_fact_ack_source() -> None:
    report = evaluate_phase1_slice_audit(
        main_log=(
            'phase1_slice_runtime_probe:main:acks={"authority_visual_fact":4} '
            'sources={"authority_visual_fact":{"visual_fact_event":4}} '
            'facts={"authority_visual_fact":{"visual_fact_event":["actor_looks_at_object","actor_near_object",'
            '"environment_light_drop","evidence_projection"]}} '
            "deltas=5 candidates=2 siming=3 run=phase1-slice-main"
        ),
        focus_log=(
            'phase1_slice_runtime_probe:focus:acks={"authority_visual_fact":1} '
            'sources={"authority_visual_fact":{"visual_fact_event":1}} '
            'facts={"authority_visual_fact":{"visual_fact_event":["actor_looks_at_actor"]}} '
            "deltas=2 candidates=1 siming=1 run=phase1-slice-focus"
        ),
        direct_send_scan="",
        scene_text='[node name="VisualFactEmitter" type="Node" parent="."]',
        candidate_policy_source='AUDITORY_CANDIDATE_POLICY = "targeted_actor_only"',
    )

    results = _index_by_id(report["results"])

    assert results["object_visual_fact_observed"]["status"] == "missing"
    assert results["actor_visual_fact_observed"]["status"] == "missing"
    assert results["authority_ack_observed"]["status"] == "missing"
    assert report["overall_phase1_slice_passed"] is False


def test_phase1_slice_audit_rejects_mixed_source_probe_fact_summary() -> None:
    report = evaluate_phase1_slice_audit(
        main_log=(
            'phase1_slice_runtime_probe:main:acks={"authority_visual_fact":8} '
            'sources={"authority_visual_fact":{"raw_fact_event":4,"visual_fact_event":4}} '
            'facts={"authority_visual_fact":{"visual_fact_event":["actor_looks_at_object",'
            '"actor_near_object","environment_light_drop","evidence_projection"]}} '
            "deltas=5 candidates=2 siming=3 run=phase1-slice-main"
        ),
        focus_log=(
            'phase1_slice_runtime_probe:focus:acks={"authority_visual_fact":2} '
            'sources={"authority_visual_fact":{"raw_fact_event":1,"visual_fact_event":1}} '
            'facts={"authority_visual_fact":{"visual_fact_event":["actor_looks_at_actor"]}} '
            "deltas=2 candidates=1 siming=1 run=phase1-slice-focus"
        ),
        direct_send_scan="",
        scene_text='[node name="VisualFactEmitter" type="Node" parent="."]',
        candidate_policy_source='AUDITORY_CANDIDATE_POLICY = "targeted_actor_only"',
    )

    results = _index_by_id(report["results"])

    assert results["authority_ack_observed"]["status"] == "proved"
    assert results["object_visual_fact_observed"]["status"] == "missing"
    assert results["actor_visual_fact_observed"]["status"] == "missing"
    assert report["overall_phase1_slice_passed"] is False


def test_phase1_slice_audit_rejects_legacy_visual_fact_event_ack_contract() -> None:
    report = evaluate_phase1_slice_audit(
        main_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_object
        [LocalPresentationBus] phase0_visual_fact_emitter:spatial_relation:actor_near_object
        [LocalPresentationBus] phase0_visual_fact_emitter:light_level_drop:environment_light_drop
        [LocalPresentationBus] phase0_visual_fact_emitter:visual_evidence_projection:evidence_projection
        [LocalPresentationBus] phase0_auditory_fact_emitter:speaker_active:char_a:normal
        [LocalPresentationBus] phase0_auditory_fact_emitter:auditory_reachability_changed:char_a:clear
        [LocalPresentationBus] phase0_auditory_fact_emitter:ambient_noise_changed:quiet
        [LocalPresentationBus] phase0_role_state_fact_emitter:role_state_transition:speak
        [LocalPresentationBus] phase0_physiology_fact_emitter:breathing_strain_changed:elevated
        [LocalPresentationBus] phase0_tactile_fact_emitter:contact_started:light
        [LocalPresentationBus] phase0_thermal_fact_emitter:thermal_proximity_changed:warm
        [LocalPresentationBus] phase0_olfactory_fact_emitter:odor_state_changed:noticeable
        [LocalPresentationBus] phase0_ack:{"accepted":true,"route":"authority_visual_fact","source_type":"visual_fact_event"}
        [LocalPresentationBus] conversation_candidate_event:{"candidate_object_ids":["obj_letter"]}
        [LocalPresentationBus] character_runtime_state_delta:{"current_attention_source":"visual_fact"}
        [LocalPresentationBus] backend_message_type:siming_output
        """,
        focus_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_actor
        [LocalPresentationBus] phase0_ack:{"accepted":true,"route":"authority_visual_fact","source_type":"visual_fact_event"}
        """,
        direct_send_scan="""
        scripts/player/PlayerIntentMapper.gd:76:func emit_visual_fact_event(...)
        """,
        scene_text='[node name="VisualFactEmitter" type="Node" parent="."]',
        candidate_policy_source='AUDITORY_CANDIDATE_POLICY = "targeted_actor_only"',
    )

    results = _index_by_id(report["results"])

    assert report["overall_phase1_slice_passed"] is False
    assert results["authority_ack_observed"]["status"] == "missing"
    assert results["environment_visual_fact_observed"]["status"] == "missing"
    assert results["evidence_projection_visual_fact_observed"]["status"] == "missing"


def test_phase1_slice_audit_requires_auditory_fact_proof() -> None:
    report = evaluate_phase1_slice_audit(
        main_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_object
        [LocalPresentationBus] phase0_visual_fact_emitter:spatial_relation:actor_near_object
        [LocalPresentationBus] phase0_visual_fact_emitter:light_level_drop:environment_light_drop
        [LocalPresentationBus] phase0_visual_fact_emitter:visual_evidence_projection:evidence_projection
        [LocalPresentationBus] phase0_ack:{"accepted":true,"route":"authority_visual_fact","source_type":"raw_fact_event"}
        [LocalPresentationBus] conversation_candidate_event:{"candidate_object_ids":["obj_letter"]}
        [LocalPresentationBus] character_runtime_state_delta:{"current_attention_source":"visual_fact"}
        [LocalPresentationBus] backend_message_type:siming_output
        """,
        focus_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_actor
        [LocalPresentationBus] phase0_ack:{"accepted":true,"route":"authority_visual_fact","source_type":"raw_fact_event"}
        """,
        direct_send_scan="""
        scripts/player/PlayerIntentMapper.gd:76:func emit_visual_fact_event(...)
        """,
        scene_text='[node name="VisualFactEmitter" type="Node" parent="."]',
        candidate_policy_source='AUDITORY_CANDIDATE_POLICY = "targeted_actor_only"',
    )

    results = _index_by_id(report["results"])

    assert report["overall_phase1_slice_passed"] is False
    assert results["auditory_fact_observed"]["status"] == "missing"


def test_phase1_slice_audit_requires_evidence_projection_visual_fact_proof() -> None:
    report = evaluate_phase1_slice_audit(
        main_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_object
        [LocalPresentationBus] phase0_visual_fact_emitter:spatial_relation:actor_near_object
        [LocalPresentationBus] phase0_visual_fact_emitter:light_level_drop:environment_light_drop
        [LocalPresentationBus] phase0_auditory_fact_emitter:speaker_active:char_a:normal
        [LocalPresentationBus] phase0_auditory_fact_emitter:auditory_reachability_changed:char_a:clear
        [LocalPresentationBus] phase0_auditory_fact_emitter:ambient_noise_changed:quiet
        [LocalPresentationBus] phase0_role_state_fact_emitter:role_state_transition:speak
        [LocalPresentationBus] phase0_physiology_fact_emitter:breathing_strain_changed:elevated
        [LocalPresentationBus] phase0_tactile_fact_emitter:contact_started:light
        [LocalPresentationBus] phase0_thermal_fact_emitter:thermal_proximity_changed:warm
        [LocalPresentationBus] phase0_olfactory_fact_emitter:odor_state_changed:noticeable
        [LocalPresentationBus] phase0_ack:{"accepted":true,"route":"authority_visual_fact","source_type":"raw_fact_event"}
        [LocalPresentationBus] conversation_candidate_event:{"candidate_object_ids":["obj_letter"]}
        [LocalPresentationBus] character_runtime_state_delta:{"current_attention_source":"visual_fact"}
        [LocalPresentationBus] backend_message_type:siming_output
        """,
        focus_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_actor
        [LocalPresentationBus] phase0_ack:{"accepted":true,"route":"authority_visual_fact","source_type":"raw_fact_event"}
        """,
        direct_send_scan="""
        scripts/player/PlayerIntentMapper.gd:76:func emit_visual_fact_event(...)
        """,
        scene_text='[node name="VisualFactEmitter" type="Node" parent="."]',
        candidate_policy_source='AUDITORY_CANDIDATE_POLICY = "targeted_actor_only"',
    )

    results = _index_by_id(report["results"])

    assert report["overall_phase1_slice_passed"] is False
    assert results["evidence_projection_visual_fact_observed"]["status"] == "missing"


def test_phase1_slice_audit_requires_explicit_auditory_candidate_policy() -> None:
    report = evaluate_phase1_slice_audit(
        main_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_object
        [LocalPresentationBus] phase0_visual_fact_emitter:spatial_relation:actor_near_object
        [LocalPresentationBus] phase0_visual_fact_emitter:light_level_drop:environment_light_drop
        [LocalPresentationBus] phase0_visual_fact_emitter:visual_evidence_projection:evidence_projection
        [LocalPresentationBus] phase0_auditory_fact_emitter:speaker_active:char_a:normal
        [LocalPresentationBus] phase0_auditory_fact_emitter:auditory_reachability_changed:char_a:clear
        [LocalPresentationBus] phase0_auditory_fact_emitter:ambient_noise_changed:quiet
        [LocalPresentationBus] phase0_role_state_fact_emitter:role_state_transition:speak
        [LocalPresentationBus] phase0_physiology_fact_emitter:breathing_strain_changed:elevated
        [LocalPresentationBus] phase0_tactile_fact_emitter:contact_started:light
        [LocalPresentationBus] phase0_thermal_fact_emitter:thermal_proximity_changed:warm
        [LocalPresentationBus] phase0_olfactory_fact_emitter:odor_state_changed:noticeable
        [LocalPresentationBus] phase0_ack:{"accepted":true,"route":"authority_visual_fact","source_type":"raw_fact_event"}
        [LocalPresentationBus] conversation_candidate_event:{"candidate_object_ids":["obj_letter"]}
        [LocalPresentationBus] character_runtime_state_delta:{"current_attention_source":"visual_fact"}
        [LocalPresentationBus] backend_message_type:siming_output
        """,
        focus_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_actor
        [LocalPresentationBus] phase0_ack:{"accepted":true,"route":"authority_visual_fact","source_type":"raw_fact_event"}
        """,
        direct_send_scan="""
        scripts/player/PlayerIntentMapper.gd:76:func emit_visual_fact_event(...)
        """,
        scene_text='[node name="VisualFactEmitter" type="Node" parent="."]',
        candidate_policy_source="",
    )

    results = _index_by_id(report["results"])

    assert report["overall_phase1_slice_passed"] is False
    assert results["auditory_candidate_policy_explicit"]["status"] == "missing"


def test_phase1_slice_audit_requires_role_state_fact_proof() -> None:
    report = evaluate_phase1_slice_audit(
        main_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_object
        [LocalPresentationBus] phase0_visual_fact_emitter:spatial_relation:actor_near_object
        [LocalPresentationBus] phase0_visual_fact_emitter:light_level_drop:environment_light_drop
        [LocalPresentationBus] phase0_auditory_fact_emitter:speaker_active:char_a:normal
        [LocalPresentationBus] phase0_ack:{"accepted":true,"route":"authority_visual_fact","source_type":"raw_fact_event"}
        [LocalPresentationBus] conversation_candidate_event:{"candidate_object_ids":["obj_letter"]}
        [LocalPresentationBus] character_runtime_state_delta:{"current_attention_source":"visual_fact"}
        [LocalPresentationBus] backend_message_type:siming_output
        """,
        focus_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_actor
        [LocalPresentationBus] phase0_ack:{"accepted":true,"route":"authority_visual_fact","source_type":"raw_fact_event"}
        """,
        direct_send_scan="""
        scripts/player/PlayerIntentMapper.gd:76:func emit_visual_fact_event(...)
        """,
        scene_text='[node name="VisualFactEmitter" type="Node" parent="."]',
    )

    results = _index_by_id(report["results"])

    assert report["overall_phase1_slice_passed"] is False
    assert results["role_state_fact_observed"]["status"] == "missing"


def test_phase1_slice_audit_requires_physiology_fact_proof() -> None:
    report = evaluate_phase1_slice_audit(
        main_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_object
        [LocalPresentationBus] phase0_visual_fact_emitter:spatial_relation:actor_near_object
        [LocalPresentationBus] phase0_visual_fact_emitter:light_level_drop:environment_light_drop
        [LocalPresentationBus] phase0_auditory_fact_emitter:speaker_active:char_a:normal
        [LocalPresentationBus] phase0_role_state_fact_emitter:role_state_transition:speak
        [LocalPresentationBus] phase0_ack:{"accepted":true,"route":"authority_visual_fact","source_type":"raw_fact_event"}
        [LocalPresentationBus] conversation_candidate_event:{"candidate_object_ids":["obj_letter"]}
        [LocalPresentationBus] character_runtime_state_delta:{"current_attention_source":"visual_fact"}
        [LocalPresentationBus] backend_message_type:siming_output
        """,
        focus_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_actor
        [LocalPresentationBus] phase0_ack:{"accepted":true,"route":"authority_visual_fact","source_type":"raw_fact_event"}
        """,
        direct_send_scan="""
        scripts/player/PlayerIntentMapper.gd:76:func emit_visual_fact_event(...)
        """,
        scene_text='[node name="VisualFactEmitter" type="Node" parent="."]',
    )

    results = _index_by_id(report["results"])

    assert report["overall_phase1_slice_passed"] is False
    assert results["physiology_fact_observed"]["status"] == "missing"


def test_phase1_slice_audit_requires_remaining_sensory_fact_proofs() -> None:
    report = evaluate_phase1_slice_audit(
        main_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_object
        [LocalPresentationBus] phase0_visual_fact_emitter:spatial_relation:actor_near_object
        [LocalPresentationBus] phase0_visual_fact_emitter:light_level_drop:environment_light_drop
        [LocalPresentationBus] phase0_auditory_fact_emitter:speaker_active:char_a:normal
        [LocalPresentationBus] phase0_role_state_fact_emitter:role_state_transition:speak
        [LocalPresentationBus] phase0_physiology_fact_emitter:breathing_strain_changed:elevated
        [LocalPresentationBus] phase0_ack:{"accepted":true,"route":"authority_visual_fact","source_type":"raw_fact_event"}
        [LocalPresentationBus] conversation_candidate_event:{"candidate_object_ids":["obj_letter"]}
        [LocalPresentationBus] character_runtime_state_delta:{"current_attention_source":"visual_fact"}
        [LocalPresentationBus] backend_message_type:siming_output
        """,
        focus_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_actor
        [LocalPresentationBus] phase0_ack:{"accepted":true,"route":"authority_visual_fact","source_type":"raw_fact_event"}
        """,
        direct_send_scan="""
        scripts/player/PlayerIntentMapper.gd:76:func emit_visual_fact_event(...)
        """,
        scene_text='[node name="VisualFactEmitter" type="Node" parent="."]',
    )

    results = _index_by_id(report["results"])

    assert report["overall_phase1_slice_passed"] is False
    assert results["tactile_fact_observed"]["status"] == "missing"
    assert results["thermal_fact_observed"]["status"] == "missing"
    assert results["olfactory_fact_observed"]["status"] == "missing"


def test_scan_direct_visual_fact_bypass_allows_shared_raw_emitter_only(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    allowed_dir = project_root / "scripts" / "l1" / "facts"
    rogue_dir = project_root / "scripts" / "rogue"
    visual_dir = project_root / "scripts" / "visual"
    player_dir = project_root / "scripts" / "player"

    allowed_dir.mkdir(parents=True)
    rogue_dir.mkdir(parents=True)
    visual_dir.mkdir(parents=True)
    player_dir.mkdir(parents=True)

    (allowed_dir / "RawFactEmitter.gd").write_text(
        """
extends RefCounted

func emit_raw_fact(payload: Dictionary) -> bool:
    var envelope := {"message_type": "raw_fact_event", "payload": payload}
    return bridge.send_envelope(envelope) == OK
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (visual_dir / "VisualFactEmitter.gd").write_text(
        """
extends Node

func emit_visual_fact() -> bool:
    return raw_fact_emitter.emit_raw_fact(_build_visual_fact_payload())

func _build_visual_fact_payload() -> Dictionary:
    return {"fact_family": "visual_fact", "event_type": "raw_fact_event"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (player_dir / "PlayerIntentMapper.gd").write_text(
        """
extends Node

func emit_visual_fact_event(...) -> Dictionary:
    return {}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (rogue_dir / "RogueEmitter.gd").write_text(
        """
extends Node

func bypass(payload: Dictionary) -> bool:
    var envelope := {"message_type": "raw_fact_event", "payload": payload}
    return bridge.send_envelope(envelope) == OK
""".strip()
        + "\n",
        encoding="utf-8",
    )

    scan = scan_direct_visual_fact_bypass(project_root)

    assert "scripts/l1/facts/RawFactEmitter.gd" not in scan
    assert "scripts/visual/VisualFactEmitter.gd" not in scan
    assert "scripts/rogue/RogueEmitter.gd:direct-visual-fact-send" in scan


def test_shared_raw_fact_transport_uses_raw_fact_event_visual_fact_shape() -> None:
    project_root = Path(__file__).resolve().parents[2]
    builder_source = (project_root / "scripts" / "l1" / "facts" / "FactEnvelopeBuilder.gd").read_text(
        encoding="utf-8"
    )
    raw_emitter_source = (project_root / "scripts" / "l1" / "facts" / "RawFactEmitter.gd").read_text(
        encoding="utf-8"
    )
    visual_emitter_source = (project_root / "scripts" / "visual" / "VisualFactEmitter.gd").read_text(
        encoding="utf-8"
    )

    assert '"message_type": "raw_fact_event"' in builder_source
    assert '"event_type": "raw_fact_event"' in builder_source
    assert '"fact_family": fact_family' in builder_source
    assert "build_raw_fact_envelope" in builder_source
    assert "build_raw_fact_payload" in builder_source
    assert "build_visual_fact_payload" not in builder_source
    assert "func emit_raw_fact(" in raw_emitter_source
    assert "build_raw_fact_envelope(payload)" in raw_emitter_source
    assert '"message_type": "visual_fact_event"' not in visual_emitter_source
    assert "_build_visual_fact_payload" in visual_emitter_source
    assert '"visual_fact"' in visual_emitter_source


def test_shared_raw_fact_transport_supports_effect_semantics_fields() -> None:
    project_root = Path(__file__).resolve().parents[2]
    builder_source = (project_root / "scripts" / "l1" / "facts" / "FactEnvelopeBuilder.gd").read_text(
        encoding="utf-8"
    )

    assert '"effect_kind"' in builder_source
    assert '"subject_key"' in builder_source
    assert '"ttl_ms"' in builder_source


def test_environment_visual_fact_emitter_uses_environment_state_subject_key() -> None:
    project_root = Path(__file__).resolve().parents[2]
    emitter_source = (
        project_root / "scripts" / "l1" / "facts" / "emitters" / "EnvironmentVisualFactEmitter.gd"
    ).read_text(encoding="utf-8")

    assert '"environment_state/%s" % environment_id' in emitter_source


def test_visual_fact_system_contains_object_visual_fact_emitter() -> None:
    project_root = Path(__file__).resolve().parents[2]
    emitter_source = (
        project_root / "scripts" / "l1" / "facts" / "emitters" / "ObjectVisualFactEmitter.gd"
    ).read_text(encoding="utf-8")

    assert "emit_object_state_transition" in emitter_source


def test_visual_fact_system_contains_spatial_relation_visual_fact_emitter() -> None:
    project_root = Path(__file__).resolve().parents[2]
    emitter_source = (
        project_root / "scripts" / "l1" / "facts" / "emitters" / "SpatialRelationVisualFactEmitter.gd"
    ).read_text(encoding="utf-8")

    assert "emit_spatial_relation_fact" in emitter_source


def test_visual_fact_system_contains_evidence_projection_emitter() -> None:
    project_root = Path(__file__).resolve().parents[2]
    emitter_source = (
        project_root / "scripts" / "l1" / "facts" / "emitters" / "EvidenceProjectionEmitter.gd"
    ).read_text(encoding="utf-8")

    assert "emit_visual_evidence_projection" in emitter_source


def test_main_demo_runtime_wires_evidence_projection_emitter() -> None:
    project_root = Path(__file__).resolve().parents[2]
    controller_source = (project_root / "scripts" / "phase0" / "MainDemoController.gd").read_text(
        encoding="utf-8"
    )
    scene_source = (project_root / "scenes" / "phase0" / "MainDemo.tscn").read_text(
        encoding="utf-8"
    )

    assert "evidence_projection_emitter" in controller_source
    assert "emit_visual_evidence_projection" in controller_source
    assert 'node name="EvidenceProjectionEmitter" type="Node" parent="VisualFactEmitter"' in scene_source


def test_system_l1_contains_auditory_fact_emitter() -> None:
    project_root = Path(__file__).resolve().parents[2]
    emitter_source = (
        project_root / "scripts" / "l1" / "facts" / "emitters" / "AuditoryFactEmitter.gd"
    ).read_text(encoding="utf-8")

    assert "emit_speaker_active" in emitter_source


def test_client_interaction_outputs_are_normalized_in_main_demo_controller() -> None:
    project_root = Path(__file__).resolve().parents[2]
    controller_source = (
        project_root / "scripts" / "phase0" / "MainDemoController.gd"
    ).read_text(encoding="utf-8")
    backend_main_source = (
        project_root / "backend" / "app" / "main.py"
    ).read_text(encoding="utf-8")

    assert "func _emit_dialogue_request(" in controller_source
    assert "func _emit_interaction_request(" in controller_source
    assert "func _emit_move_intent_request(" in controller_source
    assert "phase0_move_target:" in controller_source
    assert 'route["route"] == "local_motion"' in backend_main_source
    assert "MoveIntent" in backend_main_source
    assert "_ensure_runtime_snapshot_messages(event)" in backend_main_source


def test_system_l1_contains_tactile_fact_emitter() -> None:
    project_root = Path(__file__).resolve().parents[2]
    emitter_source = (
        project_root / "scripts" / "l1" / "facts" / "emitters" / "TactileFactEmitter.gd"
    ).read_text(encoding="utf-8")

    assert "emit_contact_fact" in emitter_source


def test_system_l1_contains_thermal_fact_emitter() -> None:
    project_root = Path(__file__).resolve().parents[2]
    emitter_source = (
        project_root / "scripts" / "l1" / "facts" / "emitters" / "ThermalFactEmitter.gd"
    ).read_text(encoding="utf-8")

    assert "emit_thermal_proximity_fact" in emitter_source


def test_system_l1_contains_olfactory_fact_emitter() -> None:
    project_root = Path(__file__).resolve().parents[2]
    emitter_source = (
        project_root / "scripts" / "l1" / "facts" / "emitters" / "OlfactoryFactEmitter.gd"
    ).read_text(encoding="utf-8")

    assert "emit_odor_state_fact" in emitter_source


def test_system_l1_contains_physiology_state_fact_emitter() -> None:
    project_root = Path(__file__).resolve().parents[2]
    emitter_source = (
        project_root / "scripts" / "l1" / "facts" / "emitters" / "PhysiologyStateFactEmitter.gd"
    ).read_text(encoding="utf-8")

    assert "emit_breathing_strain_fact" in emitter_source


def test_system_l1_contains_role_state_fact_emitter() -> None:
    project_root = Path(__file__).resolve().parents[2]
    emitter_source = (
        project_root / "scripts" / "l1" / "facts" / "emitters" / "RoleStateFactEmitter.gd"
    ).read_text(encoding="utf-8")

    assert "emit_role_state_transition" in emitter_source


def test_character_replica_runtime_wires_role_state_fact_emitter() -> None:
    project_root = Path(__file__).resolve().parents[2]
    character_source = (project_root / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )
    scene_source = (project_root / "scenes" / "phase0" / "CharacterReplica.tscn").read_text(
        encoding="utf-8"
    )

    assert 'role_state_fact_emitter_path := NodePath("RoleStateFactEmitter")' in character_source
    assert "_emit_role_state_fact(" in character_source
    assert 'node name="RoleStateFactEmitter" type="Node" parent="."' in scene_source


def test_character_replica_runtime_wires_physiology_state_fact_emitter() -> None:
    project_root = Path(__file__).resolve().parents[2]
    character_source = (project_root / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )
    scene_source = (project_root / "scenes" / "phase0" / "CharacterReplica.tscn").read_text(
        encoding="utf-8"
    )

    assert 'physiology_state_fact_emitter_path := NodePath("PhysiologyStateFactEmitter")' in character_source
    assert "_emit_physiology_state_fact(" in character_source
    assert 'node name="PhysiologyStateFactEmitter" type="Node" parent="."' in scene_source


def test_main_demo_runtime_wires_remaining_sensory_emitters() -> None:
    project_root = Path(__file__).resolve().parents[2]
    controller_source = (project_root / "scripts" / "phase0" / "MainDemoController.gd").read_text(
        encoding="utf-8"
    )
    scene_source = (project_root / "scenes" / "phase0" / "MainDemo.tscn").read_text(
        encoding="utf-8"
    )

    assert "tactile_fact_emitter" in controller_source
    assert "thermal_fact_emitter" in controller_source
    assert "olfactory_fact_emitter" in controller_source
    assert "_on_world_result_received(payload: Dictionary)" in controller_source
    assert 'var result_type := str(payload.get("result_type", ""))' in controller_source
    assert 'str(payload.get("target_object_id", "")) == "obj_letter"' in controller_source
    assert 'str(payload.get("target_environment_id", "")) == "env_lamp"' in controller_source
    assert 'node name="TactileFactEmitter" type="Node" parent="VisualFactEmitter"' in scene_source
    assert 'node name="ThermalFactEmitter" type="Node" parent="VisualFactEmitter"' in scene_source
    assert 'node name="OlfactoryFactEmitter" type="Node" parent="VisualFactEmitter"' in scene_source


def test_backend_bridge_exposes_backend_disconnected_signal_chain() -> None:
    project_root = Path(__file__).resolve().parents[2]
    bus_source = (project_root / "scripts" / "autoload" / "LocalPresentationBus.gd").read_text(
        encoding="utf-8"
    )
    bridge_source = (project_root / "scripts" / "autoload" / "BackendBridge.gd").read_text(
        encoding="utf-8"
    )

    assert 'signal backend_disconnected(code)' in bus_source
    assert '_bus_emit("backend_disconnected", [ws.get_close_code()])' in bridge_source


def test_backend_bridge_marks_connect_request_as_connecting_before_poll_short_circuit() -> None:
    project_root = Path(__file__).resolve().parents[2]
    bridge_source = (project_root / "scripts" / "autoload" / "BackendBridge.gd").read_text(
        encoding="utf-8"
    )
    connect_section = bridge_source.split("func connect_to_backend(url: String) -> int:", 1)[1].split(
        "func send_envelope", 1
    )[0]

    assert "last_ready_state = WebSocketPeer.STATE_CONNECTING" in connect_section


def test_main_demo_controller_reconnects_and_replays_pending_phase0_requests() -> None:
    project_root = Path(__file__).resolve().parents[2]
    controller_source = (project_root / "scripts" / "phase0" / "MainDemoController.gd").read_text(
        encoding="utf-8"
    )

    assert "var pending_backend_reconnect := false" in controller_source
    assert 'var pending_dialogue_request: Dictionary = {}' in controller_source
    assert 'var pending_interaction_request: Dictionary = {}' in controller_source
    assert 'var pending_move_request: Dictionary = {}' in controller_source
    assert "func _request_backend_reconnect() -> void:" in controller_source
    assert "func _flush_pending_backend_requests() -> void:" in controller_source
    assert "pending_backend_reconnect = true" in controller_source
    assert "_request_backend_reconnect()" in controller_source
    assert "_flush_pending_backend_requests()" in controller_source
    assert 'pending_dialogue_request = {"target_actor_id": target_actor_id, "content": content}' in controller_source
    assert 'pending_interaction_request = {"target_object_id": target_object_id, "interaction_type": interaction_type}' in controller_source
    assert 'pending_move_request = {"target_point": target_point, "move_mode": move_mode}' in controller_source


def test_backend_bridge_exposes_action_request_and_state_machine_transition_signal_chain() -> None:
    project_root = Path(__file__).resolve().parents[2]
    bus_source = (project_root / "scripts" / "autoload" / "LocalPresentationBus.gd").read_text(
        encoding="utf-8"
    )
    bridge_source = (project_root / "scripts" / "autoload" / "BackendBridge.gd").read_text(
        encoding="utf-8"
    )

    assert 'signal action_request_received(payload)' in bus_source
    assert 'signal state_machine_transition_received(payload)' in bus_source
    assert '_bus_log("action_request:%s" % JSON.stringify(payload))' in bridge_source
    assert '_bus_emit("action_request_received", [payload])' in bridge_source
    assert '_bus_log("state_machine_transition:%s" % JSON.stringify(payload))' in bridge_source
    assert '_bus_emit("state_machine_transition_received", [payload])' in bridge_source


def test_backend_bridge_exposes_character_agent_output_signal_chain() -> None:
    project_root = Path(__file__).resolve().parents[2]
    bus_source = (project_root / "scripts" / "autoload" / "LocalPresentationBus.gd").read_text(
        encoding="utf-8"
    )
    bridge_source = (project_root / "scripts" / "autoload" / "BackendBridge.gd").read_text(
        encoding="utf-8"
    )
    character_source = (project_root / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )

    assert 'signal character_agent_output_received(payload)' in bus_source
    assert '"character_agent_output":' in bridge_source
    assert '_bus_emit("character_agent_output_received", [payload])' in bridge_source
    assert 'character_agent_output_received.connect(_on_character_agent_output_received)' not in character_source
    assert 'func _on_character_agent_output_received(payload: Dictionary) -> void:' not in character_source

def test_backend_bridge_polls_before_closed_state_early_return() -> None:
    project_root = Path(__file__).resolve().parents[2]
    bridge_source = (project_root / "scripts" / "autoload" / "BackendBridge.gd").read_text(
        encoding="utf-8"
    )

    first_poll_index = bridge_source.index("ws.poll()")
    early_return_index = bridge_source.index(
        "if ws.get_ready_state() == WebSocketPeer.STATE_CLOSED and last_ready_state == WebSocketPeer.STATE_CLOSED:"
    )

    assert first_poll_index < early_return_index


def test_interactive_object_uses_visibility_state_family_defaults() -> None:
    project_root = Path(__file__).resolve().parents[2]
    object_source = (project_root / "scripts" / "object" / "InteractiveObject.gd").read_text(
        encoding="utf-8"
    )

    assert 'var current_state := "partially_visible"' in object_source
    assert 'current_state in ["hidden", "partially_visible"]' in object_source


def test_environment_state_controller_only_consumes_environment_state_results() -> None:
    project_root = Path(__file__).resolve().parents[2]
    controller_source = (project_root / "scripts" / "environment" / "EnvironmentStateController.gd").read_text(
        encoding="utf-8"
    )

    assert 'payload.get("result_type", "") == "environment_state_result"' in controller_source


def test_spatial_access_fact_emitter_sets_nearby_actor_ttl() -> None:
    project_root = Path(__file__).resolve().parents[2]
    emitter_source = (
        project_root / "scripts" / "l1" / "facts" / "emitters" / "SpatialAccessFactEmitter.gd"
    ).read_text(encoding="utf-8")

    assert '"nearby_actor_refs"' in emitter_source
    assert "1500" in emitter_source


def test_phase05_character_scene_upgrade_artifacts_exist_and_match_role_split() -> None:
    project_root = Path(__file__).resolve().parents[2]
    driver_spec_source = (project_root / "scripts" / "character" / "CharacterDriverSpec.gd").read_text(
        encoding="utf-8"
    )
    execution_notes = (project_root / "docs" / "character-execution-notes.md").read_text(
        encoding="utf-8"
    )
    scene_zones = (project_root / "docs" / "phase05-scene-zones.md").read_text(encoding="utf-8")
    mixabridge_notes = (project_root / "docs" / "mixabridge-character-pipeline.md").read_text(
        encoding="utf-8"
    )
    character_asset_notes = (project_root / "assets" / "characters" / "README.md").read_text(
        encoding="utf-8"
    )
    homebuilder_notes = (project_root / "docs" / "homebuilder-scene-pipeline.md").read_text(
        encoding="utf-8"
    )
    sample_scene_notes = (project_root / "docs" / "sample-scene-setup.md").read_text(
        encoding="utf-8"
    )

    assert "class_name CharacterDriverSpec" in driver_spec_source
    assert "enum DriverMode" in driver_spec_source
    assert "AI" in driver_spec_source
    assert "PLAYER" in driver_spec_source
    assert "driver_mode" in driver_spec_source
    assert "explicit driver mode: `ai` / `player`" in execution_notes
    assert "same shell usable by `A`, `B`, and `C`" in execution_notes
    assert "CharacterC" in scene_zones
    assert "player-driven in-world intervener" in scene_zones
    assert "Use `mixabridge` for:" in mixabridge_notes
    assert "optional offline asset-preparation path" in mixabridge_notes
    assert "not part of the current Phase 0 runtime dependency chain" in mixabridge_notes
    assert "shared skeleton and animation preparation path" in character_asset_notes
    assert "`A/B/C` should not diverge into separate asset conventions" in character_asset_notes
    assert "turn the open greybox field into a semi-open relationship space" in homebuilder_notes
    assert "`CharacterC` is the first player-driven in-world role shell" in sample_scene_notes


def test_phase0_open_scene_camera_artifacts_match_open_field_layout() -> None:
    project_root = Path(__file__).resolve().parents[2]
    scene_source = (project_root / "scenes" / "phase0" / "MainDemo.tscn").read_text(encoding="utf-8")
    controller_source = (project_root / "scripts" / "phase0" / "MainDemoController.gd").read_text(
        encoding="utf-8"
    )
    occlusion_source = (project_root / "scripts" / "player" / "CameraOcclusionFader.gd").read_text(
        encoding="utf-8"
    )
    sample_scene_notes = (project_root / "docs" / "sample-scene-setup.md").read_text(
        encoding="utf-8"
    )

    assert "size = Vector2(80, 50)" in scene_source
    assert "size = Vector3(80, 0.2, 50)" in scene_source
    assert "Boundary" in scene_source
    assert "@export var focus_max_distance := 28.0" in controller_source
    assert "spring_length = 6.6" in controller_source
    assert "floor_grid_probe" in controller_source
    assert "_is_fallback_occluder" in occlusion_source
    assert "_is_room_occluder" not in occlusion_source
    assert "WallBody" not in occlusion_source
    assert "Partition" not in occlusion_source
    assert "one open field instead of a multi-room greybox" in sample_scene_notes
    assert "Field footprint: about `80 x 50`" in sample_scene_notes


def test_wrapped_raw_fact_transport_contract_passes_scan_and_phase1_audit(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    allowed_dir = project_root / "scripts" / "l1" / "facts"
    visual_dir = project_root / "scripts" / "visual"
    player_dir = project_root / "scripts" / "player"

    allowed_dir.mkdir(parents=True)
    visual_dir.mkdir(parents=True)
    player_dir.mkdir(parents=True)

    (allowed_dir / "FactEnvelopeBuilder.gd").write_text(
        """
extends RefCounted

func build_raw_fact_envelope(payload: Dictionary) -> Dictionary:
    return {"message_type": "raw_fact_event", "payload": payload.duplicate(true)}

func build_raw_fact_payload(
    fact_family: String,
    fact_type: String,
    relation_type: String,
    room_id: String,
    scene_id: String,
    zone_id: String,
    source_actor_id: String = "",
    source_object_id: String = "",
    source_environment_id: String = "",
    target_actor_id: String = "",
    target_object_id: String = "",
    target_environment_id: String = "",
    source_system: String = "godot.raw_fact_emitter",
    source_layer: String = "L1",
    world: Dictionary = {},
    observability: Dictionary = {},
    causation_id: String = "",
    correlation_id: String = "",
    producer_ts: int = -1
) -> Dictionary:
    return {
        "event_type": "raw_fact_event",
        "fact_family": fact_family,
        "fact_type": fact_type,
        "relation_type": relation_type,
        "producer_ts": producer_ts,
        "room_id": room_id,
        "scene_id": scene_id,
        "zone_id": zone_id,
        "source": {
            "layer": source_layer,
            "system": source_system,
            "actor_id": source_actor_id,
            "object_id": source_object_id,
            "environment_id": source_environment_id,
        },
        "targets": {
            "actor_id": target_actor_id,
            "object_id": target_object_id,
            "environment_id": target_environment_id,
        },
        "world": {
            "position": world.get("position", null),
            "distance_m": world.get("distance_m", null),
            "state_before": world.get("state_before", ""),
            "state_after": world.get("state_after", ""),
        },
        "observability": {
            "visual": observability.get("visual", false),
            "auditory": observability.get("auditory", false),
            "occluded": observability.get("occluded", false),
        },
        "causation_id": causation_id,
        "correlation_id": correlation_id,
    }
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (allowed_dir / "RawFactEmitter.gd").write_text(
        """
extends RefCounted

func emit_raw_fact(payload: Dictionary, _log_prefix: String, _success_log: String = "", _dedupe_key: String = "") -> bool:
    var envelope := {"message_type": "raw_fact_event", "payload": payload}
    return bridge.send_envelope(envelope) == OK
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (visual_dir / "VisualFactEmitter.gd").write_text(
        """
extends Node

func emit_visual_fact(fact_type: String, relation_type: String, target_actor_id: String = "", target_object_id: String = "", target_environment_id: String = "") -> bool:
    return raw_fact_emitter.emit_raw_fact(
        _build_visual_fact_payload(fact_type, relation_type, target_actor_id, target_object_id, target_environment_id),
        "phase0_visual_fact_emitter",
        "phase0_visual_fact_emitter:%s:%s" % [fact_type, relation_type]
    )

func _build_visual_fact_payload(fact_type: String, relation_type: String, target_actor_id: String, target_object_id: String, target_environment_id: String) -> Dictionary:
    return builder.build_raw_fact_payload(
        "visual_fact",
        fact_type,
        relation_type,
        room_id,
        scene_id,
        zone_id,
        actor_id,
        "",
        "",
        target_actor_id,
        target_object_id,
        target_environment_id
    )
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (player_dir / "PlayerIntentMapper.gd").write_text(
        """
extends Node

func emit_visual_fact_event(...) -> Dictionary:
    return {}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    scan = scan_direct_visual_fact_bypass(project_root)
    report = evaluate_phase1_slice_audit(
        main_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_object
        [LocalPresentationBus] phase0_visual_fact_emitter:spatial_relation:actor_near_object
        [LocalPresentationBus] phase0_visual_fact_emitter:light_level_drop:environment_light_drop
        [LocalPresentationBus] phase0_visual_fact_emitter:visual_evidence_projection:evidence_projection
        [LocalPresentationBus] phase0_auditory_fact_emitter:speaker_active:char_a:normal
        [LocalPresentationBus] phase0_auditory_fact_emitter:auditory_reachability_changed:char_a:clear
        [LocalPresentationBus] phase0_auditory_fact_emitter:ambient_noise_changed:quiet
        [LocalPresentationBus] phase0_role_state_fact_emitter:role_state_transition:speak
        [LocalPresentationBus] phase0_physiology_fact_emitter:breathing_strain_changed:elevated
        [LocalPresentationBus] phase0_tactile_fact_emitter:contact_started:light
        [LocalPresentationBus] phase0_thermal_fact_emitter:thermal_proximity_changed:warm
        [LocalPresentationBus] phase0_olfactory_fact_emitter:odor_state_changed:noticeable
        [LocalPresentationBus] phase0_ack:{"accepted":true,"route":"authority_visual_fact","source_type":"raw_fact_event"}
        [LocalPresentationBus] conversation_candidate_event:{"candidate_object_ids":["obj_letter"]}
        [LocalPresentationBus] character_runtime_state_delta:{"current_attention_source":"visual_fact"}
        [LocalPresentationBus] backend_message_type:siming_output
        """,
        focus_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_actor
        [LocalPresentationBus] phase0_ack:{"accepted":true,"route":"authority_visual_fact","source_type":"raw_fact_event"}
        """,
        direct_send_scan=scan,
        scene_text='[node name="VisualFactEmitter" type="Node" parent="."]',
        candidate_policy_source='AUDITORY_CANDIDATE_POLICY = "targeted_actor_only"',
    )
    results = _index_by_id(report["results"])

    assert scan == "scripts/player/PlayerIntentMapper.gd:visual-fact-envelope-builder"
    assert report["overall_phase1_slice_passed"] is False
    assert results["no_direct_visual_fact_send_bypass"]["status"] == "proved"
    assert results["authority_ack_observed"]["status"] == "missing"
    assert results["object_visual_fact_observed"]["status"] == "missing"
    assert results["auditory_candidate_policy_explicit"]["status"] == "proved"
