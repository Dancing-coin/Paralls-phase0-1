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


def test_script_beat_projection_keeps_pair_member_targeted_siming_context_for_pair() -> None:
    projection = ScriptBeatProjection()
    actor_events = [
        ActorDramaticEvent(
            actor_id="char_a",
            producer_ts=700,
            causation_id="cause-700",
            correlation_id="corr-700",
            participants=["char_a", "char_b"],
            stage="decision",
            summary="char_a chooses a guarded reply to char_b",
            focus_target="char_b",
            intent_label="dialogue_reply",
            detail={
                "target_actor_id": "char_b",
                "perceived_summary": "char_b sounds demanding",
                "interpreted_summary": "char_a thinks the request is a test",
                "spoken_content": "I need proof before I agree.",
            },
        ),
        ActorDramaticEvent(
            actor_id="char_b",
            producer_ts=701,
            causation_id="cause-700",
            correlation_id="corr-700",
            participants=["char_a", "char_b"],
            stage="dialogue_writeback",
            summary="char_b pushes back on char_a",
            focus_target="char_a",
            intent_label="dialogue_reply",
            detail={
                "target_actor_id": "char_a",
                "perceived_summary": "char_a is hesitating",
                "interpreted_summary": "char_b reads the pause as resistance",
                "spoken_content": "Then give me one reason to trust you.",
            },
        ),
    ]
    siming_events = [
        SimingDramaticEvent(
            producer_ts=702,
            causation_id="cause-700",
            correlation_id="corr-700",
            participants=["char_a", "char_b"],
            stage="intervention_decision",
            summary="siming tightens the trust pressure between char_a and char_b",
            selected_path="trust_pressure_path",
            intervention_band="pressure",
            target_ref="char_b",
            reason_summary="keep the exchange focused on whether either side can trust the other",
            downstream_status="published",
            no_action_reason="",
        )
    ]

    beat = projection.project(actor_events, siming_events, [])

    assert beat.dialogue_pairs
    assert beat.dialogue_pairs[0]["pair_key"] == "char_a<->char_b"
    assert beat.dialogue_pairs[0]["siming_pressure_context"] == (
        "司命关注 char_b：siming tightens the trust pressure between char_a and char_b"
        "（原因：keep the exchange focused on whether either side can trust the other）"
    )


def test_script_beat_projection_rejects_third_party_targeted_siming_context_for_pair() -> None:
    projection = ScriptBeatProjection()
    actor_events = [
        ActorDramaticEvent(
            actor_id="char_a",
            producer_ts=800,
            causation_id="cause-800",
            correlation_id="corr-800",
            participants=["char_a", "char_c"],
            stage="decision",
            summary="char_a commits to watching char_a",
            focus_target="char_a",
            intent_label="observe",
            detail={
                "target_actor_id": "char_a",
                "perceived_summary": "watch char_a",
                "interpreted_summary": "watch char_a",
                "spoken_content": "watch char_a",
            },
        )
    ]
    siming_events = [
        SimingDramaticEvent(
            producer_ts=801,
            causation_id="cause-800",
            correlation_id="corr-800",
            participants=["char_a", "char_c"],
            stage="dispatch_finalized",
            summary="conversation fact reveal published",
            selected_path="character_input_path",
            intervention_band="fact_reveal",
            target_ref="char_c",
            reason_summary="conversation candidate fact reveal requested",
            downstream_status="published",
            no_action_reason="",
        )
    ]

    beat = projection.project(actor_events, siming_events, [])

    assert beat.dialogue_pairs
    assert beat.dialogue_pairs[0]["pair_key"] == "char_a<->char_a"
    assert beat.dialogue_pairs[0]["siming_pressure_context"] == ""


def test_script_beat_projection_keeps_explicitly_delivered_third_party_siming_context_for_pair() -> None:
    projection = ScriptBeatProjection()
    actor_events = [
        ActorDramaticEvent(
            actor_id="char_a",
            producer_ts=850,
            causation_id="cause-850",
            correlation_id="corr-850",
            participants=["char_a", "char_c"],
            stage="decision",
            summary="char_a commits to watching char_a",
            focus_target="char_a",
            intent_label="observe",
            detail={
                "target_actor_id": "char_a",
                "perceived_summary": "watch char_a",
                "interpreted_summary": "watch char_a",
                "spoken_content": "watch char_a",
            },
        ),
        ActorDramaticEvent(
            actor_id="char_a",
            producer_ts=851,
            causation_id="conversation_candidate:850:char_c",
            correlation_id="focus:850",
            participants=["char_a", "char_c"],
            stage="siming_output_event",
            summary="watch the shift around char_c",
            focus_target="char_c",
            intent_label="fact_reveal",
            detail={
                "input_type": "siming_high_level_message",
                "target_actor_id": "char_a",
                "causation_id": "conversation_candidate:850:char_c",
                "correlation_id": "focus:850",
                "presentation_hint": "watch the shift around char_c",
            },
        ),
    ]
    siming_events = [
        SimingDramaticEvent(
            producer_ts=852,
            causation_id="conversation_candidate:850:char_c",
            correlation_id="focus:850",
            participants=["char_a", "char_c"],
            stage="dispatch_finalized",
            summary="conversation fact reveal published",
            selected_path="character_input_path",
            intervention_band="fact_reveal",
            target_ref="char_c",
            reason_summary="conversation candidate fact reveal requested",
            downstream_status="published",
            no_action_reason="",
        )
    ]

    beat = projection.project(actor_events, siming_events, [])

    assert beat.dialogue_pairs
    assert beat.dialogue_pairs[0]["pair_key"] == "char_a<->char_a"
    assert beat.dialogue_pairs[0]["siming_pressure_context"] == (
        "司命关注 char_c：conversation fact reveal published"
        "（原因：conversation candidate fact reveal requested）"
    )


def test_script_beat_projection_keeps_untargeted_global_siming_context_for_pair() -> None:
    projection = ScriptBeatProjection()
    actor_events = [
        ActorDramaticEvent(
            actor_id="char_a",
            producer_ts=900,
            causation_id="cause-900",
            correlation_id="corr-900",
            participants=["char_a", "char_b"],
            stage="decision",
            summary="char_a presses char_b for a direct answer",
            focus_target="char_b",
            intent_label="dialogue_reply",
            detail={
                "target_actor_id": "char_b",
                "perceived_summary": "char_b is deflecting",
                "interpreted_summary": "char_a reads the deflection as stalling",
                "spoken_content": "Answer me directly.",
            },
        )
    ]
    siming_events = [
        SimingDramaticEvent(
            producer_ts=901,
            causation_id="cause-900",
            correlation_id="corr-900",
            participants=["char_a", "char_b"],
            stage="dispatch_finalized",
            summary="ambient tension rises around the exchange",
            selected_path="pressure_path",
            intervention_band="pressure",
            target_ref="",
            reason_summary="keep the whole beat focused on the unresolved accusation",
            downstream_status="published",
            no_action_reason="",
        )
    ]

    beat = projection.project(actor_events, siming_events, [])

    assert beat.dialogue_pairs
    assert beat.dialogue_pairs[0]["pair_key"] == "char_a<->char_b"
    assert beat.dialogue_pairs[0]["siming_pressure_context"] == (
        "司命上下文：ambient tension rises around the exchange"
        "（原因：keep the whole beat focused on the unresolved accusation）"
    )
