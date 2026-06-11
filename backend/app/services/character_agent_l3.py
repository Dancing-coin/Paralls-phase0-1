from app.models.character_agent_runtime import CharacterIntentDecision, CharacterInterpretation


class CharacterAgentL3Service:
    def select_intent(self, interpretation: CharacterInterpretation) -> CharacterIntentDecision:
        selected_intent = "observe_target"
        if interpretation.risk_level in {"medium", "high"}:
            selected_intent = "physiology_hint"
        elif interpretation.opportunity_level in {"medium", "high"}:
            selected_intent = "attention_shift"
        return CharacterIntentDecision(
            actor_id=interpretation.actor_id,
            selected_intent=selected_intent,
            persona_passed=True,
            logic_passed=True,
            gain_loss_passed=True,
            rationale=interpretation.interpreted_summary,
        )
