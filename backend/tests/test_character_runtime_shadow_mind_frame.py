from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.skills.models import SkillAffordanceSummary
from app.character_agent.skills.service import CharacterSkillService
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


def test_runtime_shadow_skill_affordance_does_not_change_command_output() -> None:
    baseline = CharacterAgentRuntime()
    shadowed = CharacterAgentRuntime()
    shadowed._skill_service = _RecordingSkillService()

    baseline_commands = baseline.ingest_character_perceived_event(_event())
    shadowed_commands = shadowed.ingest_character_perceived_event(_event())

    assert [command.model_dump() for command in shadowed_commands] == [
        command.model_dump() for command in baseline_commands
    ]


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
