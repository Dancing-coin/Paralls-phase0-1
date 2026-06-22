from app.services.character_agent_runtime import CharacterAgentRuntime
from app.models.authority_event import AuthorityEvent
from app.services.siming_character_dispatch_adapter import SimingCharacterDispatchAdapter


def make_siming_event(
    *,
    event_type: str = "siming.impulse",
    target_ids: list[str] | None = None,
) -> AuthorityEvent:
    return AuthorityEvent.model_validate(
        {
            "event_id": "siming:impulse:101:cause:1",
            "event_type": event_type,
            "producer_ts": 101,
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "source": {"layer": "L2", "system": "siming.dispatcher", "actor_id": None},
            "routing": {
                "audience_mode": "targeted",
                "routing_mode": "event_type",
                "target_ids": target_ids or ["char_a", "char_b"],
            },
            "priority": "p1",
            "ttl": 5000,
            "durability": "replayable",
            "causation_id": "cause:1",
            "correlation_id": "corr:1",
            "payload": {
                "message_id": "msg:siming:1",
                "intervention_band": event_type.removeprefix("siming."),
                "presentation_hint": "notice the movement near the desk",
            },
        }
    )


def test_adapter_fans_out_one_delivery_per_actor() -> None:
    runtime = CharacterAgentRuntime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime)

    result = adapter.dispatch(make_siming_event())

    assert len(result.delivery_inputs) == 2
    assert {entry.actor_id for entry in result.delivery_inputs} == {"char_a", "char_b"}
    assert len({entry.delivery_id for entry in result.delivery_inputs}) == 2


def test_adapter_rejects_expired_delivery_before_runtime_ingress() -> None:
    runtime = CharacterAgentRuntime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime, now_ts_provider=lambda: 999999)

    result = adapter.dispatch(make_siming_event())

    assert result.delivery_inputs == []
    assert len(result.audit_summaries) == 1
    assert result.audit_summaries[0].status == "expired"


def test_adapter_preserves_high_level_semantics_without_low_level_command_fields() -> None:
    runtime = CharacterAgentRuntime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime)

    result = adapter.dispatch(make_siming_event(event_type="siming.fact_reveal", target_ids=["char_a"]))

    payload = result.delivery_inputs[0]
    assert payload.band == "fact_reveal"
    assert payload.input_type == "siming_high_level_message"
    assert "go_to_position" not in payload.model_dump()
