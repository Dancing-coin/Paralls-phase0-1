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
        [LocalPresentationBus] object_state:obj_letter:object interaction accepted
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


def test_phase0_audit_proves_root_motion_player_and_patrol_evidence() -> None:
    report = evaluate_phase0_audit(
        pytest_passed=True,
        scene_load_ok=True,
        main_log="""
        [LocalPresentationBus] backend_connected:ws://127.0.0.1:8000/ws
        [LocalPresentationBus] phase0_dialogue_target:char_a
        [LocalPresentationBus] dialogue_applied:char_a
        [LocalPresentationBus] phase0_interact_target:obj_letter
        [LocalPresentationBus] object_state:obj_letter:object interaction accepted
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


def test_phase0_audit_requires_locomotion_state_ui_evidence() -> None:
    report = evaluate_phase0_audit(
        pytest_passed=True,
        scene_load_ok=True,
        main_log="""
        [LocalPresentationBus] backend_connected:ws://127.0.0.1:8010/ws
        [LocalPresentationBus] phase0_dialogue_target:char_a
        [LocalPresentationBus] dialogue_applied:char_a
        [LocalPresentationBus] phase0_interact_target:obj_letter
        [LocalPresentationBus] object_state:obj_letter:object interaction accepted
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
        [LocalPresentationBus] object_state:obj_letter:object interaction accepted
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
        [LocalPresentationBus] object_state:obj_letter:object interaction accepted
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

    assert report["overall_phase1_slice_passed"] is True
    assert results["emitter_scene_wired"]["status"] == "proved"
    assert results["no_direct_visual_fact_send_bypass"]["status"] == "proved"
    assert results["auditory_fact_observed"]["status"] == "proved"
    assert results["authority_ack_observed"]["status"] == "proved"
    assert results["environment_visual_fact_observed"]["status"] == "proved"


def test_phase1_slice_audit_rejects_legacy_visual_fact_event_ack_contract() -> None:
    report = evaluate_phase1_slice_audit(
        main_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_object
        [LocalPresentationBus] phase0_visual_fact_emitter:spatial_relation:actor_near_object
        [LocalPresentationBus] phase0_visual_fact_emitter:light_level_drop:environment_light_drop
        [LocalPresentationBus] phase0_auditory_fact_emitter:speaker_active:char_a:normal
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
    )

    results = _index_by_id(report["results"])

    assert report["overall_phase1_slice_passed"] is False
    assert results["authority_ack_observed"]["status"] == "missing"
    assert results["environment_visual_fact_observed"]["status"] == "proved"


def test_phase1_slice_audit_requires_auditory_fact_proof() -> None:
    report = evaluate_phase1_slice_audit(
        main_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_object
        [LocalPresentationBus] phase0_visual_fact_emitter:spatial_relation:actor_near_object
        [LocalPresentationBus] phase0_visual_fact_emitter:light_level_drop:environment_light_drop
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
    assert results["auditory_fact_observed"]["status"] == "missing"


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

    assert "func _emit_dialogue_request(" in controller_source
    assert "func _emit_interaction_request(" in controller_source
    assert "func _emit_move_intent_request(" in controller_source
    assert "phase0_move_target:" in controller_source


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


def test_spatial_access_fact_emitter_sets_nearby_actor_ttl() -> None:
    project_root = Path(__file__).resolve().parents[2]
    emitter_source = (
        project_root / "scripts" / "l1" / "facts" / "emitters" / "SpatialAccessFactEmitter.gd"
    ).read_text(encoding="utf-8")

    assert '"nearby_actor_refs"' in emitter_source
    assert "1500" in emitter_source


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
        direct_send_scan=scan,
        scene_text='[node name="VisualFactEmitter" type="Node" parent="."]',
    )
    results = _index_by_id(report["results"])

    assert scan == "scripts/player/PlayerIntentMapper.gd:visual-fact-envelope-builder"
    assert report["overall_phase1_slice_passed"] is True
    assert results["no_direct_visual_fact_send_bypass"]["status"] == "proved"
    assert results["authority_ack_observed"]["status"] == "proved"
