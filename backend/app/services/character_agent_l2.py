from app.models.character_agent_runtime import CharacterInterpretation, CharacterPrivateWorldSnapshot
from app.models.character_perceived import CharacterPerceivedEvent
from app.models.self_body_perceived import SelfBodyPerceivedEvent


class CharacterAgentL2Service:
    def interpret_perceived_event(
        self,
        snapshot: CharacterPrivateWorldSnapshot,
        event: CharacterPerceivedEvent,
    ) -> CharacterInterpretation:
        summary = event.perceived_summary
        interpretation_type = "opportunity" if "visual_fact" in summary else "state_change"
        return CharacterInterpretation(
            actor_id=event.actor_id,
            interpreted_summary=summary,
            interpretation_type=interpretation_type,
            salience_score=event.clarity_score,
            ambiguity_level="low" if event.certainty_score >= 0.6 else "medium",
            risk_level="low",
            opportunity_level="medium" if interpretation_type == "opportunity" else "low",
            attention_target=snapshot.attention_targets[0] if snapshot.attention_targets else None,
            inner_prompt_candidate=f"{event.actor_id}:{summary}",
        )

    def interpret_self_body_event(
        self,
        snapshot: CharacterPrivateWorldSnapshot,
        event: SelfBodyPerceivedEvent,
    ) -> CharacterInterpretation:
        return CharacterInterpretation(
            actor_id=event.actor_id,
            interpreted_summary=event.perceived_summary,
            interpretation_type="body_state",
            salience_score=snapshot.clarity_score,
            ambiguity_level="low",
            risk_level="medium",
            opportunity_level="low",
            attention_target=snapshot.attention_targets[0] if snapshot.attention_targets else None,
            inner_prompt_candidate=f"{event.actor_id}:{event.body_state_class}",
        )

    def interpret_siming_output(
        self,
        snapshot: CharacterPrivateWorldSnapshot,
        payload: dict[str, object],
    ) -> CharacterInterpretation:
        summary = str(payload.get("presentation_hint", "") or "siming_catalyst")
        return CharacterInterpretation(
            actor_id=snapshot.actor_id,
            interpreted_summary=summary,
            interpretation_type="catalyst",
            salience_score=snapshot.clarity_score,
            ambiguity_level="low",
            risk_level="low",
            opportunity_level="medium",
            attention_target=snapshot.attention_targets[0] if snapshot.attention_targets else None,
            inner_prompt_candidate=f"{snapshot.actor_id}:{summary}",
        )
