from app.models.authority_event import AuthorityEvent
from app.models.siming_runtime_state import ObservedSimingEvent
from app.services.siming_narrative_core import SimingNarrativeCore


def make_event(event_type: str, payload: dict[str, object]) -> AuthorityEvent:
    return AuthorityEvent.model_validate(
        {
            "event_id": f"{event_type}:300",
            "event_type": event_type,
            "producer_ts": 300,
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "source": {"layer": "L1", "system": "visual_fact", "actor_id": "char_c"},
            "routing": {"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["siming"]},
            "priority": "p2",
            "ttl": 5000,
            "durability": "replayable",
            "causation_id": f"{event_type}:300",
            "correlation_id": "corr_demo",
            "payload": payload,
        }
    )


def observed(event: AuthorityEvent) -> ObservedSimingEvent:
    return ObservedSimingEvent.from_authority_event(event)


def test_visual_fact_creates_unresolved_reveal_obligation_and_seed() -> None:
    core = SimingNarrativeCore()
    event = make_event(
        "visual_fact_event",
        {
            "fact_type": "light_level_drop",
            "established_fact_id": "visual_fact:300:light",
            "target_environment_id": "env_lamp",
            "target_actor_id": "char_b",
        },
    )

    result = core.update([observed(event)])

    assert result.state.active_phase == "rising"
    assert result.state.pressure_level == "normal"
    assert [item.obligation_type for item in result.ledger.obligations] == ["unresolved_reveal"]
    assert result.seeds[0].seed_type == "fact_reveal"
    assert result.seeds[0].basis_obligation_refs == [result.ledger.obligations[0].obligation_id]
    assert result.seeds[0].target_refs == ["char_b", "env_lamp"]


def test_constraint_rejection_creates_recovery_obligation() -> None:
    core = SimingNarrativeCore()
    event = make_event(
        "constraint_state_event",
        {
            "constraint_summary": "locked cabinet rejected",
            "target_object_id": "obj_cabinet",
        },
    )

    result = core.update([observed(event)])

    assert [item.obligation_type for item in result.ledger.obligations] == ["constraint_recovery"]
    assert result.seeds[0].suggested_band == "opportunity"
    assert "phase2_projection_required" not in result.seeds[0].risk_tags


def test_repeated_unresolved_obligations_raise_pressure_without_llm() -> None:
    core = SimingNarrativeCore()
    event = make_event(
        "visual_fact_event",
        {
            "fact_type": "light_level_drop",
            "established_fact_id": "visual_fact:300:light",
            "target_actor_id": "char_b",
        },
    )

    first = core.update([observed(event)])
    second = core.update([observed(event)])

    assert first.state.pressure_level == "normal"
    assert second.state.pressure_level == "elevated"
    assert all(seed.source == "narrative_core" for seed in second.seeds)
