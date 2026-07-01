from app.models.character_agent_runtime import CharacterGoalCommand
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.models.character_perceived import CharacterPerceivedEvent
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from app.services.character_agent_runtime import CharacterAgentRuntime


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


def _local_runtime() -> CharacterAgentRuntime:
    runtime = CharacterAgentRuntime()
    local_gateway = _LocalGateway()
    runtime._l2 = CharacterAgentL2Service(gateway=local_gateway, profile_registry=runtime._profile_registry)
    runtime._l3 = CharacterAgentL3Service(gateway=local_gateway)
    return runtime


def make_character_perceived_event(
    *,
    actor_id: str = "char_a",
    perceived_summary: str = "visual_fact/fixed_gaze_on_target",
    producer_ts: int = 300,
) -> CharacterPerceivedEvent:
    return CharacterPerceivedEvent(
        actor_id=actor_id,
        percept_channel="visual",
        producer_ts=producer_ts,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary=perceived_summary,
        source_candidate_event_id=f"visual_fact:{producer_ts}:{actor_id}",
        clarity_score=1.0,
        certainty_score=1.0,
    )


def test_character_agent_runtime_emits_goal_command() -> None:
    runtime = _local_runtime()
    event = make_character_perceived_event(actor_id="char_a", perceived_summary="visual_fact/fixed_gaze_on_target")

    commands = runtime.ingest_character_perceived_event(event)

    assert commands
    assert isinstance(commands[0], CharacterGoalCommand)
    assert commands[0].command_type == "observe"
    assert commands[0].execution_payload is not None


def test_character_agent_runtime_keeps_self_body_as_actor_goal_not_frame() -> None:
    runtime = _local_runtime()
    event = SelfBodyPerceivedEvent(
        actor_id="char_b",
        body_state_class="interaction_strain",
        producer_ts=320,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="body_state_result/interaction_strain=engaged",
        source_body_result_id="body_result:char_b:320",
    )

    commands = runtime.ingest_self_body_perceived_event(event)

    assert commands
    assert isinstance(commands[0], CharacterGoalCommand)
    assert commands[0].command_type == "observe"


def test_character_agent_runtime_threads_self_body_state_into_legacy_command_physiology_hint() -> None:
    runtime = _local_runtime()
    event = SelfBodyPerceivedEvent(
        actor_id="char_b",
        body_state_class="interaction_strain",
        producer_ts=321,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="body_state_result/interaction_strain=engaged",
        source_body_result_id="body_result:char_b:321",
    )

    commands = runtime.ingest_self_body_perceived_event(event)

    assert commands
    assert isinstance(commands[0], CharacterGoalCommand)
    assert commands[0].physiology_hint == "elevated"
