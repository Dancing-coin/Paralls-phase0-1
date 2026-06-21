from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.models.character_agent_runtime import CharacterInterpretation
from app.models.character_perceived import CharacterPerceivedEvent
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from app.character_agent.gateway.model_gateway import CharacterModelGateway


class CharacterAgentL2Service:
    def __init__(self, gateway: CharacterModelGateway | None = None) -> None:
        self._gateway = gateway or CharacterModelGateway()

    def prepare_reasoning_request(
        self,
        *,
        snapshot: CharacterPrivateWorldSnapshot,
        event: CharacterPerceivedEvent | SelfBodyPerceivedEvent,
        memory_bundle: dict[str, list[dict[str, object]]],
        control_mode: str,
        working_memory_state: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return self._gateway.prepare_run_request(
            task_kind="l2_reasoning",
            context={
                "actor_id": snapshot.actor_id,
                "control_mode": control_mode,
                "snapshot": snapshot.model_dump(),
                "memory": memory_bundle,
                "working_memory_state": working_memory_state or {},
                "event": event.model_dump(),
            },
        )

    def map_reasoning_output(
        self,
        *,
        actor_id: str,
        output: dict[str, object],
    ) -> CharacterInterpretation:
        return CharacterInterpretation(
            actor_id=actor_id,
            interpreted_summary=str(output.get("interpreted_summary", "") or ""),
            interpretation_type=str(output.get("interpretation_type", "state_change") or "state_change"),
            salience_score=float(output.get("salience_score", 0.0) or 0.0),
            ambiguity_level=str(output.get("ambiguity_level", "low") or "low"),
            risk_level=str(output.get("risk_level", "low") or "low"),
            opportunity_level=str(output.get("opportunity_level", "low") or "low"),
            attention_target=str(output.get("attention_target", "") or "") or None,
            inner_prompt_candidate=str(output.get("inner_prompt_candidate", "") or "") or None,
        )

    def interpret_perceived_event(
        self,
        snapshot: CharacterPrivateWorldSnapshot,
        event: CharacterPerceivedEvent,
        *,
        memory_bundle: dict[str, list[dict[str, object]]] | None = None,
        control_mode: str = "agent_full_auto",
        working_memory_state: dict[str, object] | None = None,
    ) -> CharacterInterpretation:
        model_output = self._gateway.run_task(
            task_kind="l2_reasoning",
            context={
                "actor_id": snapshot.actor_id,
                "control_mode": control_mode,
                "snapshot": snapshot.model_dump(),
                "memory": memory_bundle or {
                    "working_memory": [],
                    "episodic_memories": [],
                    "relational_memories": [],
                },
                "working_memory_state": working_memory_state or {},
                "event": event.model_dump(),
            },
        )
        return self.map_reasoning_output(actor_id=event.actor_id, output=model_output)

    def interpret_self_body_event(
        self,
        snapshot: CharacterPrivateWorldSnapshot,
        event: SelfBodyPerceivedEvent,
        *,
        memory_bundle: dict[str, list[dict[str, object]]] | None = None,
        control_mode: str = "agent_full_auto",
        working_memory_state: dict[str, object] | None = None,
    ) -> CharacterInterpretation:
        model_output = self._gateway.run_task(
            task_kind="l2_reasoning",
            context={
                "actor_id": snapshot.actor_id,
                "control_mode": control_mode,
                "snapshot": snapshot.model_dump(),
                "memory": memory_bundle or {
                    "working_memory": [],
                    "episodic_memories": [],
                    "relational_memories": [],
                },
                "working_memory_state": working_memory_state or {},
                "event": event.model_dump(),
            },
        )
        return self.map_reasoning_output(actor_id=event.actor_id, output=model_output)

    def interpret_siming_output(
        self,
        snapshot: CharacterPrivateWorldSnapshot,
        payload: dict[str, object],
        *,
        memory_bundle: dict[str, list[dict[str, object]]] | None = None,
        control_mode: str = "agent_full_auto",
        working_memory_state: dict[str, object] | None = None,
    ) -> CharacterInterpretation:
        model_output = self._gateway.run_task(
            task_kind="l2_reasoning",
            context={
                "actor_id": snapshot.actor_id,
                "control_mode": control_mode,
                "snapshot": snapshot.model_dump(),
                "memory": memory_bundle or {
                    "working_memory": [],
                    "episodic_memories": [],
                    "relational_memories": [],
                },
                "working_memory_state": working_memory_state or {},
                "event": payload,
            },
        )
        return self.map_reasoning_output(actor_id=snapshot.actor_id, output=model_output)
