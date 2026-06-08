from app.models.environment_request import EnvironmentRequest
from app.models.player_input import InteractIntent
from app.services.esm_service import ESMService


def test_esm_service_builds_action_request_from_interact_intent() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=9,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )

    request = service.build_action_request(event, source_system="player_input_bridge")

    assert request.request_type == "interact"
    assert request.room_id == "room_demo"
    assert request.scene_id == "scene_demo"
    assert request.zone_id == "zone_focus"
    assert request.source["layer"] == "L1"
    assert request.source["system"] == "player_input_bridge"
    assert request.source["actor_id"] == "char_c"
    assert request.target_entity_refs["object_ids"] == ["obj_letter"]
    assert request.action_profile == "inspect"
    assert request.causation_id == "interact:9"
    assert request.correlation_id == "interact:9"


def test_esm_service_builds_action_request_from_environment_request() -> None:
    service = ESMService()
    event = EnvironmentRequest(
        request_id="envreq:1",
        candidate_ref="cand_light_drop",
        decision_ref="decision_light_drop",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L3", "system": "siming.orchestrator", "actor_id": ""},
        target_entity_refs={"actor_ids": [], "object_ids": [], "environment_ids": ["env_lamp"]},
        goal="reduce visibility near the letter",
        requested_change_type="light_level_drop",
        requested_strength="medium",
        ttl=1500,
        reason_tag="opportunity_window",
        producer_ts=30,
        causation_id="decision:30",
        correlation_id="decision:30",
    )

    request = service.build_environment_action_request(event)

    assert request.request_id == "envreq:1"
    assert request.request_type == "environment_request"
    assert request.room_id == "room_demo"
    assert request.scene_id == "scene_demo"
    assert request.zone_id == "zone_focus"
    assert request.source["layer"] == "L3"
    assert request.source["system"] == "siming.orchestrator"
    assert request.target_entity_refs["environment_ids"] == ["env_lamp"]
    assert request.action_profile == "light_level_drop"
    assert request.intent_strength == "medium"
    assert request.constraints_hint["goal"] == "reduce visibility near the letter"
    assert request.causation_id == "decision:30"
    assert request.correlation_id == "decision:30"


def test_esm_service_accepts_nearby_interaction() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=10,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )
    result = service.resolve_interaction(event, is_in_range=True)
    assert result.result_type == "action_resolution_result"


def test_esm_service_rejects_out_of_range_interaction() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=11,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )
    result = service.resolve_interaction(event, is_in_range=False)
    assert result.result_type == "constraint_state_result"
    assert result.constraint_type == "distance_constraint"
    assert result.constraint_code == "out_of_range"


def test_esm_service_computes_range_from_actor_position() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=12,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )
    near = service.resolve_interaction(event, actor_position=(0.0, 1.0, -0.5))
    far = service.resolve_interaction(event, actor_position=(0.0, 1.0, 20.0))

    assert near.result_type == "action_resolution_result"
    assert far.result_type == "constraint_state_result"


def test_esm_service_rejects_far_actor_position() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=12,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )
    result = service.resolve_interaction(event, actor_position=(0.0, 0.0, 16.0))
    assert result.result_type == "constraint_state_result"
    assert result.constraint_type == "distance_constraint"
    assert result.constraint_code == "out_of_range"


def test_esm_service_success_result_exposes_stable_phase1_contract_fields() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=20,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )

    result = service.resolve_interaction(event, is_in_range=True)

    assert result.result_type == "action_resolution_result"
    assert result.actor_id == "char_c"
    assert result.scene_id == "scene_demo"
    assert result.zone_id == "zone_focus"
    assert result.request_ref == "interact:20:obj_letter"
    assert result.result_id == "action_resolution:interact:20:obj_letter"
    assert result.causation_id == "interact:20"
    assert result.correlation_id == "interact:20"
    assert result.settlement_status == "accepted"
    assert result.resolved_entities == ["obj_letter"]
    assert result.applied_state_changes == [
        "object_state_result",
        "body_state_result",
        "environment_state_result",
    ]
    assert result.stable_state_summary == "interaction accepted"


def test_esm_service_constraint_result_exposes_stable_phase1_contract_fields() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=21,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )

    result = service.resolve_interaction(event, is_in_range=False)

    assert result.result_type == "constraint_state_result"
    assert result.actor_id == "char_c"
    assert result.scene_id == "scene_demo"
    assert result.zone_id == "zone_focus"
    assert result.request_ref == "interact:21:obj_letter"
    assert result.result_id == "constraint:interact:21:obj_letter"
    assert result.causation_id == "interact:21"
    assert result.correlation_id == "interact:21"
    assert result.constraint_type == "distance_constraint"
    assert result.constraint_code == "out_of_range"
    assert result.blocking_entity_refs == ["obj_letter"]
    assert result.settlement_status == "rejected"


def test_esm_service_environment_shift_result_is_replayable_and_updates_field_state() -> None:
    service = ESMService()

    result = service.emit_environment_shift(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        target_environment_id="env_lamp",
        previous_state="stable",
        current_state="alerted",
    )

    assert result.result_type == "environment_state_result"
    assert result.actor_id == "char_c"
    assert result.scene_id == "scene_demo"
    assert result.zone_id == "zone_focus"
    assert result.causation_id == "env:env_lamp:alerted"
    assert result.correlation_id == "env:env_lamp:alerted"
    assert result.settlement_status == "applied"
    assert result.affected_zone_ids == ["zone_focus"]
    assert result.field_delta_summary == ["light_level", "noise_level", "smoke_density", "visibility_level"]
    assert result.light_level == "low"
    assert result.noise_level == "elevated"
    assert result.smoke_density == "light"
    assert result.visibility_level == "reduced"

    field = service.get_environment_field("room_demo", "zone_focus")
    assert field.field_id == "field:room_demo:scene_demo:zone_focus"
    assert field.scene_id == "scene_demo"
    assert field.light_level == "low"
    assert field.noise_level == "elevated"
    assert field.temperature == "ambient"
    assert field.humidity == "stable"
    assert field.smoke_density == "light"
    assert field.visibility_level == "reduced"
    assert field.updated_at == result.producer_ts


def test_esm_service_accepts_environment_request_and_emits_resolution_and_environment_result() -> None:
    service = ESMService()
    event = EnvironmentRequest(
        request_id="envreq:2",
        candidate_ref="cand_light_drop",
        decision_ref="decision_light_drop",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L3", "system": "siming.orchestrator", "actor_id": ""},
        target_entity_refs={"actor_ids": [], "object_ids": [], "environment_ids": ["env_lamp"]},
        goal="reduce visibility near the letter",
        requested_change_type="light_level_drop",
        requested_strength="medium",
        ttl=1500,
        reason_tag="opportunity_window",
        producer_ts=31,
        causation_id="decision:31",
        correlation_id="decision:31",
    )

    resolution, environment_result = service.resolve_environment_request(event)

    assert resolution.result_type == "action_resolution_result"
    assert resolution.request_ref == "envreq:2"
    assert resolution.result_id == "action_resolution:envreq:2"
    assert resolution.resolution_status == "accepted"
    assert resolution.resolved_entities == ["env_lamp"]
    assert resolution.applied_state_changes == ["environment_state_result"]
    assert resolution.stable_state_summary == "environment_request accepted"
    assert environment_result.result_type == "environment_state_result"
    assert environment_result.target_environment_id == "env_lamp"
    assert environment_result.current_state == "alerted"
    assert environment_result.request_ref == "envreq:2"
    assert environment_result.causation_id == "decision:31"
    assert environment_result.correlation_id == "decision:31"


def test_esm_service_emits_state_machine_transition_for_object_state() -> None:
    service = ESMService()

    transition = service.emit_state_machine_transition(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        entity_id="obj_letter",
        machine_id="visibility",
        from_state="partially_visible",
        to_state="visible",
        trigger_type="interact.inspect",
        transition_reason="player inspect interaction accepted",
        producer_ts=240,
        causation_id="interact:240",
        correlation_id="interact:240",
    )

    assert transition.event_type == "state_machine_transition"
    assert transition.event_id == "transition:visibility:obj_letter:240"
    assert transition.entity_id == "obj_letter"
    assert transition.machine_id == "visibility"
    assert transition.from_state == "partially_visible"
    assert transition.to_state == "visible"
    assert transition.trigger_type == "interact.inspect"
    assert transition.transition_reason == "player inspect interaction accepted"


def test_esm_service_object_state_result_is_replayable() -> None:
    service = ESMService()

    result = service.emit_object_state_result(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        target_object_id="obj_letter",
        previous_state="partially_visible",
        current_state="visible",
        producer_ts=220,
    )

    assert result.result_type == "object_state_result"
    assert result.request_ref == "object:obj_letter:220"
    assert result.result_id == "object_result:obj_letter:220"
    assert result.target_object_id == "obj_letter"
    assert result.previous_state == "partially_visible"
    assert result.current_state == "visible"
    assert result.change_summary == "obj_letter changed from partially_visible to visible"


def test_esm_service_action_resolution_result_is_replayable() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=230,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )
    interaction_result = service.resolve_interaction(event, is_in_range=True)

    result = service.emit_action_resolution_result(event, interaction_result)

    assert result.result_type == "action_resolution_result"
    assert result.request_ref == "interact:230:obj_letter"
    assert result.result_id == "action_resolution:interact:230:obj_letter"
    assert result.target_object_id == "obj_letter"
    assert result.resolution_status == "accepted"
    assert result.resolved_entities == ["obj_letter"]
    assert result.applied_state_changes == [
        "object_state_result",
        "body_state_result",
        "environment_state_result",
    ]
    assert result.stable_state_summary == "interaction accepted"


def test_esm_service_body_state_result_is_replayable() -> None:
    service = ESMService()

    result = service.emit_body_state_result(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        body_state_class="interaction_strain",
        previous_state="steady",
        current_state="engaged",
        producer_ts=231,
    )

    assert result.result_type == "body_state_result"
    assert result.request_ref == "body:char_c:231"
    assert result.result_id == "body_result:char_c:231"
    assert result.actor_id == "char_c"
    assert result.body_state_class == "interaction_strain"
    assert result.previous_state == "steady"
    assert result.current_state == "engaged"
    assert result.change_summary == "interaction_strain changed from steady to engaged"


def test_esm_service_propagates_noise_and_smoke_to_adjacent_zone() -> None:
    service = ESMService()

    service.emit_environment_shift(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        target_environment_id="env_lamp",
        previous_state="stable",
        current_state="alerted",
        producer_ts=300,
    )
    propagated = service.propagate_environment_field_to_adjacent_zones(
        room_id="room_demo",
        scene_id="scene_demo",
        source_zone_id="zone_focus",
        adjacent_zone_ids=["zone_adjacent"],
        producer_ts=301,
    )

    assert propagated["zone_adjacent"].field_id == "field:room_demo:scene_demo:zone_adjacent"
    assert propagated["zone_adjacent"].noise_level == "moderate"
    assert propagated["zone_adjacent"].smoke_density == "trace"
    assert propagated["zone_adjacent"].visibility_level == "soft_reduced"
    assert propagated["zone_adjacent"].updated_at == 301


def test_esm_service_exposes_state_machine_and_material_templates() -> None:
    service = ESMService()

    burning_machine = service.get_state_machine_template("burning")
    lock_machine = service.get_state_machine_template("lock")
    visibility_machine = service.get_state_machine_template("visibility")
    integrity_machine = service.get_state_machine_template("integrity")
    moisture_machine = service.get_state_machine_template("moisture")
    wood_material = service.get_material_template("wood")
    fabric_material = service.get_material_template("fabric")
    metal_material = service.get_material_template("metal")
    glass_material = service.get_material_template("glass")

    assert burning_machine["machine_id"] == "burning"
    assert burning_machine["entity_type"] == "object"
    assert "transition_list" in burning_machine
    assert "entry_effects" in burning_machine
    assert "exit_effects" in burning_machine
    assert "stable_state_tags" in burning_machine
    assert burning_machine["state_list"][0]["state_id"] == "idle"
    assert burning_machine["state_list"][0]["is_stable"] is True
    assert burning_machine["transition_list"][0]["from_state"] == "idle"
    assert burning_machine["transition_list"][0]["to_state"] == "heated"
    assert lock_machine["machine_id"] == "lock"
    assert lock_machine["state_list"][0]["state_id"] == "locked"
    assert visibility_machine["machine_id"] == "visibility"
    assert visibility_machine["state_list"][0]["state_id"] == "hidden"
    assert integrity_machine["machine_id"] == "integrity"
    assert integrity_machine["transition_list"][0]["to_state"] == "disturbed"
    assert moisture_machine["machine_id"] == "moisture"
    assert moisture_machine["state_list"][0]["state_id"] == "dry"
    assert wood_material["material_id"] == "wood"
    assert wood_material["flammability"] == "medium"
    assert fabric_material["material_id"] == "fabric"
    assert fabric_material["smoke_factor"] == "high"
    assert metal_material["material_id"] == "metal"
    assert metal_material["burnable"] is False
    assert glass_material["material_id"] == "glass"
    assert glass_material["visibility_transparency"] == "high"
