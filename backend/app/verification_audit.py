from __future__ import annotations

import json
import re


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


def _extract_probe_json(body: str, field: str) -> dict[str, object]:
    marker = f"{field}="
    start = body.find(marker)
    if start < 0:
        return {}
    index = start + len(marker)
    while index < len(body) and body[index].isspace():
        index += 1
    if index >= len(body) or body[index] != "{":
        return {}

    depth = 0
    in_string = False
    escaped = False
    for end in range(index, len(body)):
        char = body[end]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(body[index : end + 1])
                except json.JSONDecodeError:
                    return {}
                return parsed if isinstance(parsed, dict) else {}
    return {}


def _extract_probe_int(body: str, field: str) -> int:
    match = re.search(rf"\b{re.escape(field)}=(?P<value>\d+)", body)
    if match is None:
        return 0
    return int(match.group("value"))


def _phase1_probe_summary(log: str, mode: str) -> dict[str, object]:
    pattern = re.compile(rf"phase1_slice_runtime_probe:{re.escape(mode)}:(?P<body>.+)")
    match = pattern.search(log)
    if match is None:
        return {"acks": {}, "sources": {}, "facts": {}, "deltas": 0, "candidates": 0, "siming": 0}
    body = match.group("body")
    acks = _extract_probe_json(body, "acks")
    sources = _extract_probe_json(body, "sources")
    facts = _extract_probe_json(body, "facts")
    return {
        "acks": acks,
        "sources": sources,
        "facts": facts,
        "deltas": _extract_probe_int(body, "deltas"),
        "candidates": _extract_probe_int(body, "candidates"),
        "siming": _extract_probe_int(body, "siming"),
    }


def _probe_source_ack_count(summary: dict[str, object], route: str, source_type: str) -> int:
    sources = summary.get("sources", {})
    if not isinstance(sources, dict):
        return 0
    route_sources = sources.get(route, {})
    if not isinstance(route_sources, dict):
        return 0
    try:
        return int(route_sources.get(source_type, 0))
    except (TypeError, ValueError):
        return 0


def _probe_has_fact(
    summary: dict[str, object],
    route: str,
    fact_key: str,
    *,
    source_type: str = "raw_fact_event",
) -> bool:
    facts = summary.get("facts", {})
    if not isinstance(facts, dict):
        return False
    route_facts_by_source = facts.get(route, {})
    if not isinstance(route_facts_by_source, dict):
        return False
    route_facts = route_facts_by_source.get(source_type, [])
    if not isinstance(route_facts, list):
        return False
    return fact_key in {str(entry) for entry in route_facts}


def _probe_has_all_facts(summary: dict[str, object], route: str, fact_keys: list[str]) -> bool:
    return all(_probe_has_fact(summary, route, fact_key) for fact_key in fact_keys)


def evaluate_phase0_audit(
    *,
    pytest_passed: bool,
    scene_load_ok: bool,
    main_log: str,
    focus_log: str,
    main_screenshot_exists: bool,
    focus_screenshot_exists: bool,
    interaction_source: str,
    esm_service_source: str,
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

    execution_contract_ok = (
        "character_agent_execution" in combined_log
        and '"controller_source":"agent"' in combined_log
        and '"control_mode":"agent_controlled"' in combined_log
        and '"focus_state":{' in combined_log
        and '"action_state":{' in combined_log
        and '"speech_state":{' in combined_log
        and "character_agent_output:" not in combined_log
    )
    results.append(
        _result(
            "character_agent_execution_contract",
            "Runtime character_agent_execution payload stays on the shared CharacterActor execution contract",
            "proved" if execution_contract_ok else "missing",
            [
                "character_agent_execution",
                "controller_source=agent",
                "control_mode=agent_controlled",
                "focus_state",
                "action_state",
                "speech_state",
            ]
            if execution_contract_ok
            else [],
            "" if execution_contract_ok else "Runtime log did not prove the stronger execution contract or still showed legacy runtime output handling.",
        )
    )

    execution_consumer_ok = (
        "character_agent_execution_probe:consumer_seen=true" in combined_log
        and "character_agent_execution_probe:legacy_output_seen=false" in combined_log
    )
    results.append(
        _result(
            "character_agent_execution_consumer",
            "CharacterReplica consumes the execution contract in runtime",
            "proved" if execution_consumer_ok else "missing",
            ["CharacterA is CharacterReplica", "has_external_look_target"] if execution_consumer_ok else [],
            "" if execution_consumer_ok else "Runtime log did not prove CharacterReplica consumed the execution contract as the active runtime consumer.",
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

    esm_request_lineage_ok = _contains_all(
        interaction_source,
        [
            "request_ref=world_result.request_ref",
            "causation_id=world_result.causation_id",
            "correlation_id=world_result.correlation_id",
        ],
    )
    results.append(
        _result(
            "esm_request_lineage",
            "ESM follow-on success results preserve the originating request lineage",
            "proved" if esm_request_lineage_ok else "missing",
            ["request_ref", "causation_id", "correlation_id"] if esm_request_lineage_ok else [],
        )
    )

    esm_thermal_field_ok = (
        "thermal_level=field_state.thermal_level" in esm_service_source
        and '"thermal_level"' in esm_service_source
    )
    results.append(
        _result(
            "esm_thermal_field",
            "ESM environment-state evidence includes the coarse thermal field contract",
            "proved" if esm_thermal_field_ok else "missing",
            ["thermal_level field contract"] if esm_thermal_field_ok else [],
        )
    )

    siming_ok = "attention_applied:char_b" in main_log or "backend_message_type:siming_output" in combined_log
    results.append(
        _result(
            "siming_reaction",
            "Minimal Siming reaction is observable",
            "proved" if siming_ok else "missing",
            ["attention_applied:char_b", "backend_message_type:siming_output"] if siming_ok else [],
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

    observatory_state_payloads_ok = (
        "character_director_observatory_probe:state_payloads_ok=true" in combined_log
        and "character_agent_debug_snapshot" in combined_log
        and "siming_debug_snapshot" in combined_log
        and "world_outcome_trace" in combined_log
        and "script_beat_event" in combined_log
    )
    results.append(
        _result(
            "observatory_state_payloads",
            "Observatory state center receives actor/siming/world/script payloads",
            "proved" if observatory_state_payloads_ok else "missing",
            ["character_director_observatory_probe:state_payloads_ok=true"] if observatory_state_payloads_ok else [],
        )
    )

    observatory_panels_populated_ok = "character_director_observatory_probe:panels_populated=true" in combined_log
    results.append(
        _result(
            "observatory_panels_populated",
            "Observatory workstation panels populate with dramatic scene data",
            "proved" if observatory_panels_populated_ok else "missing",
            ["character_director_observatory_probe:panels_populated=true"] if observatory_panels_populated_ok else [],
        )
    )

    observatory_freeze_roundtrip_ok = "character_director_observatory_probe:freeze_roundtrip_ok=true" in combined_log
    results.append(
        _result(
            "observatory_freeze_roundtrip",
            "Observatory freeze mode can be entered and exited cleanly",
            "proved" if observatory_freeze_roundtrip_ok else "missing",
            ["character_director_observatory_probe:freeze_roundtrip_ok=true"] if observatory_freeze_roundtrip_ok else [],
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
        "esm_request_lineage",
        "esm_thermal_field",
        "siming_reaction",
        "voice_stub_path",
        "player_root_motion_chain",
        "npc_root_motion_patrol",
        "locomotion_state_ui",
        "jump_variant_probes",
        "forward_direction_probe",
        "repeatable_run",
        "observatory_state_payloads",
        "observatory_panels_populated",
        "observatory_freeze_roundtrip",
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
    scene_label: str = "Phase1SliceRuntimeProbe",
    candidate_policy_source: str = "",
) -> dict[str, object]:
    results: list[dict[str, object]] = []
    main_probe = _phase1_probe_summary(main_log, "main")
    focus_probe = _phase1_probe_summary(focus_log, "focus")
    emitter_scene_wired = 'name="VisualFactEmitter"' in scene_text
    results.append(
        _result(
            "emitter_scene_wired",
            f"VisualFactEmitter is wired into {scene_label}",
            "proved" if emitter_scene_wired else "missing",
            [f"{scene_label} VisualFactEmitter scene node"] if emitter_scene_wired else [],
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

    object_fact_ok = _probe_has_fact(main_probe, "authority_visual_fact", "actor_looks_at_object")
    results.append(
        _result(
            "object_visual_fact_observed",
            "Object-focused visual fact goes through emitter",
            "proved" if object_fact_ok else "missing",
            ["actor_looks_at_object"] if object_fact_ok else [],
        )
    )

    actor_fact_ok = _probe_has_fact(focus_probe, "authority_visual_fact", "actor_looks_at_actor")
    results.append(
        _result(
            "actor_visual_fact_observed",
            "Actor-focused visual fact goes through emitter",
            "proved" if actor_fact_ok else "missing",
            ["actor_looks_at_actor"] if actor_fact_ok else [],
        )
    )

    near_object_ok = _probe_has_fact(main_probe, "authority_visual_fact", "actor_near_object")
    results.append(
        _result(
            "near_object_visual_fact_observed",
            "Near-object spatial relation goes through emitter",
            "proved" if near_object_ok else "missing",
            ["actor_near_object"] if near_object_ok else [],
        )
    )

    environment_ok = _probe_has_fact(main_probe, "authority_visual_fact", "environment_light_drop")
    results.append(
        _result(
            "environment_visual_fact_observed",
            "Environment visual fact goes through emitter",
            "proved" if environment_ok else "missing",
            ["environment_light_drop"] if environment_ok else [],
        )
    )

    evidence_projection_ok = _probe_has_fact(main_probe, "authority_visual_fact", "evidence_projection")
    results.append(
        _result(
            "evidence_projection_visual_fact_observed",
            "Evidence-projection visual fact goes through emitter",
            "proved" if evidence_projection_ok else "missing",
            ["visual_evidence_projection"] if evidence_projection_ok else [],
        )
    )

    auditory_ok = _probe_has_all_facts(
        main_probe,
        "authority_auditory_fact",
        ["speaker_active", "auditory_reachability_changed", "ambient_noise_changed"],
    )
    results.append(
        _result(
            "auditory_fact_observed",
            "Auditory raw fact goes through emitter",
            "proved" if auditory_ok else "missing",
            ["speaker_active", "auditory_reachability_changed", "ambient_noise_changed"] if auditory_ok else [],
        )
    )

    auditory_policy_ok = 'AUDITORY_CANDIDATE_POLICY = "targeted_actor_only"' in candidate_policy_source
    results.append(
        _result(
            "auditory_candidate_policy_explicit",
            "Auditory candidate policy is explicitly frozen to targeted-actor-only for now",
            "proved" if auditory_policy_ok else "missing",
            ["AUDITORY_CANDIDATE_POLICY=targeted_actor_only"] if auditory_policy_ok else [],
        )
    )

    role_state_ok = _probe_has_fact(main_probe, "authority_role_state_fact", "role_state_transition")
    results.append(
        _result(
            "role_state_fact_observed",
            "Role-state raw fact goes through emitter",
            "proved" if role_state_ok else "missing",
            ["role_state_transition"] if role_state_ok else [],
        )
    )

    physiology_ok = _probe_has_fact(main_probe, "authority_physiology_fact", "breathing_strain_changed")
    results.append(
        _result(
            "physiology_fact_observed",
            "Physiology-state raw fact goes through emitter",
            "proved" if physiology_ok else "missing",
            ["breathing_strain_changed"] if physiology_ok else [],
        )
    )

    tactile_ok = _probe_has_fact(main_probe, "authority_tactile_fact", "contact_started")
    results.append(
        _result(
            "tactile_fact_observed",
            "Tactile raw fact goes through emitter",
            "proved" if tactile_ok else "missing",
            ["contact_started"] if tactile_ok else [],
        )
    )

    thermal_ok = _probe_has_fact(main_probe, "authority_thermal_fact", "thermal_proximity_changed")
    results.append(
        _result(
            "thermal_fact_observed",
            "Thermal raw fact goes through emitter",
            "proved" if thermal_ok else "missing",
            ["thermal_proximity_changed"] if thermal_ok else [],
        )
    )

    olfactory_ok = _probe_has_fact(main_probe, "authority_olfactory_fact", "odor_state_changed")
    results.append(
        _result(
            "olfactory_fact_observed",
            "Olfactory raw fact goes through emitter",
            "proved" if olfactory_ok else "missing",
            ["odor_state_changed"] if olfactory_ok else [],
        )
    )

    authority_ack_ok = (
        _probe_source_ack_count(main_probe, "authority_visual_fact", "raw_fact_event") >= 4
        and _probe_source_ack_count(focus_probe, "authority_visual_fact", "raw_fact_event") >= 1
    )
    results.append(
        _result(
            "authority_ack_observed",
            "Authority lane acknowledges visual facts",
            "proved" if authority_ack_ok else "missing",
            ["authority_visual_fact via raw_fact_event"] if authority_ack_ok else [],
        )
    )

    runtime_projection_ok = (
        "character_runtime_state_delta" in main_log
        and '"current_attention_source":"visual_fact"' in main_log
    ) or int(main_probe["deltas"]) >= 1
    results.append(
        _result(
            "runtime_projection_observed",
            "Visual facts project into backend-owned runtime state",
            "proved" if runtime_projection_ok else "missing",
            ["character_runtime_state_delta", "current_attention_source=visual_fact"] if runtime_projection_ok else [],
        )
    )

    candidate_and_siming_ok = (
        "conversation_candidate_event" in main_log
        and "backend_message_type:siming_output" in main_log
    ) or (int(main_probe["candidates"]) >= 1 and int(main_probe["siming"]) >= 1)
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
