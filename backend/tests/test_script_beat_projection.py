from app.models.observatory import ActorDramaticEvent, ScriptBeat, SimingDramaticEvent, WorldOutcomeEvent
from app.services.script_beat_projection import ScriptBeatProjection


def test_script_beat_projection_groups_events_by_correlation_id() -> None:
    projection = ScriptBeatProjection()
    actor_event = ActorDramaticEvent(
        actor_id="char_a",
        producer_ts=600,
        causation_id="cause-600",
        correlation_id="corr-600",
        participants=["char_a", "obj_letter"],
        stage="decision",
        summary="char_a selected inspect_object toward obj_letter",
        focus_target="obj_letter",
        intent_label="inspect_object",
        detail={},
    )
    siming_event = SimingDramaticEvent(
        producer_ts=601,
        causation_id="cause-600",
        correlation_id="corr-600",
        participants=["char_a", "obj_letter"],
        stage="intervention_decision",
        summary="siming highlighted the letter reveal",
        selected_path="visual_fact_path",
        intervention_band="fact_reveal",
        target_ref="obj_letter",
        reason_summary="make the reveal legible",
        downstream_status="published",
        no_action_reason="",
    )
    world_event = WorldOutcomeEvent(
        producer_ts=602,
        causation_id="cause-600",
        correlation_id="corr-600",
        participants=["char_a", "obj_letter"],
        actor_id="char_a",
        target_ref="obj_letter",
        request_type="inspect",
        settlement_status="accepted",
        constraint_summary="",
        world_change_summary="obj_letter changed from hidden to visible",
        dramatic_consequence_summary="the letter is now visible to the cast",
        source_message_type="world_result",
        detail={},
    )

    beat = projection.project([actor_event], [siming_event], [world_event])

    assert isinstance(beat, ScriptBeat)
    assert beat.correlation_id == "corr-600"
    assert beat.participants == ["char_a", "obj_letter"]
    assert beat.actor_event_refs == [actor_event.event_ref]
    assert beat.siming_event_refs == [siming_event.event_ref]
    assert beat.world_event_refs == [world_event.event_ref]
    assert "char_a" in beat.dramatic_summary
    assert "obj_letter" in beat.dramatic_summary
