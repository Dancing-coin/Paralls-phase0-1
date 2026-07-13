from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.skills.catalog import create_runtime_skill_registry
from app.character_agent.skills.models import ActionDefinition, SkillActionBinding
from app.character_agent.skills.registry import CharacterSkillRegistry
from app.character_agent.skills.service import CharacterSkillService
from app.models.character_agent_runtime import CharacterIntentDecision, CharacterInterpretation
from app.models.character_perceived import CharacterPerceivedEvent


def _event(*, actor_id: str = "char_a") -> CharacterPerceivedEvent:
    return CharacterPerceivedEvent(
        actor_id=actor_id,
        percept_channel="visual",
        producer_ts=100,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_demo",
        perceived_summary="char_b pauses near the archive threshold",
        source_candidate_event_id="event:shadow:1",
        source_actor_id="char_b",
        target_actor_id="char_b",
        clarity_score=0.95,
        certainty_score=0.95,
    )


def _skill_affordance_payload(frame: dict[str, object]) -> dict[str, object]:
    affordances = frame["affordances"]
    assert isinstance(affordances, dict)
    cards = affordances["cards"]
    assert isinstance(cards, list)
    for card in cards:
        assert isinstance(card, dict)
        if card.get("factor_type") == "skill_affordance":
            payload = card.get("payload", {})
            assert isinstance(payload, dict)
            return payload
    raise AssertionError("skill_affordance card missing")


def _execution_snapshot() -> CharacterPrivateWorldSnapshot:
    return CharacterPrivateWorldSnapshot(
        actor_id="char_a",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_demo",
        producer_ts=200,
        visible_entities=[],
        audible_entities=[],
        attention_targets=["char_b"],
        updated_at=200,
    )


def _execution_interpretation() -> CharacterInterpretation:
    return CharacterInterpretation(
        actor_id="char_a",
        interpreted_summary="char_b is injured and anxious",
        interpretation_type="social_signal",
        salience_score=0.8,
        ambiguity_level="low",
        risk_level="medium",
        opportunity_level="medium",
        attention_target="char_b",
        inner_prompt_candidate="help char_b",
    )


def _execution_decision() -> CharacterIntentDecision:
    return CharacterIntentDecision(
        actor_id="char_a",
        selected_intent="share_info",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="offer help",
    )


def _latest_execution_payload(runtime: CharacterAgentRuntime, *, actor_id: str = "char_a") -> dict[str, object]:
    timeline = runtime.get_session_timeline(actor_id)
    execution_events = [
        entry
        for entry in timeline
        if entry["event_type"] == "character_agent_execution_request"
    ]
    assert execution_events
    payload = execution_events[-1]["payload"]
    assert isinstance(payload, dict)
    return payload


def test_runtime_shadow_frame_projects_compressed_skill_affordance_summary() -> None:
    runtime = CharacterAgentRuntime()
    runtime.ingest_character_perceived_event(_event())

    frame = runtime.build_shadow_mind_frame(
        actor_id="char_a",
        producer_ts=101,
        trigger_event={"event_id": "event:shadow:manual", "event_type": "shadow_probe"},
    )
    payload = _skill_affordance_payload(frame)

    assert payload["profile_skill_ids"] == ["observation", "mediation", "procedural recall"]
    assert payload["available_action_families"]["observation"]["examples"] == ["survey_scene"]
    assert payload["available_action_families"]["observation"]["level"] == "basic"
    assert payload["available_action_families"]["social"]["examples"] == [
        "defuse_social_tension"
    ]
    assert payload["available_action_families"]["procedure"]["examples"] == [
        "follow_room_protocol"
    ]
    assert "registry" not in payload
    assert "skills" not in payload
    assert "actions" not in payload
    assert "bindings" not in payload


def test_runtime_shadow_frame_tolerates_empty_skill_registry_without_exposing_registry() -> None:
    runtime = CharacterAgentRuntime(
        skill_service=CharacterSkillService(registry=CharacterSkillRegistry())
    )
    runtime.ingest_character_perceived_event(_event())

    frame = runtime.build_shadow_mind_frame(
        actor_id="char_a",
        producer_ts=101,
        trigger_event={"event_id": "event:shadow:manual", "event_type": "shadow_probe"},
    )
    payload = _skill_affordance_payload(frame)

    assert payload["profile_skill_ids"] == ["observation", "mediation", "procedural recall"]
    assert payload["profile_limits"] == []
    assert payload["available_action_families"] == {}
    assert payload["blocked_action_families"] == {}
    assert "registry" not in payload
    assert "skills" not in payload
    assert "actions" not in payload
    assert "bindings" not in payload


def test_runtime_execution_plan_attaches_advisory_skill_shadow_without_rewriting_action_request_bundle() -> None:
    runtime = CharacterAgentRuntime()

    plan = runtime._record_execution_plan(  # type: ignore[attr-defined]
        "char_a",
        200,
        _execution_snapshot(),
        _execution_interpretation(),
        _execution_decision(),
    )

    expected_requested_actions = [
        {
            "request_type": "share_info",
            "actor_id": "char_a",
            "target_actor_id": "char_b",
            "content": "char_b is injured and anxious",
        }
    ]
    payload = _latest_execution_payload(runtime)
    skill_evaluation_result = payload["skill_evaluation_result"]

    assert plan["composite_action_proposal"]["action_id"] == "share_info"
    assert plan["action_request_bundle"]["requested_actions"] == expected_requested_actions
    assert payload["action_request_bundle"]["requested_actions"] == expected_requested_actions
    assert skill_evaluation_result["actor_id"] == "char_a"
    assert skill_evaluation_result["action_id"] == "share_info"
    assert skill_evaluation_result["selected_path"] == {}
    assert skill_evaluation_result["viable_paths"] == []
    assert skill_evaluation_result["blocked_paths"] == []
    assert skill_evaluation_result["advisory"] is True
    assert skill_evaluation_result["evaluation_mode"] == "shadow"
    assert "primitive_action_plan" not in payload


def test_runtime_execution_plan_can_attach_advisory_primitive_plan_for_bound_share_info_path() -> None:
    overlay_registry = CharacterSkillRegistry(
        actions=[
            ActionDefinition(
                action_id="share_info",
                kind="composite",
                settlement_categories=["social"],
                primitive_sequence_templates={
                    "mediation_to_share_info": [
                        "assess_receptivity",
                        "share_carefully",
                    ]
                },
                realization_keys=["steady_voice", "open_palms"],
            )
        ],
        bindings=[
            SkillActionBinding(
                binding_id="mediation_to_share_info",
                skill_id="mediation",
                action_id="share_info",
                skill_path_tags=["social", "careful_disclosure"],
                eligibility={"required_rank": "basic"},
            )
        ],
    )
    runtime = CharacterAgentRuntime(
        skill_service=CharacterSkillService(
            registry=create_runtime_skill_registry(overlay_registry)
        )
    )

    plan = runtime._record_execution_plan(  # type: ignore[attr-defined]
        "char_a",
        200,
        _execution_snapshot(),
        _execution_interpretation(),
        _execution_decision(),
    )

    payload = _latest_execution_payload(runtime)
    skill_evaluation_result = payload["skill_evaluation_result"]
    primitive_action_plan = payload["primitive_action_plan"]

    assert plan["action_request_bundle"]["requested_actions"] == [
        {
            "request_type": "share_info",
            "actor_id": "char_a",
            "target_actor_id": "char_b",
            "content": "char_b is injured and anxious",
        }
    ]
    assert skill_evaluation_result["selected_path"]["binding_id"] == "mediation_to_share_info"
    assert skill_evaluation_result["selected_path"]["action_id"] == "share_info"
    assert skill_evaluation_result["advisory"] is True
    assert skill_evaluation_result["evaluation_mode"] == "shadow"
    assert primitive_action_plan["composite_action_id"] == "share_info"
    assert primitive_action_plan["skill_path_id"] == "mediation_to_share_info"
    assert primitive_action_plan["primitive_actions"] == [
        "assess_receptivity",
        "share_carefully",
    ]
    assert primitive_action_plan["realization_keys"] == ["steady_voice", "open_palms"]
