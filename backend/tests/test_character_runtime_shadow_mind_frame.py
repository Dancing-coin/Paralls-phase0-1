from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.character_agent.skills.models import SkillAffordanceSummary
from app.character_agent.skills.service import CharacterSkillService
from app.models.character_agent_runtime import CharacterIntentDecision, CharacterInterpretation
from app.models.character_perceived import CharacterPerceivedEvent


def _event() -> CharacterPerceivedEvent:
    return CharacterPerceivedEvent(
        actor_id="char_b",
        percept_channel="visual",
        producer_ts=100,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_demo",
        perceived_summary="char_a moves quietly near the medicine kit",
        source_candidate_event_id="event:shadow:1",
        source_actor_id="char_a",
        target_actor_id="char_a",
        clarity_score=0.9,
        certainty_score=0.8,
    )


class _RecordingSkillService(CharacterSkillService):
    def __init__(self) -> None:
        super().__init__()
        self.build_affordance_summary_calls = 0

    def build_affordance_summary(
        self,
        *,
        actor_id: str,
        skill_states: list,
    ) -> SkillAffordanceSummary:
        self.build_affordance_summary_calls += 1
        return SkillAffordanceSummary(
            actor_id=actor_id,
            available_action_families={"shadow_probe": {"level": "trained"}},
            blocked_action_families={},
        )


def test_runtime_can_build_shadow_mind_frame_without_changing_command_output() -> None:
    runtime = CharacterAgentRuntime()

    commands = runtime.ingest_character_perceived_event(_event())
    frame = runtime.build_shadow_mind_frame(
        actor_id="char_b",
        producer_ts=101,
        trigger_event={"event_id": "event:shadow:manual", "event_type": "shadow_probe"},
    )

    assert isinstance(commands, list)
    assert frame["actor_id"] == "char_b"
    assert frame["trigger"]["event_id"] == "event:shadow:manual"
    assert frame["memory_evidence"]["summary"]["event_memory_count"] >= 1
    assert frame["runtime_state"]["summary"]["focus_target"]


def test_runtime_records_l3_skill_affordance_shadow_summary() -> None:
    runtime = CharacterAgentRuntime()
    service = _RecordingSkillService()
    runtime._skill_service = service

    runtime.ingest_character_perceived_event(_event())
    frame = runtime.build_shadow_mind_frame(
        actor_id="char_b",
        producer_ts=101,
        trigger_event={"event_id": "event:shadow:manual", "event_type": "shadow_probe"},
    )

    skill_cards = [
        card
        for card in frame["affordances"]["cards"]
        if card["factor_type"] == "skill_affordance"
    ]
    assert service.build_affordance_summary_calls >= 1
    assert skill_cards
    assert skill_cards[0]["payload"]["available_action_families"]["shadow_probe"]["level"] == "trained"
    assert frame["affordances"]["summary"]["has_skill_affordance"] is True


def test_runtime_skill_consumption_preserves_legacy_command_surface() -> None:
    baseline = CharacterAgentRuntime()
    shadowed = CharacterAgentRuntime()
    shadowed._skill_service = _RecordingSkillService()

    baseline_commands = baseline.ingest_character_perceived_event(_event())
    shadowed_commands = shadowed.ingest_character_perceived_event(_event())

    baseline = baseline_commands[0]
    shadowed = shadowed_commands[0]
    assert shadowed.command_type == baseline.command_type
    assert shadowed.actor_id == baseline.actor_id
    assert shadowed.target_actor_id == baseline.target_actor_id
    assert shadowed.producer_ts == baseline.producer_ts
    assert shadowed.execution_payload["action_request_bundle"] == baseline.execution_payload["action_request_bundle"]
    assert shadowed.execution_payload["skill_guardrail"]["advisory_only"] is True


def test_runtime_attaches_selected_skill_binding_without_rewriting_legacy_action() -> None:
    runtime = CharacterAgentRuntime()
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id="char_a",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_demo",
        producer_ts=101,
        updated_at=101,
        attention_targets=["obj_console"],
    )
    interpretation = CharacterInterpretation(
        actor_id="char_a",
        interpreted_summary="inspect the console",
        interpretation_type="environment_change",
        salience_score=0.8,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="medium",
        attention_target="obj_console",
    )

    plan = runtime._record_execution_plan(
        "char_a",
        101,
        snapshot,
        interpretation,
        CharacterIntentDecision(
            actor_id="char_a",
            selected_intent="observe",
            persona_passed=True,
            logic_passed=True,
            gain_loss_passed=True,
            rationale="inspect the console",
        ),
    )

    assert plan["action_request_bundle"]["requested_actions"] == []
    assert runtime._l4.build_commands_from_execution_plan(plan)[0].command_type == "observe"
    assert plan["skill_guardrail"]["status"] == "selected_path"
    assert plan["skill_guardrail"]["selected_path"]["binding_id"] == "observation_to_survey_scene"
    assert plan["primitive_action_plan"]["primitive_actions"]


def test_runtime_records_blocked_skill_path_without_blocking_legacy_command() -> None:
    runtime = CharacterAgentRuntime()
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_demo",
        producer_ts=102,
        updated_at=102,
        attention_targets=["obj_console"],
    )
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="inspect the console",
        interpretation_type="environment_change",
        salience_score=0.8,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="medium",
        attention_target="obj_console",
    )
    plan = runtime._record_execution_plan(
        "char_b",
        102,
        snapshot,
        interpretation,
        CharacterIntentDecision(
            actor_id="char_b",
            selected_intent="observe",
            persona_passed=True,
            logic_passed=True,
            gain_loss_passed=True,
            rationale="inspect the console",
        ),
    )

    assert plan["skill_guardrail"]["status"] == "no_eligible_path"
    assert plan["skill_guardrail"]["advisory_only"] is True
    assert "primitive_action_plan" not in plan
    assert runtime._l4.build_commands_from_execution_plan(plan)[0].command_type == "observe"


def test_runtime_shadow_mind_frame_is_read_only_snapshot() -> None:
    runtime = CharacterAgentRuntime()
    runtime.ingest_character_perceived_event(_event())

    before = runtime.get_memory_bundle("char_b")
    frame = runtime.build_shadow_mind_frame(
        actor_id="char_b",
        producer_ts=102,
        trigger_event={"event_id": "event:shadow:manual", "event_type": "shadow_probe"},
    )
    after = runtime.get_memory_bundle("char_b")

    assert frame["mind_turn_id"] == "mind_turn:char_b:102"
    assert before == after
