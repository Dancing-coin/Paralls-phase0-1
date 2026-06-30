import app.main as app_main
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.models.character_perceived import CharacterPerceivedEvent
from app.models.siming_character_bridge import SimingCharacterCompatibilityInput
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.main import _handle_envelope, reset_runtime_state
from app.ws_protocol import Envelope
from pathlib import Path
from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle

_STAGE2_MEMORY_KEYS = {
    "working_memory",
    "event_memories",
    "observation_memories",
    "knowledge_memories",
    "social_memories",
    "higher_order_memories",
}
_COMPATIBILITY_MEMORY_ALIAS_KEYS = {
    "episodic_memories",
    "relational_memories",
}


class _LocalGateway:
    def __init__(self) -> None:
        self._gateway = CharacterModelGateway()

    def run_task(
        self,
        *,
        task_kind: str,
        context: dict[str, object],
        route_override: str | None = None,
    ) -> dict[str, object]:
        return self._gateway.run_task(
            task_kind=task_kind,
            context=context,
            route_override=route_override or "local_only",
        )

    def prepare_run_request(
        self,
        *,
        task_kind: str,
        context: dict[str, object],
        route_override: str | None = None,
    ) -> dict[str, object]:
        return self._gateway.prepare_run_request(
            task_kind=task_kind,
            context=context,
            route_override=route_override or "local_only",
        )


def _local_runtime(storage_root: Path | None = None) -> CharacterAgentRuntime:
    runtime = CharacterAgentRuntime(storage_root=storage_root)
    local_gateway = _LocalGateway()
    runtime._l2 = CharacterAgentL2Service(gateway=local_gateway, profile_registry=runtime._profile_registry)
    runtime._l3 = CharacterAgentL3Service(gateway=local_gateway)
    return runtime


def _reset_runtime_state_with_local_character_model() -> None:
    reset_runtime_state()
    runtime = _local_runtime()
    app_main.character_agent_runtime = runtime
    app_main.siming_event_pipeline._character_dispatch_adapter._runtime = runtime


def _assert_stage2_memory_bundle_contract(bundle: dict[str, object]) -> None:
    assert _STAGE2_MEMORY_KEYS.issubset(bundle.keys())
    assert set(bundle.keys()) <= _STAGE2_MEMORY_KEYS | _COMPATIBILITY_MEMORY_ALIAS_KEYS

    if "episodic_memories" in bundle:
        assert isinstance(bundle["episodic_memories"], list)
    if "relational_memories" in bundle:
        assert isinstance(bundle["relational_memories"], list)


def test_runtime_writes_character_perceived_event_into_session_timeline() -> None:
    runtime = _local_runtime()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=1201,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:1201:char_a",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    runtime.ingest_character_perceived_event(event)
    timeline = runtime.get_session_timeline("char_a")

    assert len(timeline) == 5
    assert timeline[0]["event_type"] == "character_perceived_event"
    assert timeline[0]["payload"]["summary"] == "visual_fact/fixed_gaze_on_target"
    assert timeline[1]["event_type"] == "l2_reasoning_request"
    assert timeline[2]["event_type"] == "character_interpretation_event"
    assert timeline[3]["event_type"] == "goal_state_event"
    assert timeline[4]["event_type"] == "character_agent_execution_request"


def test_runtime_writes_self_body_event_into_working_memory_bundle() -> None:
    runtime = _local_runtime()
    event = SelfBodyPerceivedEvent(
        actor_id="char_b",
        body_state_class="interaction_strain",
        producer_ts=1202,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="body_state_result/interaction_strain=engaged",
        source_body_result_id="body_result:char_b:1202",
    )

    runtime.ingest_self_body_perceived_event(event)
    bundle = runtime.get_memory_bundle("char_b")

    assert bundle["working_memory"]
    assert bundle["working_memory"][0]["event_type"] == "self_body_perceived_event"


def test_runtime_builds_stage2_memory_pools_from_character_perceived_events() -> None:
    runtime = _local_runtime()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="auditory",
        producer_ts=1203,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:1203:char_a",
        clarity_score=0.75,
        certainty_score=0.6,
    )

    runtime.ingest_character_perceived_event(event)
    bundle = runtime.get_memory_bundle("char_a")

    _assert_stage2_memory_bundle_contract(bundle)
    assert bundle["event_memories"]
    assert bundle["event_memories"][0]["summary"] == "auditory_fact/speaker_active"
    assert bundle["observation_memories"]
    assert bundle["observation_memories"][0]["observation_summary"] == "auditory_fact/speaker_active"
    if "episodic_memories" in bundle:
        assert bundle["episodic_memories"]
        assert bundle["episodic_memories"][0]["summary"] == bundle["event_memories"][0]["summary"]
    if "relational_memories" in bundle:
        assert bundle["relational_memories"] == []


def test_runtime_accepts_new_nonvisual_modalities_into_private_snapshot_and_memory() -> None:
    runtime = _local_runtime()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="thermal",
        producer_ts=1203,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="thermal_fact/thermal_proximity_changed",
        source_candidate_event_id="thermal_fact:1203:char_a",
        target_object_id="obj_letter",
        clarity_score=0.72,
        certainty_score=0.58,
    )

    runtime.ingest_character_perceived_event(event)
    snapshot = runtime.get_private_snapshot("char_a")
    bundle = runtime.get_memory_bundle("char_a")

    assert snapshot is not None
    assert snapshot.thermal_entities == ["thermal_fact/thermal_proximity_changed"]
    assert snapshot.partial_observations == ["thermal_fact/thermal_proximity_changed"]
    assert bundle["event_memories"][0]["summary"] == "thermal_fact/thermal_proximity_changed"
    assert bundle["observation_memories"][0]["observation_type"] == "thermal"


def test_runtime_records_l2_reasoning_request_and_interpretation_events() -> None:
    runtime = _local_runtime()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=1204,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:1204:char_a",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    runtime.ingest_character_perceived_event(event)
    timeline = runtime.get_session_timeline("char_a")

    event_types = [entry["event_type"] for entry in timeline]
    assert "l2_reasoning_request" in event_types
    assert "character_interpretation_event" in event_types


def test_runtime_reasoning_request_coexists_with_stage2_memory_bundle() -> None:
    runtime = _local_runtime()

    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="auditory",
            producer_ts=1205,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="auditory_fact/speaker_active",
            source_candidate_event_id="auditory_fact:1205:char_a",
            clarity_score=0.8,
            certainty_score=0.65,
        )
    )
    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=1206,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="visual_fact/fixed_gaze_on_target",
            source_candidate_event_id="visual_fact:1206:char_a",
            clarity_score=1.0,
            certainty_score=1.0,
        )
    )

    timeline = runtime.get_session_timeline("char_a")
    bundle = runtime.get_memory_bundle("char_a")
    reasoning_requests = [entry for entry in timeline if entry["event_type"] == "l2_reasoning_request"]

    assert reasoning_requests
    latest_request = reasoning_requests[-1]
    _assert_stage2_memory_bundle_contract(bundle)
    assert bundle["event_memories"]
    assert bundle["observation_memories"]
    if "episodic_memories" in bundle:
        assert bundle["episodic_memories"]
        assert bundle["episodic_memories"][0]["summary"] == bundle["event_memories"][0]["summary"]
    if "relational_memories" in bundle:
        assert bundle["relational_memories"] == []
    state = latest_request["payload"]["context"]["working_memory_state"]
    assert state["recent_perceived_events"]
    assert "episodic_memories" not in state
    assert "event_memories" not in state
    assert "observation_memories" not in state
    assert "knowledge_memories" not in state
    assert "relational_memories" not in state
    assert "social_memories" not in state


def test_interact_intent_records_self_body_event_once() -> None:
    import app.main as main

    _reset_runtime_state_with_local_character_model()
    _handle_envelope(
        Envelope(
            message_type="player_input",
            payload={
                "player_id": "p1",
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "actor_id": "char_c",
                "intent_type": "interact_intent",
                "producer_ts": 456,
                "target_object_id": "obj_letter",
                "interaction_type": "inspect",
            },
        )
    )

    timeline = main.character_agent_runtime.get_session_timeline("char_c")

    self_body_events = [entry for entry in timeline if entry["event_type"] == "self_body_perceived_event"]
    l2_requests = [entry for entry in timeline if entry["event_type"] == "l2_reasoning_request"]
    interpretations = [entry for entry in timeline if entry["event_type"] == "character_interpretation_event"]

    assert len(self_body_events) == 1
    assert len(l2_requests) == 1
    assert len(interpretations) == 1


def test_runtime_can_recover_timeline_and_memory_bundle_from_optional_storage_root(tmp_path: Path) -> None:
    runtime = _local_runtime(storage_root=tmp_path)
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=1207,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/object_state_changed",
        source_candidate_event_id="visual_fact:1207:char_a",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    runtime.ingest_character_perceived_event(event)
    reloaded = _local_runtime(storage_root=tmp_path)

    timeline = reloaded.get_session_timeline("char_a")
    bundle = reloaded.get_memory_bundle("char_a")

    assert timeline
    assert any(entry["event_type"] == "character_perceived_event" for entry in timeline)
    assert bundle["working_memory"]
    assert bundle["event_memories"]


def test_runtime_can_rebuild_memory_bundle_from_session_durability_path_only(tmp_path: Path) -> None:
    runtime = _local_runtime(storage_root=tmp_path)
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=1207,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/object_state_changed",
        source_candidate_event_id="visual_fact:1207:char_a",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    runtime.ingest_character_perceived_event(event)
    memory_path = tmp_path / "character_agent_memory_store.json"
    if memory_path.exists():
        memory_path.unlink()
    reloaded = _local_runtime(storage_root=tmp_path)

    timeline = reloaded.get_session_timeline("char_a")
    bundle = reloaded.get_memory_bundle("char_a")

    assert timeline
    assert any(entry["event_type"] == "character_perceived_event" for entry in timeline)
    assert bundle["working_memory"]
    assert bundle["event_memories"]


def test_runtime_can_recover_unresolved_tensions_and_supervision_from_storage_root(tmp_path: Path) -> None:
    runtime = _local_runtime(storage_root=tmp_path)
    runtime.set_background_cognition_enabled(True)
    runtime.set_background_mode("char_a", "active")
    runtime.ingest_siming_output(
        SimingCharacterCompatibilityInput.model_validate(
            {
                "message_id": "msg:siming:storage:1",
                "delivery_id": "delivery:msg:siming:storage:1:char_a:1",
                "actor_id": "char_a",
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "producer_ts": 2201,
                "input_type": "siming_high_level_message",
                "band": "opportunity",
                "presentation_hint": "watch obj_letter",
                "pressure_hint": "crowd closing in",
                "reason_scope": "threat_scan",
                "salience_boost": 0.7,
                "target_actor_id": "char_a",
                "causation_id": "siming:2201",
                "correlation_id": "siming:2201",
            }
        )
    )
    runtime.apply_supervision_authorization(
        {
            "authorization_id": "auth:storage:1",
            "actor_id": "char_a",
            "approved_level": "medium",
            "approved_by": "strategy_service",
            "approval_reason": "persist quiet supervision for reload",
            "constraints": {
                "allow_background_loop": True,
                "background_mode": "quiet",
                "min_tick_interval_ms": 1000,
                "max_tick_budget_tokens": 180,
                "blocked_goal_classes": ["conflict_escalation"],
            },
            "effective_from_ts": 2201,
            "expires_at_ts": 4201,
            "producer_ts": 2201,
        }
    )
    reloaded = _local_runtime(storage_root=tmp_path)

    tensions = reloaded.get_unresolved_tensions("char_a")
    supervision_state = reloaded.get_supervision_state("char_a")

    assert tensions
    assert tensions[0]["category"] == "siming_pressure"
    assert supervision_state["current_level"] == "medium"
    assert supervision_state["active_constraints"]["background_mode"] == "quiet"


def test_runtime_can_recover_background_agenda_state_from_storage_root(tmp_path: Path) -> None:
    runtime = _local_runtime(storage_root=tmp_path)
    runtime.set_background_cognition_enabled(True)
    runtime.set_background_mode("char_a", "active")
    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="auditory",
            producer_ts=2301,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="auditory_fact/metal_click",
            source_candidate_event_id="auditory_fact:2301:char_a",
            target_object_id="obj_letter",
            clarity_score=0.71,
            certainty_score=0.73,
        )
    )
    runtime.apply_supervision_authorization(
        {
            "authorization_id": "auth:agenda:1",
            "actor_id": "char_a",
            "approved_level": "medium",
            "approved_by": "strategy_service",
            "approval_reason": "quiet review window",
            "constraints": {
                "allow_background_loop": True,
                "background_mode": "quiet",
                "min_tick_interval_ms": 1000,
            },
            "effective_from_ts": 2301,
            "expires_at_ts": 4301,
            "producer_ts": 2301,
        }
    )
    runtime.run_background_cognition_tick(actor_id="char_a", producer_ts=3301)
    reloaded = _local_runtime(storage_root=tmp_path)

    agenda_state = reloaded.get_background_agenda_state("char_a")

    assert agenda_state["latent_tendency"]
    assert agenda_state["agenda_phase"] == "quiet"


def test_handle_envelope_can_apply_external_supervision_authorization() -> None:
    _reset_runtime_state_with_local_character_model()

    messages = _handle_envelope(
        Envelope(
            message_type="character_supervision_authorization",
            payload={
                "authorization_id": "auth:envelope:1",
                "actor_id": "char_a",
                "approved_level": "medium",
                "approved_by": "strategy_service",
                "approval_reason": "quiet the room and constrain escalation",
                "constraints": {
                    "allow_background_loop": True,
                    "background_mode": "quiet",
                    "min_tick_interval_ms": 2000,
                    "blocked_goal_classes": ["conflict_escalation"],
                },
                "effective_from_ts": 4000,
                "expires_at_ts": 6000,
                "producer_ts": 4000,
            },
        )
    )

    supervision_state = app_main.character_agent_runtime.get_supervision_state("char_a")

    assert messages[0]["message_type"] == "ack"
    assert messages[1]["message_type"] == "character_supervision_state"
    assert supervision_state["current_level"] == "medium"
    assert supervision_state["active_constraints"]["background_mode"] == "quiet"


def test_runtime_records_l4_execution_request_for_full_auto_actor() -> None:
    runtime = _local_runtime()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=1208,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:1208:char_a",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    runtime.ingest_character_perceived_event(event)
    timeline = runtime.get_session_timeline("char_a")
    observatory_messages = runtime.drain_observatory_messages("char_a")
    execution_events = [
        message["payload"]
        for message in observatory_messages
        if message["message_type"] == "character_agent_debug_event"
        and message["payload"]["stage"] == "execution_request"
    ]

    assert any(entry["event_type"] == "character_agent_execution_request" for entry in timeline)
    assert execution_events


def test_runtime_record_settlement_result_updates_observatory_snapshot_and_event() -> None:
    runtime = _local_runtime()
    runtime.record_settlement_result(
        actor_id="char_a",
        producer_ts=1301,
        payload={
            "result_type": "constraint_state_result",
            "actor_id": "char_a",
            "constraint_summary": "too far from obj_letter",
            "causation_id": "interact:1301",
            "correlation_id": "interact:1301",
        },
    )

    observatory_messages = runtime.drain_observatory_messages("char_a")
    snapshots = [
        message["payload"]
        for message in observatory_messages
        if message["message_type"] == "character_agent_debug_snapshot"
    ]
    settlement_events = [
        message["payload"]
        for message in observatory_messages
        if message["message_type"] == "character_agent_debug_event"
        and message["payload"]["stage"] == "settlement_result"
    ]

    assert settlement_events
    assert settlement_events[-1]["summary"] == "too far from obj_letter"
    assert snapshots[-1]["latest_outcome_summary"] == "too far from obj_letter"


def test_runtime_record_dialogue_response_updates_observatory_snapshot_and_event() -> None:
    runtime = _local_runtime()
    runtime.record_dialogue_response(
        actor_id="char_b",
        producer_ts=1302,
        payload={
            "actor_id": "char_b",
            "content": "Keep your eyes on the letter.",
            "causation_id": "dialogue:1302",
            "correlation_id": "dialogue:1302",
        },
    )

    observatory_messages = runtime.drain_observatory_messages("char_b")
    snapshots = [
        message["payload"]
        for message in observatory_messages
        if message["message_type"] == "character_agent_debug_snapshot"
    ]
    dialogue_events = [
        message["payload"]
        for message in observatory_messages
        if message["message_type"] == "character_agent_debug_event"
        and message["payload"]["stage"] == "dialogue_writeback"
    ]

    assert dialogue_events
    assert dialogue_events[-1]["summary"] == "Keep your eyes on the letter."
    assert snapshots[-1]["latest_outcome_summary"] == "Keep your eyes on the letter."


def test_runtime_still_returns_legacy_goal_commands_while_recording_execution_requests() -> None:
    runtime = _local_runtime()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=1209,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:1209:char_a",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    commands = runtime.ingest_character_perceived_event(event)
    timeline = runtime.get_session_timeline("char_a")

    assert commands
    assert commands[0].command_type in {"observe", "speak", "approach"}
    assert any(entry["event_type"] == "character_agent_execution_request" for entry in timeline)


def test_runtime_tracks_cadence_policy_and_contact_continuity_state() -> None:
    runtime = _local_runtime()

    cadence = runtime.get_runtime_cadence_policy()
    assert cadence["perception_interval_ms"] == 200
    assert cadence["cognition_interval_ms"] == 500
    assert cadence["degraded_mode"] is False

    runtime.record_execution_request(
        actor_id="char_a",
        producer_ts=1310,
        payload={
            "action_request_bundle": {
                "requested_actions": [
                    {
                        "request_type": "approach",
                        "actor_id": "char_a",
                        "target_actor_id": "char_b",
                    }
                ]
            }
        },
    )

    continuity = runtime.get_runtime_continuity_state("char_a")
    assert continuity["ongoing_contact_target"] == "char_b"
    assert continuity["interrupted_action"] == "approach"
    assert continuity["last_transition_kind"] == "execution_requested"

    runtime.record_settlement_result(
        actor_id="char_a",
        producer_ts=1311,
        payload={
            "result_type": "action_resolution_result",
            "actor_id": "char_a",
            "target_actor_id": "char_b",
            "action_profile": "approach",
            "settlement_status": "accepted",
            "stable_state_summary": "approach accepted",
        },
    )

    settled = runtime.get_runtime_continuity_state("char_a")
    assert settled["ongoing_contact_target"] == "char_b"
    assert settled["interrupted_action"] == ""
    assert settled["last_transition_kind"] == "accepted"


def test_runtime_observatory_snapshot_carries_cadence_and_continuity_summaries() -> None:
    runtime = _local_runtime()
    runtime.record_execution_request(
        actor_id="char_a",
        producer_ts=1312,
        payload={
            "action_request_bundle": {
                "requested_actions": [
                    {
                        "request_type": "approach",
                        "actor_id": "char_a",
                        "target_actor_id": "char_b",
                    }
                ]
            }
        },
    )

    snapshots = [
        message["payload"]
        for message in runtime.drain_observatory_messages("char_a")
        if message["message_type"] == "character_agent_debug_snapshot"
    ]

    assert snapshots
    assert snapshots[-1]["cadence_summary"] == "perception=200|cognition=500|degraded=False"
    assert snapshots[-1]["continuity_summary"] == "contact=char_b|interrupted=approach|transition=execution_requested"


def test_runtime_degraded_mode_defers_second_cognition_pass_inside_cadence_window() -> None:
    runtime = _local_runtime()
    runtime.set_runtime_cadence_policy(
        perception_interval_ms=200,
        cognition_interval_ms=500,
        degraded_mode=True,
    )

    first = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=2000,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:2000:char_a",
        clarity_score=1.0,
        certainty_score=1.0,
    )
    second = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=2200,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:2200:char_a",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    runtime.ingest_character_perceived_event(first)
    runtime.ingest_character_perceived_event(second)

    timeline = runtime.get_session_timeline("char_a")
    observatory_messages = runtime.drain_observatory_messages("char_a")
    execution_requests = [entry for entry in timeline if entry["event_type"] == "character_agent_execution_request"]
    deferred_events = [
        message["payload"]
        for message in observatory_messages
        if message["message_type"] == "character_agent_debug_event"
        and message["payload"]["stage"] == "cognition_deferred"
    ]

    assert len(execution_requests) == 1
    assert deferred_events
    assert deferred_events[-1]["intent_label"] == "degraded_mode"


def test_runtime_degraded_mode_defers_second_perception_pass_inside_perception_window() -> None:
    runtime = _local_runtime()
    runtime.set_runtime_cadence_policy(
        perception_interval_ms=300,
        cognition_interval_ms=500,
        degraded_mode=True,
    )

    first = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=3000,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:3000:char_a",
        clarity_score=1.0,
        certainty_score=1.0,
    )
    second = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=3200,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:3200:char_a",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    runtime.ingest_character_perceived_event(first)
    runtime.ingest_character_perceived_event(second)

    timeline = runtime.get_session_timeline("char_a")
    observatory_messages = runtime.drain_observatory_messages("char_a")
    perceived_events = [entry for entry in timeline if entry["event_type"] == "character_perceived_event"]
    deferred_events = [
        message["payload"]
        for message in observatory_messages
        if message["message_type"] == "character_agent_debug_event"
        and message["payload"]["stage"] == "perception_deferred"
    ]

    assert len(perceived_events) == 1
    assert deferred_events
    assert deferred_events[-1]["intent_label"] == "degraded_mode"


def test_runtime_marks_recovering_when_approach_restarts_after_terminal_transition() -> None:
    runtime = _local_runtime()

    runtime.record_execution_request(
        actor_id="char_a",
        producer_ts=2100,
        payload={
            "action_request_bundle": {
                "requested_actions": [
                    {
                        "request_type": "approach",
                        "actor_id": "char_a",
                        "target_actor_id": "char_b",
                    }
                ]
            }
        },
    )
    runtime.record_settlement_result(
        actor_id="char_a",
        producer_ts=2101,
        payload={
            "result_type": "action_resolution_result",
            "actor_id": "char_a",
            "target_actor_id": "char_b",
            "action_profile": "break_contact",
            "settlement_status": "accepted",
            "stable_state_summary": "break_contact accepted",
        },
    )
    runtime.record_execution_request(
        actor_id="char_a",
        producer_ts=2102,
        payload={
            "action_request_bundle": {
                "requested_actions": [
                    {
                        "request_type": "approach",
                        "actor_id": "char_a",
                        "target_actor_id": "char_b",
                    }
                ]
            }
        },
    )

    continuity = runtime.get_runtime_continuity_state("char_a")
    assert continuity["ongoing_contact_target"] == "char_b"
    assert continuity["interrupted_action"] == "approach"
    assert continuity["last_transition_kind"] == "recovering"


def test_runtime_degraded_mode_defers_repeated_social_spatial_request_inside_cooldown_window() -> None:
    runtime = _local_runtime()
    runtime.set_runtime_cadence_policy(
        perception_interval_ms=200,
        cognition_interval_ms=500,
        degraded_mode=True,
    )

    payload = {
        "action_request_bundle": {
            "requested_actions": [
                {
                    "request_type": "approach",
                    "actor_id": "char_a",
                    "target_actor_id": "char_b",
                }
            ]
        }
    }

    runtime.record_execution_request(actor_id="char_a", producer_ts=4000, payload=payload)
    runtime.record_execution_request(actor_id="char_a", producer_ts=4200, payload=payload)

    timeline = runtime.get_session_timeline("char_a")
    observatory_messages = runtime.drain_observatory_messages("char_a")
    execution_requests = [entry for entry in timeline if entry["event_type"] == "character_agent_execution_request"]
    cooldown_events = [
        message["payload"]
        for message in observatory_messages
        if message["message_type"] == "character_agent_debug_event"
        and message["payload"]["stage"] == "cooldown_deferred"
    ]

    assert len(execution_requests) == 1
    assert cooldown_events
    assert cooldown_events[-1]["intent_label"] == "degraded_mode"


def test_runtime_wake_up_high_salience_siming_input_bypasses_degraded_cognition_deferral() -> None:
    runtime = _local_runtime()
    runtime.set_runtime_cadence_policy(
        perception_interval_ms=200,
        cognition_interval_ms=500,
        degraded_mode=True,
    )

    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=5000,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="visual_fact/fixed_gaze_on_target",
            source_candidate_event_id="visual_fact:5000:char_a",
            clarity_score=1.0,
            certainty_score=1.0,
        )
    )

    commands = runtime.ingest_siming_output(
        SimingCharacterCompatibilityInput(
            message_id="msg:siming:wake-up:1",
            delivery_id="delivery:msg:siming:wake-up:1:char_a:1",
            actor_id="char_a",
            input_type="siming_high_level_message",
            band="impulse",
            producer_ts=5200,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            causation_id="siming:wake-up:1",
            correlation_id="siming:wake-up:1",
            presentation_hint="watch env_lamp now",
            pressure_hint="crowd closing in",
            salience_boost=0.95,
            reason_scope="threat_scan",
        )
    )

    timeline = runtime.get_session_timeline("char_a")
    observatory_messages = runtime.drain_observatory_messages("char_a")
    execution_requests = [entry for entry in timeline if entry["event_type"] == "character_agent_execution_request"]
    wake_up_events = [
        message["payload"]
        for message in observatory_messages
        if message["message_type"] == "character_agent_debug_event"
        and message["payload"]["stage"] == "wake_up"
    ]
    deferred_events = [
        message["payload"]
        for message in observatory_messages
        if message["message_type"] == "character_agent_debug_event"
        and message["payload"]["stage"] == "cognition_deferred"
    ]

    assert commands
    assert len(execution_requests) == 2
    assert wake_up_events
    assert wake_up_events[-1]["intent_label"] == "high_salience_siming"
    assert deferred_events == []


def test_runtime_observatory_snapshot_carries_scheduling_summary_for_degraded_population() -> None:
    runtime = _local_runtime()
    runtime.set_runtime_population_policy(
        max_active_actors_per_tick=4,
        wake_up_batch_size=2,
        degraded_population_threshold=3,
        prioritize_continuity_recovery=True,
    )

    runtime.record_execution_request(
        actor_id="char_b",
        producer_ts=6100,
        payload={
            "action_request_bundle": {
                "requested_actions": [
                    {
                        "request_type": "approach",
                        "actor_id": "char_b",
                        "target_actor_id": "char_c",
                    }
                ]
            }
        },
    )
    runtime.record_settlement_result(
        actor_id="char_b",
        producer_ts=6101,
        payload={
            "result_type": "action_resolution_result",
            "actor_id": "char_b",
            "target_actor_id": "char_c",
            "action_profile": "break_contact",
            "settlement_status": "accepted",
            "stable_state_summary": "break_contact accepted",
        },
    )
    runtime.record_execution_request(
        actor_id="char_b",
        producer_ts=6102,
        payload={
            "action_request_bundle": {
                "requested_actions": [
                    {
                        "request_type": "approach",
                        "actor_id": "char_b",
                        "target_actor_id": "char_c",
                    }
                ]
            }
        },
    )
    runtime.ingest_siming_output(
        SimingCharacterCompatibilityInput(
            message_id="msg:siming:scheduling:1",
            delivery_id="delivery:msg:siming:scheduling:1:char_a:1",
            actor_id="char_a",
            input_type="siming_high_level_message",
            band="impulse",
            producer_ts=6103,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            causation_id="siming:scheduling:1",
            correlation_id="siming:scheduling:1",
            presentation_hint="watch env_lamp now",
            pressure_hint="crowd closing in",
            salience_boost=0.95,
            reason_scope="threat_scan",
        )
    )

    snapshots = [
        message["payload"]
        for message in runtime.drain_observatory_messages("char_a")
        if message["message_type"] == "character_agent_debug_snapshot"
    ]

    assert snapshots
    assert snapshots[-1]["scheduling_summary"] == "population=3|limit=2|degraded=True|active=char_b,char_a"


def test_runtime_emits_scheduling_state_event_for_selected_actor_under_population_pressure() -> None:
    runtime = _local_runtime()
    runtime.set_runtime_population_policy(
        max_active_actors_per_tick=4,
        wake_up_batch_size=2,
        degraded_population_threshold=3,
        prioritize_continuity_recovery=True,
    )

    runtime.record_execution_request(
        actor_id="char_b",
        producer_ts=6200,
        payload={
            "action_request_bundle": {
                "requested_actions": [
                    {
                        "request_type": "approach",
                        "actor_id": "char_b",
                        "target_actor_id": "char_c",
                    }
                ]
            }
        },
    )
    runtime.record_settlement_result(
        actor_id="char_b",
        producer_ts=6201,
        payload={
            "result_type": "action_resolution_result",
            "actor_id": "char_b",
            "target_actor_id": "char_c",
            "action_profile": "break_contact",
            "settlement_status": "accepted",
            "stable_state_summary": "break_contact accepted",
        },
    )
    runtime.record_execution_request(
        actor_id="char_b",
        producer_ts=6202,
        payload={
            "action_request_bundle": {
                "requested_actions": [
                    {
                        "request_type": "approach",
                        "actor_id": "char_b",
                        "target_actor_id": "char_c",
                    }
                ]
            }
        },
    )
    runtime.ingest_siming_output(
        SimingCharacterCompatibilityInput(
            message_id="msg:siming:scheduling-state:1",
            delivery_id="delivery:msg:siming:scheduling-state:1:char_a:1",
            actor_id="char_a",
            input_type="siming_high_level_message",
            band="impulse",
            producer_ts=6203,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            causation_id="siming:scheduling-state:1",
            correlation_id="siming:scheduling-state:1",
            presentation_hint="watch env_lamp now",
            pressure_hint="crowd closing in",
            salience_boost=0.95,
            reason_scope="threat_scan",
        )
    )

    scheduling_events = [
        message["payload"]
        for message in runtime.drain_observatory_messages("char_a")
        if message["message_type"] == "character_agent_debug_event"
        and message["payload"]["stage"] == "scheduling_state"
    ]

    assert scheduling_events
    assert scheduling_events[-1]["summary"] == "actor selected for active runtime set"
    assert scheduling_events[-1]["detail"]["active_actor_ids"] == ["char_b", "char_a"]
    assert scheduling_events[-1]["detail"]["degraded_population"] is True
    assert scheduling_events[-1]["detail"]["actor_selected"] is True
    assert scheduling_events[-1]["detail"]["wake_up_requested"] is True


def test_runtime_exposes_unified_scheduling_state_for_population_tick() -> None:
    runtime = _local_runtime()
    runtime.set_runtime_population_policy(
        max_active_actors_per_tick=4,
        wake_up_batch_size=2,
        degraded_population_threshold=3,
        prioritize_continuity_recovery=True,
    )

    runtime.record_execution_request(
        actor_id="char_b",
        producer_ts=6300,
        payload={
            "action_request_bundle": {
                "requested_actions": [
                    {
                        "request_type": "approach",
                        "actor_id": "char_b",
                        "target_actor_id": "char_c",
                    }
                ]
            }
        },
    )
    runtime.record_settlement_result(
        actor_id="char_b",
        producer_ts=6301,
        payload={
            "result_type": "action_resolution_result",
            "actor_id": "char_b",
            "target_actor_id": "char_c",
            "action_profile": "break_contact",
            "settlement_status": "accepted",
            "stable_state_summary": "break_contact accepted",
        },
    )
    runtime.record_execution_request(
        actor_id="char_b",
        producer_ts=6302,
        payload={
            "action_request_bundle": {
                "requested_actions": [
                    {
                        "request_type": "approach",
                        "actor_id": "char_b",
                        "target_actor_id": "char_c",
                    }
                ]
            }
        },
    )
    runtime.ingest_siming_output(
        SimingCharacterCompatibilityInput(
            message_id="msg:siming:unified-scheduling-state:1",
            delivery_id="delivery:msg:siming:unified-scheduling-state:1:char_a:1",
            actor_id="char_a",
            input_type="siming_high_level_message",
            band="impulse",
            producer_ts=6303,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            causation_id="siming:unified-scheduling-state:1",
            correlation_id="siming:unified-scheduling-state:1",
            presentation_hint="watch env_lamp now",
            pressure_hint="crowd closing in",
            salience_boost=0.95,
            reason_scope="threat_scan",
        )
    )

    scheduling_state = runtime.get_runtime_scheduling_state()

    assert scheduling_state["actor_population"] == 3
    assert scheduling_state["active_limit"] == 2
    assert scheduling_state["degraded_population"] is True
    assert scheduling_state["active_actor_ids"] == ["char_b", "char_a"]
    assert scheduling_state["per_actor"]["char_b"]["actor_selected"] is True
    assert scheduling_state["per_actor"]["char_b"]["continuity_priority"] == 3
    assert scheduling_state["per_actor"]["char_a"]["wake_up_requested"] is True
    assert scheduling_state["per_actor"]["char_c"]["actor_selected"] is False


def test_runtime_scheduling_round_state_advances_round_id_when_new_runtime_tick_arrives() -> None:
    runtime = _local_runtime()

    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=6400,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="visual_fact/fixed_gaze_on_target",
            source_candidate_event_id="visual_fact:6400:char_a",
            clarity_score=1.0,
            certainty_score=1.0,
        )
    )
    first_state = runtime.get_runtime_scheduling_state()

    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=6500,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="visual_fact/object_state_changed",
            source_candidate_event_id="visual_fact:6500:char_a",
            clarity_score=1.0,
            certainty_score=1.0,
        )
    )
    second_state = runtime.get_runtime_scheduling_state()

    assert first_state["round_id"] == 1
    assert first_state["round_started_at"] == 6400
    assert second_state["round_id"] == 2
    assert second_state["round_started_at"] == 6500


def test_runtime_scheduling_state_exposes_selection_reason_tags_for_active_actor_set() -> None:
    runtime = _local_runtime()
    runtime.set_runtime_population_policy(
        max_active_actors_per_tick=4,
        wake_up_batch_size=2,
        degraded_population_threshold=3,
        prioritize_continuity_recovery=True,
    )

    runtime.record_execution_request(
        actor_id="char_b",
        producer_ts=6600,
        payload={
            "action_request_bundle": {
                "requested_actions": [
                    {
                        "request_type": "approach",
                        "actor_id": "char_b",
                        "target_actor_id": "char_c",
                    }
                ]
            }
        },
    )
    runtime.record_settlement_result(
        actor_id="char_b",
        producer_ts=6601,
        payload={
            "result_type": "action_resolution_result",
            "actor_id": "char_b",
            "target_actor_id": "char_c",
            "action_profile": "break_contact",
            "settlement_status": "accepted",
            "stable_state_summary": "break_contact accepted",
        },
    )
    runtime.record_execution_request(
        actor_id="char_b",
        producer_ts=6602,
        payload={
            "action_request_bundle": {
                "requested_actions": [
                    {
                        "request_type": "approach",
                        "actor_id": "char_b",
                        "target_actor_id": "char_c",
                    }
                ]
            }
        },
    )
    runtime.ingest_siming_output(
        SimingCharacterCompatibilityInput(
            message_id="msg:siming:selection-reason:1",
            delivery_id="delivery:msg:siming:selection-reason:1:char_a:1",
            actor_id="char_a",
            input_type="siming_high_level_message",
            band="impulse",
            producer_ts=6603,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            causation_id="siming:selection-reason:1",
            correlation_id="siming:selection-reason:1",
            presentation_hint="watch env_lamp now",
            pressure_hint="crowd closing in",
            salience_boost=0.95,
            reason_scope="threat_scan",
        )
    )

    scheduling_state = runtime.get_runtime_scheduling_state()

    assert scheduling_state["active_actor_ids"] == ["char_b", "char_a"]
    assert scheduling_state["per_actor"]["char_b"]["selection_reason_tags"] == ["continuity_recovery"]
    assert scheduling_state["per_actor"]["char_a"]["selection_reason_tags"] == [
        "continuity_priority",
        "wake_up_signal",
        "salience_priority",
    ]
    assert scheduling_state["active_actor_reason_map"]["char_b"] == ["continuity_recovery"]
    assert scheduling_state["active_actor_reason_map"]["char_a"] == [
        "continuity_priority",
        "wake_up_signal",
        "salience_priority",
    ]


def test_runtime_scheduling_state_exposes_round_summary_and_reason_tags_for_active_actor_set() -> None:
    runtime = _local_runtime()
    runtime.set_runtime_population_policy(
        max_active_actors_per_tick=4,
        wake_up_batch_size=2,
        degraded_population_threshold=3,
        prioritize_continuity_recovery=True,
    )

    runtime.record_execution_request(
        actor_id="char_b",
        producer_ts=6700,
        payload={
            "action_request_bundle": {
                "requested_actions": [
                    {
                        "request_type": "approach",
                        "actor_id": "char_b",
                        "target_actor_id": "char_c",
                    }
                ]
            }
        },
    )
    runtime.record_settlement_result(
        actor_id="char_b",
        producer_ts=6701,
        payload={
            "result_type": "action_resolution_result",
            "actor_id": "char_b",
            "target_actor_id": "char_c",
            "action_profile": "break_contact",
            "settlement_status": "accepted",
            "stable_state_summary": "break_contact accepted",
        },
    )
    runtime.record_execution_request(
        actor_id="char_b",
        producer_ts=6702,
        payload={
            "action_request_bundle": {
                "requested_actions": [
                    {
                        "request_type": "approach",
                        "actor_id": "char_b",
                        "target_actor_id": "char_c",
                    }
                ]
            }
        },
    )
    runtime.ingest_siming_output(
        SimingCharacterCompatibilityInput(
            message_id="msg:siming:round-summary:1",
            delivery_id="delivery:msg:siming:round-summary:1:char_a:1",
            actor_id="char_a",
            input_type="siming_high_level_message",
            band="impulse",
            producer_ts=6703,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            causation_id="siming:round-summary:1",
            correlation_id="siming:round-summary:1",
            presentation_hint="watch env_lamp now",
            pressure_hint="crowd closing in",
            salience_boost=0.95,
            reason_scope="threat_scan",
        )
    )

    scheduling_state = runtime.get_runtime_scheduling_state()

    assert scheduling_state["lead_actor_id"] == "char_b"
    assert scheduling_state["round_reason_tags"] == [
        "continuity_recovery",
        "continuity_priority",
        "wake_up_signal",
        "salience_priority",
    ]
    assert scheduling_state["round_summary"] == "round 4 selects char_b, char_a because continuity_recovery, continuity_priority, wake_up_signal, salience_priority"


def test_runtime_emits_single_scheduling_round_state_event_with_unified_summary() -> None:
    runtime = _local_runtime()
    runtime.set_runtime_population_policy(
        max_active_actors_per_tick=4,
        wake_up_batch_size=2,
        degraded_population_threshold=3,
        prioritize_continuity_recovery=True,
    )

    runtime.record_execution_request(
        actor_id="char_b",
        producer_ts=6800,
        payload={
            "action_request_bundle": {
                "requested_actions": [
                    {
                        "request_type": "approach",
                        "actor_id": "char_b",
                        "target_actor_id": "char_c",
                    }
                ]
            }
        },
    )
    runtime.record_settlement_result(
        actor_id="char_b",
        producer_ts=6801,
        payload={
            "result_type": "action_resolution_result",
            "actor_id": "char_b",
            "target_actor_id": "char_c",
            "action_profile": "break_contact",
            "settlement_status": "accepted",
            "stable_state_summary": "break_contact accepted",
        },
    )
    runtime.record_execution_request(
        actor_id="char_b",
        producer_ts=6802,
        payload={
            "action_request_bundle": {
                "requested_actions": [
                    {
                        "request_type": "approach",
                        "actor_id": "char_b",
                        "target_actor_id": "char_c",
                    }
                ]
            }
        },
    )
    _ = runtime.drain_observatory_messages()
    runtime.ingest_siming_output(
        SimingCharacterCompatibilityInput(
            message_id="msg:siming:round-event:1",
            delivery_id="delivery:msg:siming:round-event:1:char_a:1",
            actor_id="char_a",
            input_type="siming_high_level_message",
            band="impulse",
            producer_ts=6803,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            causation_id="siming:round-event:1",
            correlation_id="siming:round-event:1",
            presentation_hint="watch env_lamp now",
            pressure_hint="crowd closing in",
            salience_boost=0.95,
            reason_scope="threat_scan",
        )
    )

    round_events = [
        message["payload"]
        for message in runtime.drain_observatory_messages()
        if message["message_type"] == "character_agent_debug_event"
        and message["payload"]["stage"] == "scheduling_round_state"
    ]

    assert len(round_events) == 1
    assert round_events[0]["actor_id"] == "char_b"
    assert round_events[0]["summary"] == "round 4 selects char_b, char_a because continuity_recovery, wake_up_signal, salience_priority"
    assert round_events[0]["detail"]["lead_actor_id"] == "char_b"
    assert round_events[0]["detail"]["active_actor_ids"] == ["char_b", "char_a"]
    assert round_events[0]["detail"]["round_reason_tags"] == [
        "continuity_recovery",
        "wake_up_signal",
        "salience_priority",
    ]


def test_runtime_execution_request_and_returned_commands_stay_causally_aligned() -> None:
    runtime = _local_runtime()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=1210,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:1210:char_a",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    commands = runtime.ingest_character_perceived_event(event)
    timeline = runtime.get_session_timeline("char_a")
    execution_requests = [entry for entry in timeline if entry["event_type"] == "character_agent_execution_request"]

    assert commands
    assert execution_requests
    latest_request = execution_requests[-1]
    assert latest_request["payload"]["actor_id"] == commands[0].actor_id


def test_player_priority_suggestion_packets_are_written_into_runtime_timeline() -> None:
    runtime = _local_runtime()
    event = CharacterPerceivedEvent(
        actor_id="char_c",
        percept_channel="auditory",
        producer_ts=1211,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:1211:char_c",
        clarity_score=0.8,
        certainty_score=0.65,
    )

    runtime.ingest_character_perceived_event(event)
    _ = runtime.drain_suggestion_packets("char_c")
    timeline = runtime.get_session_timeline("char_c")

    assert any(entry["event_type"] == "character_agent_suggestion_packet" for entry in timeline)


def test_char_c_private_perception_path_records_snapshot_reasoning_and_suggestion_without_bypassing_to_commands() -> None:
    runtime = _local_runtime()
    event = CharacterPerceivedEvent(
        actor_id="char_c",
        percept_channel="auditory",
        producer_ts=1212,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:1212:char_c",
        source_actor_id="char_a",
        target_actor_id="char_c",
        clarity_score=0.81,
        certainty_score=0.69,
    )

    commands = runtime.ingest_character_perceived_event(event)
    snapshot = runtime.get_private_snapshot("char_c")
    timeline = runtime.get_session_timeline("char_c")

    assert commands == []
    assert snapshot is not None
    assert snapshot.actor_id == "char_c"
    assert snapshot.audible_entities == ["auditory_fact/speaker_active"]
    assert snapshot.attention_targets == ["char_c"]
    assert snapshot.current_attention_targets == ["char_c"]
    event_types = [entry["event_type"] for entry in timeline]
    assert "character_perceived_event" in event_types
    assert "l2_reasoning_request" in event_types
    assert "character_interpretation_event" in event_types
    assert "character_agent_suggestion_packet" in event_types
    assert "character_agent_execution_request" not in event_types


def test_runtime_writes_relational_belief_event_for_targeted_actor_private_perception() -> None:
    runtime = _local_runtime()
    event = CharacterPerceivedEvent(
        actor_id="char_c",
        percept_channel="auditory",
        producer_ts=1213,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:1213:char_c",
        source_actor_id="char_a",
        target_actor_id="char_c",
        clarity_score=0.81,
        certainty_score=0.69,
    )

    runtime.ingest_character_perceived_event(event)
    timeline = runtime.get_session_timeline("char_c")
    bundle = runtime.get_memory_bundle("char_c")

    relational_events = [entry for entry in timeline if entry["event_type"] == "relational_belief_event"]

    assert relational_events
    assert relational_events[-1]["payload"]["entity_id"] == "char_a"
    assert relational_events[-1]["payload"]["belief_type"] == "trust_level"
    assert relational_events[-1]["payload"]["value"] == "guarded"
    assert bundle["social_memories"]
    assert any(entry["entity_id"] == "char_a" for entry in bundle["social_memories"])
    assert bundle["knowledge_memories"]
    assert any(entry["proposition_key"] == "social:char_a:trust_level" for entry in bundle["knowledge_memories"])
    if "relational_memories" in bundle:
        assert bundle["relational_memories"]
        assert any(
            entry["entity_id"] == "char_a"
            and entry["belief_type"] == "trust_level"
            and entry["value"] == "guarded"
            for entry in bundle["relational_memories"]
        )


def test_runtime_working_memory_state_remains_short_window_only() -> None:
    runtime = _local_runtime()
    runtime.record_settlement_result(
        actor_id="char_d",
        producer_ts=1214,
        payload={
            "result_type": "action_resolution_result",
            "change_summary": "door half open",
            "causation_id": "settlement:1214",
            "correlation_id": "settlement:1214",
        },
    )

    state = runtime.get_working_memory_state("char_d", private_snapshot={"actor_id": "char_d"})

    assert state["recent_esm_results"]
    assert "episodic_memories" not in state
    assert "event_memories" not in state
    assert "observation_memories" not in state
    assert "knowledge_memories" not in state
    assert "relational_memories" not in state
    assert "social_memories" not in state


def test_retrieval_bundle_exposes_five_memory_pools_and_dynamic_state_inputs() -> None:
    runtime = _local_runtime()

    bundle = runtime.get_memory_bundle("char_a")

    assert set(bundle.keys()) >= {
        "working_memory",
        "event_memories",
        "observation_memories",
        "knowledge_memories",
        "social_memories",
        "higher_order_memories",
    }


def test_runtime_exposes_typed_memory_record_bundle() -> None:
    runtime = _local_runtime()
    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="auditory",
            producer_ts=1203,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="auditory_fact/speaker_active",
            source_candidate_event_id="auditory_fact:1203:char_a",
            clarity_score=0.75,
            certainty_score=0.6,
        )
    )

    bundle = runtime.get_memory_record_bundle("char_a")

    assert isinstance(bundle, CharacterMemoryRecordBundle)
    assert bundle.event_memories
    assert bundle.observation_memories
    assert bundle.knowledge_memories == [] or bundle.knowledge_memories[0].proposition_key


def test_runtime_working_memory_state_record_carries_typed_dynamic_state() -> None:
    runtime = _local_runtime()
    runtime._dynamic_state_store.write(
        "char_a",
        {
            "actor_id": "char_a",
            "vigilance_level": 0.2,
            "distraction_level": 0.1,
            "stress_load": 0.4,
            "social_pressure": 0.3,
            "masking_pressure": 0.2,
            "motivation_stack": ["preserve_order"],
        },
    )

    state = runtime.get_working_memory_state_record("char_a", private_snapshot={"actor_id": "char_a"})

    assert state.dynamic_state is not None
    assert state.dynamic_state.actor_id == "char_a"
    assert state.dynamic_state.motivation_stack == ["preserve_order"]
