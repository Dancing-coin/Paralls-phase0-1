from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.models.siming_event import SimingOutput
from app.services.siming_debug_projection import SimingDebugProjection


def make_visual_fact_event() -> AuthorityEvent:
    return AuthorityEvent(
        event_id="visual_fact:300:light_drop",
        event_type="visual_fact_event",
        producer_ts=300,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source=AuthorityEventSource(layer="L1", system="visual_fact", actor_id="char_c"),
        routing=AuthorityEventRouting(audience_mode="room", routing_mode="event_type", target_ids=["siming"]),
        priority="p2",
        ttl=5000,
        durability="replayable",
        causation_id="visual_fact:300",
        correlation_id="scene-beat-300",
        payload={
            "fact_type": "light_level_drop",
            "established_fact_id": "visual_fact:300:light_drop",
            "target_environment_id": "env_lamp",
        },
    )


def test_siming_debug_projection_builds_director_snapshot() -> None:
    event = make_visual_fact_event()
    decision = SimingOutput(
        output_type="intervention_decision",
        room_id=event.room_id,
        scene_id=event.scene_id,
        zone_id=event.zone_id,
        causation_id=event.event_id,
        correlation_id=event.correlation_id,
        producer_ts=303,
        selected_path="visual_fact_path",
        intervention_band="fact_reveal",
        payload={"decision_id": "decision_300"},
    )
    projection = SimingDebugProjection()

    state = projection.project_snapshot(
        source_event=event,
        fairness_summary="visibility imbalance detected around env_lamp",
        intervention_candidate="fact_reveal:env_lamp",
        intervention_decision="approved",
        selected_path=decision.selected_path or "",
        intervention_band=decision.intervention_band or "",
        target_ref="env_lamp",
        reason_summary="make the light drop legible to the cast",
        downstream_status="published",
        no_action_reason="",
    )

    assert state.fairness_summary == "visibility imbalance detected around env_lamp"
    assert state.intervention_candidate == "fact_reveal:env_lamp"
    assert state.selected_path == "visual_fact_path"
    assert state.target_ref == "env_lamp"


def test_siming_debug_projection_builds_no_action_and_decision_events() -> None:
    event = make_visual_fact_event()
    projection = SimingDebugProjection()

    decision_event = projection.project_event(
        source_event=event,
        stage="intervention_decision",
        summary="siming approved a visual fact reveal for env_lamp",
        selected_path="visual_fact_path",
        intervention_band="fact_reveal",
        target_ref="env_lamp",
        reason_summary="char_b needs a clearer cue",
        downstream_status="published",
        no_action_reason="",
    )
    no_action_event = projection.project_event(
        source_event=event,
        stage="no_action",
        summary="siming declined to intervene",
        selected_path="no_action",
        intervention_band="none",
        target_ref="",
        reason_summary="",
        downstream_status="audit_only",
        no_action_reason="no eligible intervention",
    )

    assert decision_event.stage == "intervention_decision"
    assert decision_event.downstream_status == "published"
    assert no_action_event.stage == "no_action"
    assert no_action_event.no_action_reason == "no eligible intervention"
