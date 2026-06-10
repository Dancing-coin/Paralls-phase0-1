import app.main as main
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.models.authority_event import AuthorityEvent
from app.models.visual_fact import VisualFactEvent
from app.ws_protocol import Envelope


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


def _reset_runtime_state_with_local_character_model() -> None:
    main.reset_runtime_state()
    runtime = CharacterAgentRuntime()
    local_gateway = _LocalGateway()
    runtime._l2 = CharacterAgentL2Service(gateway=local_gateway, profile_registry=runtime._profile_registry)
    runtime._l3 = CharacterAgentL3Service(gateway=local_gateway)
    main.character_agent_runtime = runtime
    main.siming_event_pipeline._character_dispatch_adapter._runtime = runtime


def test_visual_fact_light_drop_returns_projected_siming_authority_event() -> None:
    _reset_runtime_state_with_local_character_model()

    outbound = main._handle_envelope(
        Envelope(
            message_type="visual_fact_event",
            payload=VisualFactEvent(
                actor_id="char_c",
                room_id="room_demo",
                scene_id="scene_demo",
                zone_id="zone_focus",
                producer_ts=300,
                fact_type="light_level_drop",
                relation_type="environment_light_drop",
                target_environment_id="env_lamp",
            ).model_dump(),
        )
    )

    projected = [
        message
        for message in outbound
        if message.get("message_type") == "authority_event"
        and message.get("payload", {}).get("event_type") == "siming.visual_observability_request"
        and str(message.get("payload", {}).get("payload", {}).get("established_fact_id", "")).startswith(
            "visual_fact:300:char_c:light_level_drop"
        )
    ]
    assert len(projected) == 1
    payload = projected[0]["payload"]
    assert payload["payload"]["established_fact_id"].startswith("visual_fact:300:char_c:light_level_drop")
    assert payload["payload"]["presentation_hint"] == "increase observability for established light change"


def test_non_visual_siming_events_do_not_project_visual_observability_request() -> None:
    main.reset_runtime_state()

    main.frontend_authority_event_projector.handle_event(
        AuthorityEvent.model_validate(
            {
                "event_id": "siming:audit:301",
                "event_type": "siming.audit_recorded",
                "producer_ts": 301,
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "source": {"layer": "L2", "system": "siming.audit", "actor_id": None},
                "routing": {
                    "audience_mode": "internal",
                    "routing_mode": "event_type",
                    "target_ids": [],
                },
                "priority": "p2",
                "ttl": 5000,
                "durability": "replayable",
                "causation_id": "visual_fact:301",
                "correlation_id": "visual_fact:301",
                "payload": {"status": "recorded"},
            }
        )
    )
    outbound = main.frontend_authority_event_projector.drain()

    assert all(
        message.get("payload", {}).get("event_type") != "siming.visual_observability_request"
        for message in outbound
        if message.get("message_type") == "authority_event"
    )
