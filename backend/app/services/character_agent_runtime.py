from app.models.character_agent_runtime import CharacterGoalCommand
from app.models.character_agent_runtime import CHARACTER_ACTOR_AUTONOMY_MODES
from app.models.character_agent_runtime import SHARED_CHARACTER_COMMANDS
from app.models.character_perceived import CharacterPerceivedEvent
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from app.services.character_agent_l1 import CharacterAgentL1Service
from app.services.character_agent_l2 import CharacterAgentL2Service
from app.services.character_agent_l3 import CharacterAgentL3Service
from app.services.character_agent_l4_adapter import CharacterAgentL4Adapter


class CharacterAgentRuntime:
    SUPPORTED_ACTORS = {"char_a", "char_b"}
    AWAY_CONSERVATIVE_ALLOWED_COMMANDS = {"look_at", "observe", "speak"}

    def __init__(self) -> None:
        self._l1 = CharacterAgentL1Service()
        self._l2 = CharacterAgentL2Service()
        self._l3 = CharacterAgentL3Service()
        self._l4 = CharacterAgentL4Adapter()

    def ingest_character_perceived_event(self, event: CharacterPerceivedEvent) -> list[CharacterGoalCommand]:
        if event.actor_id not in self.SUPPORTED_ACTORS:
            return []
        snapshot = self._l1.apply_character_perceived_event(event)
        interpretation = self._l2.interpret_perceived_event(snapshot, event)
        decision = self._l3.select_intent(interpretation)
        return self._l4.build_commands(snapshot, interpretation, decision)

    def is_command_allowed_for_mode(self, mode: str, command: str) -> bool:
        if mode not in CHARACTER_ACTOR_AUTONOMY_MODES:
            return False
        if command not in SHARED_CHARACTER_COMMANDS:
            return False
        if mode == "away_conservative_takeover":
            return command in self.AWAY_CONSERVATIVE_ALLOWED_COMMANDS
        return True

    def ingest_self_body_perceived_event(self, event: SelfBodyPerceivedEvent) -> list[CharacterGoalCommand]:
        if event.actor_id not in self.SUPPORTED_ACTORS:
            return []
        snapshot = self._l1.apply_self_body_perceived_event(event)
        interpretation = self._l2.interpret_self_body_event(snapshot, event)
        decision = self._l3.select_intent(interpretation)
        return self._l4.build_commands(snapshot, interpretation, decision)

    def ingest_siming_output(self, payload: dict[str, object]) -> list[CharacterGoalCommand]:
        actor_id = str(payload.get("target_actor_id", "") or "")
        if actor_id not in self.SUPPORTED_ACTORS:
            return []
        snapshot = self._l1.apply_siming_output(payload)
        interpretation = self._l2.interpret_siming_output(snapshot, payload)
        decision = self._l3.select_intent(interpretation)
        return self._l4.build_commands(snapshot, interpretation, decision)
