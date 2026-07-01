from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.models.authority_event import AuthorityEvent
from app.services.siming_character_dispatch_adapter import SimingCharacterDispatchAdapter


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
    runtime = _local_runtime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime)

    result = adapter.dispatch(make_siming_event())

    assert len(result.delivery_inputs) == 2
    assert {entry.actor_id for entry in result.delivery_inputs} == {"char_a", "char_b"}
    assert len({entry.delivery_id for entry in result.delivery_inputs}) == 2


def test_adapter_rejects_expired_delivery_before_runtime_ingress() -> None:
    runtime = _local_runtime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime, now_ts_provider=lambda: 999999)

    result = adapter.dispatch(make_siming_event())

    assert result.delivery_inputs == []
    assert len(result.audit_summaries) == 1
    assert result.audit_summaries[0].status == "expired"


def test_adapter_accepts_delivery_at_exact_ttl_boundary() -> None:
    runtime = _local_runtime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime, now_ts_provider=lambda: 5101)

    result = adapter.dispatch(make_siming_event(target_ids=["char_a"]))

    assert len(result.delivery_inputs) == 1
    assert result.audit_summaries == []


def test_adapter_preserves_high_level_semantics_without_low_level_command_fields() -> None:
    runtime = _local_runtime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime)

    result = adapter.dispatch(make_siming_event(event_type="siming.fact_reveal", target_ids=["char_a"]))

    payload = result.delivery_inputs[0]
    assert payload.band == "fact_reveal"
    assert payload.input_type == "siming_high_level_message"
    assert "go_to_position" not in payload.model_dump()


def test_adapter_records_target_unavailable_for_unsupported_actor() -> None:
    runtime = _local_runtime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime)

    result = adapter.dispatch(make_siming_event(target_ids=["char_a", "char_unknown"]))

    assert [entry.actor_id for entry in result.delivery_inputs] == ["char_a"]
    assert len(result.audit_summaries) == 1
    assert result.audit_summaries[0].actor_id == "char_unknown"
    assert result.audit_summaries[0].status == "target_unavailable"


def test_adapter_falls_back_to_event_id_when_message_id_is_missing() -> None:
    runtime = _local_runtime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime)
    event = make_siming_event(target_ids=["char_a"])
    event.payload.pop("message_id")

    result = adapter.dispatch(event)

    assert result.delivery_inputs[0].message_id == event.event_id
    assert result.delivery_inputs[0].delivery_id == f"delivery:{event.event_id}:char_a:1"


def test_adapter_deduplicates_duplicate_target_ids_per_actor() -> None:
    runtime = _local_runtime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime)

    result = adapter.dispatch(make_siming_event(target_ids=["char_a", "char_a", "char_b"]))

    assert [entry.actor_id for entry in result.delivery_inputs] == ["char_a", "char_b"]
    assert len(result.commands_by_actor) == 2
