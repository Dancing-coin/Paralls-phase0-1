from app.models.character_agent_runtime import (
    CharacterIntentDecision,
    CharacterInterpretation,
    CharacterPresentationCommand,
    CharacterPrivateWorldSnapshot,
)


class CharacterAgentL4Adapter:
    def build_commands(
        self,
        snapshot: CharacterPrivateWorldSnapshot,
        interpretation: CharacterInterpretation,
        decision: CharacterIntentDecision,
    ) -> list[CharacterPresentationCommand]:
        target = interpretation.attention_target or (snapshot.attention_targets[0] if snapshot.attention_targets else None)
        command = CharacterPresentationCommand(
            actor_id=decision.actor_id,
            output_type=decision.selected_intent,
            producer_ts=snapshot.updated_at,
            causation_id=f"character_agent:{snapshot.updated_at}",
            correlation_id=f"character_agent:{snapshot.updated_at}",
            target_actor_id=target if target and target.startswith("char_") else None,
            target_object_id=target if target and target.startswith("obj_") else None,
            target_environment_id=target if target and target.startswith("env_") else None,
            physiology_hint="elevated" if decision.selected_intent == "physiology_hint" else None,
        )
        return [command]
