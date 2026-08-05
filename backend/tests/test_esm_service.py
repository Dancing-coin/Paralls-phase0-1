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


def test_esm_service_accepts_the_registered_default_scene_plaque_policy() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=12,
        target_object_id="obj_plaque",
        interaction_type="read",
    )

    result = service.resolve_interaction(event, actor_position=(-2.2, 1.2, -1.0))

    assert result.result_type == "action_resolution_result"
    assert service.interaction_policy_for("obj_plaque", "read") == {
        "allowed_interactions": {"inspect", "read"},
        "machine_id": "visibility",
        "previous_state": "partially_visible",
        "current_state": "visible",
        "affordances": ["inspect", "read"],
        "occludes": False,
        "environment_transition": "none",
    }


def test_esm_service_accepts_only_press_for_the_registered_lamp_switch_policy() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=13,
        target_object_id="obj_lamp_switch",
        interaction_type="press",
    )

    result = service.resolve_interaction(event, actor_position=(2.2, 1.2, -1.0))

    assert result.result_type == "action_resolution_result"
    assert service.interaction_policy_for("obj_lamp_switch", "press") == {
        "allowed_interactions": {"press"},
        "machine_id": "switch",
        "previous_state": "idle",
        "current_state": "activated",
        "affordances": ["press"],
        "occludes": False,
        "environment_transition": "alert_lamp",
    }
    assert service.interaction_policy_for("obj_lamp_switch", "inspect") is None

    object_result = service.emit_object_state_result(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        target_object_id="obj_lamp_switch",
        previous_state="idle",
        current_state="activated",
        machine_id="switch",
        producer_ts=14,
    )
    assert object_result.machine_id == "switch"


def test_esm_service_accepts_only_open_for_the_registered_archive_door_policy() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=15,
        target_object_id="obj_archive_door",
        interaction_type="open",
    )

    result = service.resolve_interaction(event, actor_position=(0.0, 1.2, -3.0))

    assert result.result_type == "action_resolution_result"
    assert service.interaction_policy_for("obj_archive_door", "open") == {
        "allowed_interactions": {"open", "close"},
        "machine_id": "door",
        "previous_state": "closed",
        "current_state": "open",
        "affordances": ["open", "close"],
        "occludes": False,
        "environment_transition": "none",
        "initial_state": "closed",
        "stateful": True,
        "state_match": True,
    }


def test_esm_service_accepts_stateful_use_and_finish_use_for_the_registered_worktable_policy() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=15,
        target_object_id="obj_worktable",
        interaction_type="use",
    )

    result = service.resolve_interaction(event, actor_position=(-0.9, 0.85, -1.0))

    assert result.result_type == "action_resolution_result"
    assert service.interaction_policy_for("obj_worktable", "use") == {
        "allowed_interactions": {"use", "finish_use"},
        "machine_id": "work_surface",
        "previous_state": "ready",
        "current_state": "engaged",
        "affordances": ["use", "finish_use"],
        "occludes": False,
        "environment_transition": "none",
        "initial_state": "ready",
        "stateful": True,
        "state_match": True,
    }


def test_esm_service_worktable_policy_requires_authority_committed_state_before_finish_use() -> None:
    service = ESMService()
    use_policy = service.interaction_policy_for(
        "obj_worktable",
        "use",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
    )
    premature_finish_policy = service.interaction_policy_for(
        "obj_worktable",
        "finish_use",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
    )

    assert use_policy is not None
    assert use_policy["state_match"] is True
    assert premature_finish_policy is not None
    assert premature_finish_policy["previous_state"] == "engaged"
    assert premature_finish_policy["current_state"] == "ready"
    assert premature_finish_policy["state_match"] is False

    service.commit_interaction_state(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        target_object_id="obj_worktable",
        current_state="engaged",
    )
    finish_policy = service.interaction_policy_for(
        "obj_worktable",
        "finish_use",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
    )
    repeated_use_policy = service.interaction_policy_for(
        "obj_worktable",
        "use",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
    )
    assert finish_policy is not None
    assert finish_policy["state_match"] is True
    assert repeated_use_policy is not None
    assert repeated_use_policy["state_match"] is False


def test_esm_service_observation_bench_requires_the_authority_scoped_occupant() -> None:
    service = ESMService()
    sit_policy = service.interaction_policy_for(
        "obj_observation_bench",
        "sit",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
    )
    premature_stand_policy = service.interaction_policy_for(
        "obj_observation_bench",
        "stand",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
    )

    assert sit_policy is not None
    assert sit_policy["state_match"] is True
    assert sit_policy["owner_match"] is True
    assert sit_policy["body_state_class"] == "posture"
    assert premature_stand_policy is not None
    assert premature_stand_policy["state_match"] is False

    service.commit_interaction_state(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        target_object_id="obj_observation_bench",
        current_state="occupied",
        actor_id="char_c",
        interaction_type="sit",
    )
    owner_stand_policy = service.interaction_policy_for(
        "obj_observation_bench",
        "stand",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
    )
    other_actor_stand_policy = service.interaction_policy_for(
        "obj_observation_bench",
        "stand",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_a",
    )

    assert service.interaction_owner_for(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        target_object_id="obj_observation_bench",
    ) == "char_c"
    assert owner_stand_policy is not None
    assert owner_stand_policy["state_match"] is True
    assert owner_stand_policy["owner_match"] is True
    assert other_actor_stand_policy is not None
    assert other_actor_stand_policy["state_match"] is True
    assert other_actor_stand_policy["owner_match"] is False

    service.commit_interaction_state(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        target_object_id="obj_observation_bench",
        current_state="available",
        actor_id="char_c",
        interaction_type="stand",
    )
    assert service.interaction_owner_for(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        target_object_id="obj_observation_bench",
    ) == ""


def test_esm_service_door_policy_requires_authority_committed_state_before_close() -> None:
    service = ESMService()
    open_policy = service.interaction_policy_for(
        "obj_archive_door",
        "open",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
    )
    premature_close_policy = service.interaction_policy_for(
        "obj_archive_door",
        "close",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
    )

    assert open_policy is not None
    assert open_policy["state_match"] is True
    assert premature_close_policy is not None
    assert premature_close_policy["previous_state"] == "open"
    assert premature_close_policy["current_state"] == "closed"
    assert premature_close_policy["state_match"] is False

    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=16,
        target_object_id="obj_archive_door",
        interaction_type="close",
    )
    rejected = service.reject_interaction_state(event, expected_state="open", actual_state="closed")
    assert rejected.constraint_type == "interaction_state_constraint"
    assert rejected.constraint_code == "invalid_interaction_state"

    service.commit_interaction_state(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        target_object_id="obj_archive_door",
        current_state="open",
    )
    close_policy = service.interaction_policy_for(
        "obj_archive_door",
        "close",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
    )
    repeated_open_policy = service.interaction_policy_for(
        "obj_archive_door",
        "open",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
    )
    assert close_policy is not None
    assert close_policy["state_match"] is True
    assert repeated_open_policy is not None
    assert repeated_open_policy["state_match"] is False


def test_esm_service_rejects_unregistered_or_unsupported_interactions() -> None:
    service = ESMService()
    unknown_target = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=13,
        target_object_id="obj_unreviewed_mesh",
        interaction_type="inspect",
    )
    unsupported_action = unknown_target.model_copy(update={"target_object_id": "obj_plaque", "interaction_type": "grab"})

    unknown_result = service.reject_unsupported_interaction(unknown_target)
    unsupported_result = service.reject_unsupported_interaction(unsupported_action)

    assert unknown_result.constraint_code == "unsupported_object"
    assert unsupported_result.constraint_code == "unsupported_interaction"


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
    assert result.entity_id == "obj_letter"
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
    assert result.entity_id == "obj_letter"
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
    assert result.entity_id == "env_lamp"
    assert result.actor_id == "char_c"
    assert result.scene_id == "scene_demo"
    assert result.zone_id == "zone_focus"
    assert result.machine_id == "light_source"
    assert result.causation_id == "env:env_lamp:alerted"
    assert result.correlation_id == "env:env_lamp:alerted"
    assert result.settlement_status == "applied"
    assert result.affected_zone_ids == ["zone_focus"]
    assert result.field_delta_summary == [
        "light_level",
        "noise_level",
        "thermal_level",
        "smoke_density",
        "visibility_level",
    ]
    assert result.field_id == "field:room_demo:scene_demo:zone_focus"
    assert result.source_environment_id == "env_lamp"
    assert result.light_level == "low"
    assert result.noise_level == "elevated"
    assert result.thermal_level == "warm"
    assert result.smoke_density == "light"
    assert result.visibility_level == "reduced"
    assert result.updated_at == result.producer_ts

    field = service.get_environment_field("room_demo", "zone_focus")
    assert field.field_id == "field:room_demo:scene_demo:zone_focus"
    assert field.scene_id == "scene_demo"
    assert field.light_level == "low"
    assert field.noise_level == "elevated"
    assert field.thermal_level == "warm"
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
    assert resolution.entity_id == "env_lamp"
    assert resolution.resolution_status == "accepted"
    assert resolution.resolved_entities == ["env_lamp"]
    assert resolution.applied_state_changes == ["environment_state_result"]
    assert resolution.stable_state_summary == "environment_request accepted"
    assert environment_result.result_type == "environment_state_result"
    assert environment_result.entity_id == "env_lamp"
    assert environment_result.target_environment_id == "env_lamp"
    assert environment_result.machine_id == "light_source"
    assert environment_result.field_id == "field:room_demo:scene_demo:zone_focus"
    assert environment_result.source_environment_id == "env_lamp"
    assert environment_result.current_state == "alerted"
    assert environment_result.request_ref == "envreq:2"
    assert environment_result.causation_id == "decision:31"
    assert environment_result.correlation_id == "decision:31"


def test_esm_service_accepts_light_restore_environment_request_and_emits_restored_environment_result() -> None:
    service = ESMService()
    drop_event = EnvironmentRequest(
        request_id="envreq:2a-drop",
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
        reason_tag="window",
        producer_ts=31,
        causation_id="decision:31a-drop",
        correlation_id="decision:31a-drop",
    )
    service.resolve_environment_request(drop_event)
    restore_event = EnvironmentRequest(
        request_id="envreq:2a-restore",
        candidate_ref="cand_light_restore",
        decision_ref="decision_light_restore",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L3", "system": "siming.orchestrator", "actor_id": ""},
        target_entity_refs={"actor_ids": [], "object_ids": [], "environment_ids": ["env_lamp"]},
        goal="restore visibility near the letter",
        requested_change_type="light_level_restore",
        requested_strength="medium",
        ttl=1500,
        reason_tag="window",
        producer_ts=32,
        causation_id="decision:32a-restore",
        correlation_id="decision:32a-restore",
    )

    resolution, environment_result = service.resolve_environment_request(restore_event)

    assert resolution.result_type == "action_resolution_result"
    assert resolution.request_ref == "envreq:2a-restore"
    assert resolution.entity_id == "env_lamp"
    assert resolution.resolution_status == "accepted"
    assert environment_result is not None
    assert environment_result.result_type == "environment_state_result"
    assert environment_result.machine_id == "light_source"
    assert environment_result.previous_state == "alerted"
    assert environment_result.current_state == "stable"
    assert environment_result.light_level == "normal"
    assert environment_result.noise_level == "quiet"
    assert environment_result.thermal_level == "neutral"
    assert environment_result.smoke_density == "clear"
    assert environment_result.visibility_level == "clear"


def test_esm_service_accepts_thermal_environment_request_and_emits_heated_environment_result() -> None:
    service = ESMService()
    event = EnvironmentRequest(
        request_id="envreq:2b",
        candidate_ref="cand_heat_rise",
        decision_ref="decision_heat_rise",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L3", "system": "siming.orchestrator", "actor_id": ""},
        target_entity_refs={"actor_ids": [], "object_ids": [], "environment_ids": ["env_lamp"]},
        goal="raise thermal pressure near the letter",
        requested_change_type="thermal_level_rise",
        requested_strength="medium",
        ttl=1500,
        reason_tag="pressure_window",
        producer_ts=31,
        causation_id="decision:31b",
        correlation_id="decision:31b",
    )

    resolution, environment_result = service.resolve_environment_request(event)

    assert resolution.result_type == "action_resolution_result"
    assert resolution.request_ref == "envreq:2b"
    assert resolution.entity_id == "env_lamp"
    assert resolution.resolution_status == "accepted"
    assert resolution.applied_state_changes == ["environment_state_result"]
    assert resolution.stable_state_summary == "environment_request accepted"
    assert environment_result is not None
    assert environment_result.result_type == "environment_state_result"
    assert environment_result.machine_id == "heat_source"
    assert environment_result.request_ref == "envreq:2b"
    assert environment_result.current_state == "heated"
    assert environment_result.thermal_level == "hot"
    assert environment_result.light_level == "normal"
    assert environment_result.noise_level == "quiet"
    assert environment_result.visibility_level == "clear"


def test_esm_service_accepts_smoke_environment_request_and_emits_smoke_environment_result() -> None:
    service = ESMService()
    event = EnvironmentRequest(
        request_id="envreq:2c",
        candidate_ref="cand_smoke_rise",
        decision_ref="decision_smoke_rise",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L3", "system": "siming.orchestrator", "actor_id": ""},
        target_entity_refs={"actor_ids": [], "object_ids": [], "environment_ids": ["env_lamp"]},
        goal="raise smoke density near the letter",
        requested_change_type="smoke_density_rise",
        requested_strength="medium",
        ttl=1500,
        reason_tag="cover_window",
        producer_ts=31,
        causation_id="decision:31c",
        correlation_id="decision:31c",
    )

    resolution, environment_result = service.resolve_environment_request(event)

    assert resolution.result_type == "action_resolution_result"
    assert resolution.request_ref == "envreq:2c"
    assert resolution.entity_id == "env_lamp"
    assert resolution.resolution_status == "accepted"
    assert resolution.applied_state_changes == ["environment_state_result"]
    assert environment_result is not None
    assert environment_result.result_type == "environment_state_result"
    assert environment_result.machine_id == "smoke_source"
    assert environment_result.request_ref == "envreq:2c"
    assert environment_result.current_state == "smoke_rising"
    assert environment_result.smoke_density == "dense"
    assert environment_result.visibility_level == "reduced"
    assert environment_result.light_level == "normal"
    assert environment_result.noise_level == "quiet"
    assert environment_result.thermal_level == "neutral"


def test_esm_service_accepts_noise_environment_request_and_emits_noise_environment_result() -> None:
    service = ESMService()
    event = EnvironmentRequest(
        request_id="envreq:2d",
        candidate_ref="cand_noise_rise",
        decision_ref="decision_noise_rise",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L3", "system": "siming.orchestrator", "actor_id": ""},
        target_entity_refs={"actor_ids": [], "object_ids": [], "environment_ids": ["env_lamp"]},
        goal="raise noise level near the letter",
        requested_change_type="noise_level_rise",
        requested_strength="medium",
        ttl=1500,
        reason_tag="mask_window",
        producer_ts=31,
        causation_id="decision:31d",
        correlation_id="decision:31d",
    )

    resolution, environment_result = service.resolve_environment_request(event)

    assert resolution.result_type == "action_resolution_result"
    assert resolution.request_ref == "envreq:2d"
    assert resolution.entity_id == "env_lamp"
    assert resolution.resolution_status == "accepted"
    assert resolution.applied_state_changes == ["environment_state_result"]
    assert environment_result is not None
    assert environment_result.result_type == "environment_state_result"
    assert environment_result.machine_id == "noise_source"
    assert environment_result.request_ref == "envreq:2d"
    assert environment_result.current_state == "noisy"
    assert environment_result.noise_level == "loud"
    assert environment_result.light_level == "normal"
    assert environment_result.thermal_level == "neutral"
    assert environment_result.smoke_density == "clear"
    assert environment_result.visibility_level == "clear"


def test_esm_service_rejects_unsupported_environment_request_change_type() -> None:
    service = ESMService()
    event = EnvironmentRequest(
        request_id="envreq:3",
        candidate_ref="cand_heat_rise",
        decision_ref="decision_heat_rise",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L3", "system": "siming.orchestrator", "actor_id": ""},
        target_entity_refs={"actor_ids": [], "object_ids": [], "environment_ids": ["env_lamp"]},
        goal="raise thermal pressure near the letter",
        requested_change_type="thermal_spike",
        requested_strength="medium",
        ttl=1500,
        reason_tag="pressure_test",
        producer_ts=32,
        causation_id="decision:32",
        correlation_id="decision:32",
    )

    resolution, environment_result = service.resolve_environment_request(event)

    assert resolution.result_type == "constraint_state_result"
    assert resolution.request_ref == "envreq:3"
    assert resolution.entity_id == "env_lamp"
    assert resolution.constraint_type == "unsupported_environment_request"
    assert resolution.constraint_code == "unsupported_change_type"
    assert resolution.settlement_status == "rejected"
    assert resolution.blocking_entity_refs == ["env_lamp"]
    assert environment_result is None


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
        request_ref="interact:220:obj_letter",
        causation_id="interact:220",
        correlation_id="interact:220",
    )

    assert result.result_type == "object_state_result"
    assert result.request_ref == "interact:220:obj_letter"
    assert result.result_id == "object_result:obj_letter:220"
    assert result.entity_id == "obj_letter"
    assert result.target_object_id == "obj_letter"
    assert result.machine_id == "visibility"
    assert result.causation_id == "interact:220"
    assert result.correlation_id == "interact:220"
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
    assert result.entity_id == "obj_letter"
    assert result.target_object_id == "obj_letter"
    assert result.resolution_status == "accepted"
    assert result.resolved_entities == ["obj_letter"]
    assert result.applied_state_changes == [
        "object_state_result",
        "body_state_result",
        "environment_state_result",
    ]
    assert result.stable_state_summary == "interaction accepted"


def test_visible_letter_can_be_destroyed_by_authority() -> None:
    service = ESMService()
    service.commit_interaction_state(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        target_object_id="obj_letter",
        current_state="visible",
    )

    policy = service.interaction_policy_for(
        "obj_letter",
        "destroy",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
    )

    assert policy is not None
    assert policy["previous_state"] == "visible"
    assert policy["current_state"] == "removed_from_surface"
    assert policy["state_match"] is True


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
        request_ref="interact:231:obj_letter",
        causation_id="interact:231",
        correlation_id="interact:231",
    )

    assert result.result_type == "body_state_result"
    assert result.request_ref == "interact:231:obj_letter"
    assert result.result_id == "body_result:char_c:231"
    assert result.actor_id == "char_c"
    assert result.body_state_class == "interaction_strain"
    assert result.causation_id == "interact:231"
    assert result.correlation_id == "interact:231"
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
    assert propagated["zone_adjacent"].thermal_level == "mild_warm"
    assert propagated["zone_adjacent"].smoke_density == "trace"
    assert propagated["zone_adjacent"].visibility_level == "soft_reduced"
    assert propagated["zone_adjacent"].updated_at == 301


def test_esm_service_exposes_state_machine_and_material_templates() -> None:
    service = ESMService()

    burning_machine = service.get_state_machine_template("burning")
    light_source_machine = service.get_state_machine_template("light_source")
    heat_source_machine = service.get_state_machine_template("heat_source")
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
    assert light_source_machine["machine_id"] == "light_source"
    assert light_source_machine["entity_type"] == "environment"
    assert light_source_machine["state_list"][0]["state_id"] == "stable"
    assert light_source_machine["transition_list"][0]["to_state"] == "alerted"
    assert light_source_machine["transition_list"][1]["from_state"] == "alerted"
    assert light_source_machine["transition_list"][1]["to_state"] == "stable"
    assert heat_source_machine["machine_id"] == "heat_source"
    assert heat_source_machine["entity_type"] == "environment"
    assert heat_source_machine["state_list"][0]["state_id"] == "stable"
    assert heat_source_machine["transition_list"][0]["to_state"] == "heated"
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


def test_esm_service_exposes_repo_local_capability_manifest() -> None:
    service = ESMService()

    capabilities = service.get_repo_local_capabilities()

    assert capabilities["supported_settlement_classes"] == [
        "interaction_success",
        "interaction_rejection_by_constraint",
        "environment_state_shift",
    ]
    assert capabilities["supported_constraint_classes"] == [
        "distance_constraint",
        "unsupported_environment_request",
    ]
    assert capabilities["supported_environment_change_types"] == [
        "light_level_drop",
        "light_level_restore",
        "noise_level_rise",
        "smoke_density_rise",
        "thermal_level_rise",
    ]
    assert capabilities["unsupported_environment_change_types"] == ["thermal_spike"]
    assert capabilities["supported_environment_fields"] == [
        "light_level",
        "noise_level",
        "thermal_level",
        "smoke_density",
        "visibility_level",
    ]
    assert capabilities["environment_field_semantics"]["thermal_level"] == "real_but_coarse"
    assert capabilities["environment_request_policy"]["unsupported_change_type_behavior"] == "reject_constraint_state_result"
    assert capabilities["environment_request_variant_policy"]["supported_families"] == [
        "visibility_change",
        "thermal_change",
        "smoke_change",
    ]
    assert capabilities["environment_request_variant_policy"]["unsupported_families"] == [
        "humidity_change",
        "integrity_change",
        "material_change",
    ]
    assert capabilities["environment_request_variant_policy"]["current_supported_change_types"] == [
        "light_level_drop",
        "light_level_restore",
        "noise_level_rise",
        "smoke_density_rise",
        "thermal_level_rise",
    ]


def test_esm_service_exposes_environment_machine_catalog_for_debug_surfaces() -> None:
    service = ESMService()

    capabilities = service.get_repo_local_capabilities()

    assert capabilities["environment_machine_ids"] == ["heat_source", "light_source", "noise_source", "smoke_source"]


def test_esm_service_exposes_repo_local_workbench_snapshot() -> None:
    service = ESMService()
    event = EnvironmentRequest(
        request_id="envreq:workbench",
        candidate_ref="cand_heat_rise",
        decision_ref="decision_heat_rise",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L3", "system": "siming.orchestrator", "actor_id": ""},
        target_entity_refs={"actor_ids": [], "object_ids": [], "environment_ids": ["env_lamp"]},
        goal="raise thermal pressure near the letter",
        requested_change_type="thermal_level_rise",
        requested_strength="medium",
        ttl=1500,
        reason_tag="pressure_window",
        producer_ts=41,
        causation_id="decision:41",
        correlation_id="decision:41",
    )
    resolution, environment_result = service.resolve_environment_request(event)
    transition = service.emit_state_machine_transition(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        entity_id="env_lamp",
        machine_id="heat_source",
        from_state="stable",
        to_state="heated",
        trigger_type="environment_request.thermal_level_rise",
        transition_reason="environment request accepted",
        producer_ts=43,
        causation_id="decision:41",
        correlation_id="decision:41",
    )

    snapshot = service.get_repo_local_workbench_snapshot(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
    )

    assert snapshot["room_id"] == "room_demo"
    assert snapshot["scene_id"] == "scene_demo"
    assert snapshot["zone_id"] == "zone_focus"
    assert snapshot["state_machine_template_ids"] == [
        "burning",
        "heat_source",
        "integrity",
        "light_source",
        "lock",
        "moisture",
        "noise_source",
        "smoke_source",
        "visibility",
    ]
    assert snapshot["material_template_ids"] == ["fabric", "glass", "metal", "wood"]
    assert snapshot["environment_machine_ids"] == ["heat_source", "light_source", "noise_source", "smoke_source"]
    assert snapshot["supported_environment_change_types"] == [
        "light_level_drop",
        "light_level_restore",
        "noise_level_rise",
        "smoke_density_rise",
        "thermal_level_rise",
    ]
    assert snapshot["unsupported_environment_change_types"] == ["thermal_spike"]
    assert snapshot["current_environment_field"]["field_id"] == "field:room_demo:scene_demo:zone_focus"
    assert snapshot["current_environment_field"]["source_environment_id"] == "env_lamp"
    assert snapshot["current_environment_field"]["thermal_level"] == "hot"
    assert snapshot["latest_environment_result"]["result_id"] == environment_result.result_id
    assert snapshot["latest_environment_result"]["machine_id"] == "heat_source"
    assert snapshot["latest_environment_result"]["current_state"] == "heated"
    assert snapshot["latest_state_machine_transition"]["event_id"] == transition.event_id
    assert snapshot["latest_state_machine_transition"]["machine_id"] == "heat_source"
    assert snapshot["latest_state_machine_transition"]["to_state"] == "heated"
    assert snapshot["latest_environment_request"]["request_id"] == "envreq:workbench"
    assert snapshot["latest_environment_resolution"]["result_id"] == resolution.result_id


def test_esm_service_workbench_snapshot_keeps_latest_request_and_resolution_even_when_last_request_is_rejected() -> None:
    service = ESMService()
    accepted_event = EnvironmentRequest(
        request_id="envreq:accepted",
        candidate_ref="cand_heat_rise",
        decision_ref="decision_heat_rise",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L3", "system": "siming.orchestrator", "actor_id": ""},
        target_entity_refs={"actor_ids": [], "object_ids": [], "environment_ids": ["env_lamp"]},
        goal="raise thermal pressure near the letter",
        requested_change_type="thermal_level_rise",
        requested_strength="medium",
        ttl=1500,
        reason_tag="pressure_window",
        producer_ts=51,
        causation_id="decision:51",
        correlation_id="decision:51",
    )
    accepted_resolution, accepted_environment_result = service.resolve_environment_request(accepted_event)
    accepted_transition = service.emit_state_machine_transition(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        entity_id="env_lamp",
        machine_id="heat_source",
        from_state="stable",
        to_state="heated",
        trigger_type="environment_request.thermal_level_rise",
        transition_reason="environment request accepted",
        producer_ts=53,
        causation_id="decision:51",
        correlation_id="decision:51",
    )
    rejected_event = EnvironmentRequest(
        request_id="envreq:rejected",
        candidate_ref="cand_bad",
        decision_ref="decision_bad",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L3", "system": "siming.orchestrator", "actor_id": ""},
        target_entity_refs={"actor_ids": [], "object_ids": [], "environment_ids": ["env_lamp"]},
        goal="force unsupported environment mutation",
        requested_change_type="thermal_spike",
        requested_strength="medium",
        ttl=1500,
        reason_tag="pressure_window",
        producer_ts=54,
        causation_id="decision:54",
        correlation_id="decision:54",
    )
    rejected_resolution, rejected_environment_result = service.resolve_environment_request(rejected_event)

    snapshot = service.get_repo_local_workbench_snapshot(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
    )

    assert accepted_resolution.result_type == "action_resolution_result"
    assert accepted_environment_result is not None
    assert rejected_resolution.result_type == "constraint_state_result"
    assert rejected_environment_result is None
    assert snapshot["latest_environment_request"]["request_id"] == "envreq:rejected"
    assert snapshot["latest_environment_request"]["action_profile"] == "thermal_spike"
    assert snapshot["latest_environment_resolution"]["result_type"] == "constraint_state_result"
    assert snapshot["latest_environment_resolution"]["constraint_type"] == "unsupported_environment_request"
    assert snapshot["latest_environment_result"]["result_id"] == accepted_environment_result.result_id
    assert snapshot["latest_state_machine_transition"]["event_id"] == accepted_transition.event_id


def test_esm_service_workbench_snapshot_exposes_recent_history_window() -> None:
    service = ESMService()
    first_event = EnvironmentRequest(
        request_id="envreq:h1",
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
        reason_tag="window",
        producer_ts=61,
        causation_id="decision:61",
        correlation_id="decision:61",
    )
    second_event = EnvironmentRequest(
        request_id="envreq:h2",
        candidate_ref="cand_heat_rise",
        decision_ref="decision_heat_rise",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L3", "system": "siming.orchestrator", "actor_id": ""},
        target_entity_refs={"actor_ids": [], "object_ids": [], "environment_ids": ["env_lamp"]},
        goal="raise thermal pressure near the letter",
        requested_change_type="thermal_level_rise",
        requested_strength="medium",
        ttl=1500,
        reason_tag="window",
        producer_ts=62,
        causation_id="decision:62",
        correlation_id="decision:62",
    )
    third_event = EnvironmentRequest(
        request_id="envreq:h3",
        candidate_ref="cand_smoke_rise",
        decision_ref="decision_smoke_rise",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L3", "system": "siming.orchestrator", "actor_id": ""},
        target_entity_refs={"actor_ids": [], "object_ids": [], "environment_ids": ["env_lamp"]},
        goal="raise smoke density near the letter",
        requested_change_type="smoke_density_rise",
        requested_strength="medium",
        ttl=1500,
        reason_tag="window",
        producer_ts=63,
        causation_id="decision:63",
        correlation_id="decision:63",
    )
    fourth_event = EnvironmentRequest(
        request_id="envreq:h4",
        candidate_ref="cand_noise_rise",
        decision_ref="decision_noise_rise",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L3", "system": "siming.orchestrator", "actor_id": ""},
        target_entity_refs={"actor_ids": [], "object_ids": [], "environment_ids": ["env_lamp"]},
        goal="raise noise level near the letter",
        requested_change_type="noise_level_rise",
        requested_strength="medium",
        ttl=1500,
        reason_tag="window",
        producer_ts=64,
        causation_id="decision:64",
        correlation_id="decision:64",
    )

    first_resolution, first_result = service.resolve_environment_request(first_event)
    service.emit_state_machine_transition(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        entity_id="env_lamp",
        machine_id="light_source",
        from_state="stable",
        to_state="alerted",
        trigger_type="environment_request.light_level_drop",
        transition_reason="environment request accepted",
        producer_ts=64,
        causation_id="decision:61",
        correlation_id="decision:61",
    )
    second_resolution, second_result = service.resolve_environment_request(second_event)
    service.emit_state_machine_transition(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        entity_id="env_lamp",
        machine_id="heat_source",
        from_state="stable",
        to_state="heated",
        trigger_type="environment_request.thermal_level_rise",
        transition_reason="environment request accepted",
        producer_ts=65,
        causation_id="decision:62",
        correlation_id="decision:62",
    )
    third_resolution, third_result = service.resolve_environment_request(third_event)
    third_transition = service.emit_state_machine_transition(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        entity_id="env_lamp",
        machine_id="smoke_source",
        from_state="stable",
        to_state="smoke_rising",
        trigger_type="environment_request.smoke_density_rise",
        transition_reason="environment request accepted",
        producer_ts=66,
        causation_id="decision:63",
        correlation_id="decision:63",
    )
    fourth_resolution, fourth_result = service.resolve_environment_request(fourth_event)
    fourth_transition = service.emit_state_machine_transition(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        entity_id="env_lamp",
        machine_id="noise_source",
        from_state="stable",
        to_state="noisy",
        trigger_type="environment_request.noise_level_rise",
        transition_reason="environment request accepted",
        producer_ts=67,
        causation_id="decision:64",
        correlation_id="decision:64",
    )

    snapshot = service.get_repo_local_workbench_snapshot(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
    )

    assert first_resolution.result_type == "action_resolution_result"
    assert first_result is not None
    assert second_resolution.result_type == "action_resolution_result"
    assert second_result is not None
    assert third_resolution.result_type == "action_resolution_result"
    assert third_result is not None
    assert fourth_resolution.result_type == "action_resolution_result"
    assert fourth_result is not None
    assert snapshot["recent_environment_requests"][0]["request_id"] == "envreq:h3"
    assert snapshot["recent_environment_requests"][1]["request_id"] == "envreq:h4"
    assert snapshot["recent_environment_resolutions"][0]["result_id"] == third_resolution.result_id
    assert snapshot["recent_environment_resolutions"][1]["result_id"] == fourth_resolution.result_id
    assert snapshot["recent_environment_results"][0]["result_id"] == third_result.result_id
    assert snapshot["recent_environment_results"][1]["result_id"] == fourth_result.result_id
    assert snapshot["recent_state_machine_transitions"][0]["event_id"] == third_transition.event_id
    assert snapshot["recent_state_machine_transitions"][1]["event_id"] == fourth_transition.event_id
