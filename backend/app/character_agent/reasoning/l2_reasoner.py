from copy import deepcopy

from app.character_agent.gateway.context_builder import CharacterContextBuilder
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.character_agent.profile.loader import CharacterProfileLoader
from app.character_agent.profile.registry import CharacterProfileRegistry
from app.models.character_agent_runtime import CharacterInterpretation
from app.models.character_perceived import CharacterPerceivedEvent
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from app.character_agent.gateway.model_gateway import CharacterModelGateway


class CharacterAgentL2Service:
    def __init__(
        self,
        gateway: CharacterModelGateway | None = None,
        profile_loader: CharacterProfileLoader | None = None,
        profile_registry: CharacterProfileRegistry | None = None,
    ) -> None:
        self._gateway = gateway or CharacterModelGateway()
        self._context_builder = CharacterContextBuilder()
        self._profile_registry = profile_registry
        self._profile_loader = profile_loader or CharacterProfileLoader()
        self._profile_cache: dict[str, dict[str, object]] = {}

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
            context=self._reasoning_context(
                actor_id=snapshot.actor_id,
                snapshot=snapshot.model_dump(),
                event=event.model_dump(),
                memory_bundle=memory_bundle,
                control_mode=control_mode,
                working_memory_state=working_memory_state,
            ),
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
            context=self._reasoning_context(
                actor_id=snapshot.actor_id,
                snapshot=snapshot.model_dump(),
                event=event.model_dump(),
                memory_bundle=memory_bundle,
                control_mode=control_mode,
                working_memory_state=working_memory_state,
            ),
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
            context=self._reasoning_context(
                actor_id=snapshot.actor_id,
                snapshot=snapshot.model_dump(),
                event=event.model_dump(),
                memory_bundle=memory_bundle,
                control_mode=control_mode,
                working_memory_state=working_memory_state,
            ),
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
            context=self._reasoning_context(
                actor_id=snapshot.actor_id,
                snapshot=snapshot.model_dump(),
                event=payload,
                memory_bundle=memory_bundle,
                control_mode=control_mode,
                working_memory_state=working_memory_state,
            ),
        )
        return self.map_reasoning_output(actor_id=snapshot.actor_id, output=model_output)

    def _reasoning_context(
        self,
        *,
        actor_id: str,
        snapshot: dict[str, object],
        event: dict[str, object],
        memory_bundle: dict[str, list[dict[str, object]]] | None,
        control_mode: str,
        working_memory_state: dict[str, object] | None,
    ) -> dict[str, object]:
        context = self._context_builder.build_context(
            actor_id=actor_id,
            snapshot=snapshot,
            memory_bundle=memory_bundle or {},
            control_mode=control_mode,
            working_memory_state=working_memory_state or {},
            profile=self._profile_for_actor(actor_id),
        )
        context["event"] = dict(event)
        return context

    def _profile_for_actor(self, actor_id: str) -> dict[str, object]:
        cached_profile = self._profile_cache.get(actor_id)
        if cached_profile is not None:
            return deepcopy(cached_profile)

        if self._profile_registry is not None:
            profile = self._profile_registry.get(actor_id).model_dump()
        else:
            profile = self._profile_loader.load(actor_id).model_dump()
        self._profile_cache[actor_id] = deepcopy(profile)
        return deepcopy(profile)
