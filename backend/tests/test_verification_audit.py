from app.verification_audit import evaluate_phase0_audit, evaluate_phase1_slice_audit


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
    )

    results = _index_by_id(report["results"])

    assert report["overall_strict_phase0_passed"] is False
    assert results["dialogue_loop"]["status"] == "proved"
    assert results["successful_interaction"]["status"] == "proved"
    assert results["failed_interaction"]["status"] == "missing"
    assert results["voice_stub_path"]["status"] == "weak"


def test_phase1_slice_audit_requires_emitter_and_authority_lane_evidence() -> None:
    report = evaluate_phase1_slice_audit(
        main_log="""
        [LocalPresentationBus] phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_object
        [LocalPresentationBus] phase0_visual_fact_emitter:spatial_relation:actor_near_object
        [LocalPresentationBus] phase0_visual_fact_emitter:light_level_drop:environment_light_drop
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
        scripts/visual/VisualFactEmitter.gd:43: var err: int = bridge.send_envelope(envelope)
        scripts/player/PlayerIntentMapper.gd:76:func emit_visual_fact_event(...)
        """,
        scene_text='[node name="VisualFactEmitter" type="Node" parent="."]',
    )

    results = _index_by_id(report["results"])

    assert report["overall_phase1_slice_passed"] is True
    assert results["emitter_scene_wired"]["status"] == "proved"
    assert results["no_direct_visual_fact_send_bypass"]["status"] == "proved"
    assert results["authority_ack_observed"]["status"] == "proved"
    assert results["environment_visual_fact_observed"]["status"] == "proved"
