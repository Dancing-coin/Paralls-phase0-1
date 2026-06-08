from __future__ import annotations


def _result(
    result_id: str,
    title: str,
    status: str,
    evidence: list[str],
    notes: str = "",
) -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": status,
        "evidence": evidence,
        "notes": notes,
    }


def _contains_all(text: str, patterns: list[str]) -> bool:
    return all(pattern in text for pattern in patterns)


def _status_index(results: list[dict[str, object]]) -> dict[str, str]:
    return {str(entry["id"]): str(entry["status"]) for entry in results}


def evaluate_phase0_audit(
    *,
    pytest_passed: bool,
    scene_load_ok: bool,
    main_log: str,
    focus_log: str,
    main_screenshot_exists: bool,
    focus_screenshot_exists: bool,
    interaction_source: str,
    voice_controller_source: str,
    player_bridge_source: str,
    character_replica_source: str,
) -> dict[str, object]:
    results: list[dict[str, object]] = []

    results.append(
        _result(
            "backend_tests",
            "Backend tests pass",
            "proved" if pytest_passed else "missing",
            ["pytest"] if pytest_passed else [],
        )
    )
    results.append(
        _result(
            "scene_load",
            "Godot main scene loads without script parse errors",
            "proved" if scene_load_ok else "missing",
            ["scene-load"] if scene_load_ok else [],
        )
    )

    combined_log = main_log + "\n" + focus_log
    backend_connected = "backend_connected:ws://127.0.0.1:" in combined_log
    results.append(
        _result(
            "backend_connectivity",
            "Godot connects to backend",
            "proved" if backend_connected else "missing",
            ["backend_connected"] if backend_connected else [],
        )
    )

    dialogue_ok = _contains_all(main_log, ["phase0_dialogue_target:char_a", "dialogue_applied:char_a"])
    results.append(
        _result(
            "dialogue_loop",
            "Structured dialogue input produces an in-scene response",
            "proved" if dialogue_ok else "missing",
            ["phase0_dialogue_target", "dialogue_applied"] if dialogue_ok else [],
        )
    )

    success_interaction_ok = "phase0_interact_target:obj_letter" in main_log and (
        "object_state:obj_letter:object interaction accepted" in main_log
        or "object_state:obj_letter:visible" in main_log
    )
    results.append(
        _result(
            "successful_interaction",
            "Authoritative successful interaction is observable",
            "proved" if success_interaction_ok else "missing",
            ["phase0_interact_target", "object_state"] if success_interaction_ok else [],
        )
    )

    failed_interaction_ok = "constraint_state_result" in main_log or "constraint_type" in main_log or "too far" in main_log
    failed_interaction_notes = ""
    failed_interaction_status = "proved" if failed_interaction_ok else "missing"
    if not failed_interaction_ok and "is_in_range=True" in interaction_source:
        failed_interaction_notes = "Current websocket interaction path hardcodes is_in_range=True, so the Godot demo path cannot currently produce a failed interaction."
    results.append(
        _result(
            "failed_interaction",
            "Authoritative failed interaction is observable in the demo path",
            failed_interaction_status,
            ["constraint_state_result"] if failed_interaction_ok else [],
            failed_interaction_notes,
        )
    )

    world_change_ok = "environment_state:alerted" in main_log
    results.append(
        _result(
            "visible_world_state_change",
            "Object or environment visible state change is observable",
            "proved" if world_change_ok else "missing",
            ["environment_state:alerted"] if world_change_ok else [],
        )
    )

    siming_ok = "attention_applied:char_b" in main_log
    results.append(
        _result(
            "siming_reaction",
            "Minimal Siming reaction is observable",
            "proved" if siming_ok else "missing",
            ["attention_applied:char_b"] if siming_ok else [],
        )
    )

    voice_observed = "play_stub_voice" in main_log or "voice_stub_played" in main_log
    voice_path_exists = "func play_stub_voice" in voice_controller_source
    voice_status = "proved" if voice_observed else ("weak" if voice_path_exists and dialogue_ok else "missing")
    voice_notes = ""
    if voice_status == "weak":
        voice_notes = "Stub voice code path exists and dialogue is observed, but no runtime log proves audible stub playback."
    results.append(
        _result(
            "voice_stub_path",
            "Voice playback or approved stub voice path is observable",
            voice_status,
            ["play_stub_voice"] if voice_status != "missing" else [],
            voice_notes,
        )
    )

    player_root_motion_runtime_ok = "player_root_motion_step:char_c" in main_log or "player_root_motion_step:char_c" in focus_log
    player_root_motion_code_ok = "before_player_shell_move" in player_bridge_source and "consume_player_root_motion_request" in character_replica_source
    player_root_motion_status = "proved" if player_root_motion_runtime_ok else ("weak" if player_root_motion_code_ok else "missing")
    player_root_motion_notes = ""
    if player_root_motion_status == "weak":
        player_root_motion_notes = "Player root motion code path exists, but no runtime audit log proves CharacterC drove the player shell during verification."
    results.append(
        _result(
            "player_root_motion_chain",
            "CharacterC root motion drives the player locomotion shell",
            player_root_motion_status,
            ["player_root_motion_step:char_c"] if player_root_motion_status != "missing" else [],
            player_root_motion_notes,
        )
    )

    patrol_root_motion_runtime_ok = "patrol_root_motion_step:char_a" in main_log or "patrol_root_motion_step:char_b" in main_log
    patrol_root_motion_code_ok = "patrol_root_motion_step" in character_replica_source and "_consume_role_root_motion_world_delta" in character_replica_source
    patrol_root_motion_status = "proved" if patrol_root_motion_runtime_ok else ("weak" if patrol_root_motion_code_ok else "missing")
    patrol_root_motion_notes = ""
    if patrol_root_motion_status == "weak":
        patrol_root_motion_notes = "A/B patrol root motion code path exists, but runtime verification did not capture a patrol root motion step."
    results.append(
        _result(
            "npc_root_motion_patrol",
            "CharacterA/B patrol stays controller-authoritative while consuming root motion increments",
            patrol_root_motion_status,
            ["patrol_root_motion_step"] if patrol_root_motion_status != "missing" else [],
            patrol_root_motion_notes,
        )
    )

    locomotion_state_ui_ok = (
        "locomotion_state:" in combined_log
        and "gait=" in combined_log
        and "stance=" in combined_log
        and "jump=" in combined_log
        and "profile=" in combined_log
    )
    results.append(
        _result(
            "locomotion_state_ui",
            "Locomotion state is visible in UI/debug output",
            "proved" if locomotion_state_ui_ok else "missing",
            ["locomotion_state"] if locomotion_state_ui_ok else [],
        )
    )

    jump_variant_probe_ok = (
        "jump_probe:type=two_foot" in combined_log
        and "jump_probe:type=single_leg" in combined_log
    )
    results.append(
        _result(
            "jump_variant_probes",
            "Two-foot and single-leg jump probes are both observable",
            "proved" if jump_variant_probe_ok else "missing",
            ["jump_probe:type=two_foot", "jump_probe:type=single_leg"] if jump_variant_probe_ok else [],
        )
    )

    forward_direction_probe_ok = "locomotion_probe:" in combined_log and "dz=-" in combined_log
    results.append(
        _result(
            "forward_direction_probe",
            "Forward locomotion probe moves in the expected forward direction",
            "proved" if forward_direction_probe_ok else "missing",
            ["locomotion_probe dz negative"] if forward_direction_probe_ok else [],
        )
    )

    repeatable_ok = scene_load_ok and main_screenshot_exists and focus_screenshot_exists and backend_connected
    results.append(
        _result(
            "repeatable_run",
            "Validation flow is repeatable and saves evidence artifacts",
            "proved" if repeatable_ok else "missing",
            [entry for entry in ["main_screenshot", "focus_screenshot"] if (entry == "main_screenshot" and main_screenshot_exists) or (entry == "focus_screenshot" and focus_screenshot_exists)],
        )
    )

    strict_ids = [
        "backend_tests",
        "scene_load",
        "backend_connectivity",
        "dialogue_loop",
        "successful_interaction",
        "failed_interaction",
        "visible_world_state_change",
        "siming_reaction",
        "voice_stub_path",
        "player_root_motion_chain",
        "npc_root_motion_patrol",
        "locomotion_state_ui",
        "jump_variant_probes",
        "forward_direction_probe",
        "repeatable_run",
    ]
    index = _status_index(results)
    overall_strict_phase0_passed = all(index[result_id] == "proved" for result_id in strict_ids)

    return {
        "results": results,
        "overall_strict_phase0_passed": overall_strict_phase0_passed,
    }


def evaluate_phase1_slice_audit(
    *,
    main_log: str,
    focus_log: str,
    direct_send_scan: str,
    scene_text: str,
) -> dict[str, object]:
    results: list[dict[str, object]] = []

    emitter_scene_wired = 'name="VisualFactEmitter"' in scene_text
    results.append(
        _result(
            "emitter_scene_wired",
            "VisualFactEmitter is wired into MainDemo",
            "proved" if emitter_scene_wired else "missing",
            ["VisualFactEmitter scene node"] if emitter_scene_wired else [],
        )
    )

    suspicious_lines = [
        line.strip()
        for line in direct_send_scan.splitlines()
        if line.strip() != ""
        and "scripts/visual/VisualFactEmitter.gd" not in line
        and "scripts/player/PlayerIntentMapper.gd" not in line
    ]
    results.append(
        _result(
            "no_direct_visual_fact_send_bypass",
            "No ad hoc Godot-side visual_fact send bypass remains",
            "proved" if not suspicious_lines else "missing",
            ["direct-send scan clean"] if not suspicious_lines else suspicious_lines,
        )
    )

    object_fact_ok = "phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_object" in main_log
    results.append(
        _result(
            "object_visual_fact_observed",
            "Object-focused visual fact goes through emitter",
            "proved" if object_fact_ok else "missing",
            ["actor_looks_at_object"] if object_fact_ok else [],
        )
    )

    actor_fact_ok = "phase0_visual_fact_emitter:fixed_gaze_on_target:actor_looks_at_actor" in focus_log
    results.append(
        _result(
            "actor_visual_fact_observed",
            "Actor-focused visual fact goes through emitter",
            "proved" if actor_fact_ok else "missing",
            ["actor_looks_at_actor"] if actor_fact_ok else [],
        )
    )

    near_object_ok = "phase0_visual_fact_emitter:spatial_relation:actor_near_object" in main_log
    results.append(
        _result(
            "near_object_visual_fact_observed",
            "Near-object spatial relation goes through emitter",
            "proved" if near_object_ok else "missing",
            ["actor_near_object"] if near_object_ok else [],
        )
    )

    environment_ok = "phase0_visual_fact_emitter:light_level_drop:environment_light_drop" in main_log
    results.append(
        _result(
            "environment_visual_fact_observed",
            "Environment visual fact goes through emitter",
            "proved" if environment_ok else "missing",
            ["environment_light_drop"] if environment_ok else [],
        )
    )

    auditory_ok = "phase0_auditory_fact_emitter:speaker_active:" in main_log
    results.append(
        _result(
            "auditory_fact_observed",
            "Auditory raw fact goes through emitter",
            "proved" if auditory_ok else "missing",
            ["speaker_active"] if auditory_ok else [],
        )
    )

    role_state_ok = "phase0_role_state_fact_emitter:role_state_transition:" in main_log
    results.append(
        _result(
            "role_state_fact_observed",
            "Role-state raw fact goes through emitter",
            "proved" if role_state_ok else "missing",
            ["role_state_transition"] if role_state_ok else [],
        )
    )

    physiology_ok = "phase0_physiology_fact_emitter:breathing_strain_changed:" in main_log
    results.append(
        _result(
            "physiology_fact_observed",
            "Physiology-state raw fact goes through emitter",
            "proved" if physiology_ok else "missing",
            ["breathing_strain_changed"] if physiology_ok else [],
        )
    )

    tactile_ok = "phase0_tactile_fact_emitter:contact_started:" in main_log
    results.append(
        _result(
            "tactile_fact_observed",
            "Tactile raw fact goes through emitter",
            "proved" if tactile_ok else "missing",
            ["contact_started"] if tactile_ok else [],
        )
    )

    thermal_ok = "phase0_thermal_fact_emitter:thermal_proximity_changed:" in main_log
    results.append(
        _result(
            "thermal_fact_observed",
            "Thermal raw fact goes through emitter",
            "proved" if thermal_ok else "missing",
            ["thermal_proximity_changed"] if thermal_ok else [],
        )
    )

    olfactory_ok = "phase0_olfactory_fact_emitter:odor_state_changed:" in main_log
    results.append(
        _result(
            "olfactory_fact_observed",
            "Olfactory raw fact goes through emitter",
            "proved" if olfactory_ok else "missing",
            ["odor_state_changed"] if olfactory_ok else [],
        )
    )

    authority_ack_token = '"route":"authority_visual_fact","source_type":"raw_fact_event"'
    authority_ack_ok = authority_ack_token in main_log or authority_ack_token in focus_log
    results.append(
        _result(
            "authority_ack_observed",
            "Authority lane acknowledges visual facts",
            "proved" if authority_ack_ok else "missing",
            ["authority_visual_fact via raw_fact_event"] if authority_ack_ok else [],
        )
    )

    runtime_projection_ok = "character_runtime_state_delta" in main_log and '"current_attention_source":"visual_fact"' in main_log
    results.append(
        _result(
            "runtime_projection_observed",
            "Visual facts project into backend-owned runtime state",
            "proved" if runtime_projection_ok else "missing",
            ["character_runtime_state_delta", "current_attention_source=visual_fact"] if runtime_projection_ok else [],
        )
    )

    candidate_and_siming_ok = "conversation_candidate_event" in main_log and "backend_message_type:siming_output" in main_log
    results.append(
        _result(
            "candidate_and_siming_observed",
            "Visual facts feed candidate generation and Siming output",
            "proved" if candidate_and_siming_ok else "missing",
            ["conversation_candidate_event", "siming_output"] if candidate_and_siming_ok else [],
        )
    )

    overall_phase1_slice_passed = all(str(entry["status"]) == "proved" for entry in results)
    return {
        "results": results,
        "overall_phase1_slice_passed": overall_phase1_slice_passed,
    }
