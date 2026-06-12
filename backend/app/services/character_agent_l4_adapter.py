from app.models.character_agent_runtime import (
    CharacterGoalCommand,
    CharacterIntentDecision,
    CharacterInterpretation,
    CharacterPrivateWorldSnapshot,
)


class CharacterAgentL4Adapter:
    def build_commands(
        self,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
    ) -> list[CharacterGoalCommand]:
        target = interpretation.attention_target or (snapshot.attention_targets[0] if snapshot.attention_targets else None)
        command = CharacterGoalCommand(
            actor_id=decision.actor_id,
            command_type=self._map_command_type(decision.selected_intent),
            ttl_ms=1000,
            causation_id=f"character_agent:{snapshot.updated_at}",
            correlation_id=f"character_agent:{snapshot.updated_at}",
            producer_ts=snapshot.updated_at,
            target_actor_id=target if target and target.startswith("char_") else None,
            target_object_id=target if target and target.startswith("obj_") else None,
            target_environment_id=target if target and target.startswith("env_") else None,
            role_state_hint="alert" if decision.selected_intent == "attention_shift" else None,
            physiology_hint="elevated" if decision.selected_intent == "physiology_hint" else None,
        )
        return [command]

    def _map_command_type(self, selected_intent: str) -> str:
        if selected_intent == "brief_dialogue_response":
            return "speak"
        if selected_intent == "reposition_step":
            return "approach"
        if selected_intent in {"attention_shift", "observe_target", "role_state_hint", "physiology_hint"}:
            return "observe"
        return "observe"
