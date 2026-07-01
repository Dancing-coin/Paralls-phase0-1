from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.config import settings


class DialogueService:
    def __init__(self, gateway: CharacterModelGateway | None = None) -> None:
        self._gateway = gateway or CharacterModelGateway()

    def generate_reply(self, actor_id: str, content: str) -> tuple[str, str]:
        route_override = "local_only" if settings.dialogue_mode == "stub" else None
        output = self._gateway.run_task(
            task_kind="dialogue_generation",
            context={
                "actor_id": actor_id,
                "control_mode": "dialogue_service",
                "snapshot": {},
                "memory": {
                    "working_memory": [],
                    "episodic_memories": [],
                    "relational_memories": [],
                },
                "event": {
                    "content": content,
                    "target_actor_id": actor_id,
                    "intent_type": "dialogue_submit",
                },
            },
            route_override=route_override,
        )
        return (
            str(output.get("content", "") or ""),
            str(output.get("tone", "") or "neutral"),
        )

    def generate_utterance(self, actor_id: str, target_actor_id: str, content: str) -> tuple[str, str]:
        route_override = "local_only" if settings.dialogue_mode == "stub" else None
        output = self._gateway.run_task(
            task_kind="dialogue_generation",
            context={
                "actor_id": actor_id,
                "control_mode": "agent_initiated_utterance",
                "snapshot": {},
                "memory": {
                    "working_memory": [],
                    "episodic_memories": [],
                    "relational_memories": [],
                },
                "event": {
                    "content": content,
                    "target_actor_id": target_actor_id,
                    "intent_type": "agent_initiated_utterance",
                },
            },
            route_override=route_override,
        )
        return (
            str(output.get("content", "") or ""),
            str(output.get("tone", "") or "neutral"),
        )
