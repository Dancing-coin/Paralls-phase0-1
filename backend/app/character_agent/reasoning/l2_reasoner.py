from copy import deepcopy

from app.character_agent.gateway.context_builder import CharacterContextBuilder
from app.character_agent.models.cognition_delta import (
    CharacterBeliefDelta,
    CharacterDynamicStateDelta,
    CharacterHigherOrderDelta,
    CharacterSocialDelta,
)
from app.character_agent.models.goal_runtime import CharacterGoalHint
from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.character_agent.models.working_memory_state import CharacterWorkingMemoryState
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
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
        control_mode: str,
        working_memory_state: dict[str, object] | CharacterWorkingMemoryState | None = None,
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
            belief_deltas=[
                CharacterBeliefDelta(
                    proposition_key=str(item.get("proposition_key", "") or ""),
                    proposition=str(item.get("proposition", "") or ""),
                    state=str(item.get("state", "suspected") or "suspected"),
                    confidence=float(item.get("confidence", 0.0) or 0.0),
                )
                for item in output.get("belief_deltas", [])
                if isinstance(item, dict) and str(item.get("proposition_key", "") or "")
            ],
            social_deltas=[
                CharacterSocialDelta(
                    entity_id=str(item.get("entity_id", "") or ""),
                    trust_baseline=float(item.get("trust_baseline", 0.5) or 0.5),
                    suspicion_baseline=float(item.get("suspicion_baseline", 0.0) or 0.0),
                    intimacy=float(item.get("intimacy", 0.0) or 0.0),
                    dependency=float(item.get("dependency", 0.0) or 0.0),
                    unresolved_tension=float(item.get("unresolved_tension", 0.0) or 0.0),
                    shared_secret_refs=[
                        str(ref)
                        for ref in item.get("shared_secret_refs", [])
                        if str(ref)
                    ]
                    if isinstance(item.get("shared_secret_refs", []), list)
                    else [],
                )
                for item in output.get("social_deltas", [])
                if isinstance(item, dict) and str(item.get("entity_id", "") or "")
            ],
            higher_order_deltas=[
                CharacterHigherOrderDelta(
                    subject_actor_id=str(item.get("subject_actor_id", "") or ""),
                    proposition_key=str(item.get("proposition_key", "") or ""),
                    meta_belief=str(item.get("meta_belief", "") or ""),
                    confidence=float(item.get("confidence", 0.0) or 0.0),
                )
                for item in output.get("higher_order_deltas", [])
                if isinstance(item, dict) and str(item.get("subject_actor_id", "") or "") and str(item.get("meta_belief", "") or "")
            ],
            dynamic_state_delta=CharacterDynamicStateDelta(
                **{
                    str(key): float(value)
                    for key, value in dict(output.get("dynamic_state_delta", {})).items()
                    if isinstance(value, (int, float))
                }
            )
            if isinstance(output.get("dynamic_state_delta", {}), dict)
            else CharacterDynamicStateDelta(),
            goal_hints=[
                CharacterGoalHint(
                    goal=str(item.get("goal", "") or ""),
                    source=str(item.get("source", "") or "model"),
                    strength=float(item.get("strength", 0.5) or 0.5),
                    evidence_tags=[
                        str(tag)
                        for tag in item.get("evidence_tags", [])
                        if str(tag)
                    ]
                    if isinstance(item.get("evidence_tags", []), list)
                    else [],
                )
                for item in output.get("goal_hints", [])
                if isinstance(item, dict) and str(item.get("goal", "") or "")
            ],
            reasoning_trace_summary=str(output.get("reasoning_trace_summary", "") or "") or None,
        )

    def interpret_perceived_event(
        self,
        snapshot: CharacterPrivateWorldSnapshot,
        event: CharacterPerceivedEvent,
        *,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None = None,
        control_mode: str = "agent_full_auto",
        working_memory_state: dict[str, object] | CharacterWorkingMemoryState | None = None,
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
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None = None,
        control_mode: str = "agent_full_auto",
        working_memory_state: dict[str, object] | CharacterWorkingMemoryState | None = None,
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
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None = None,
        control_mode: str = "agent_full_auto",
        working_memory_state: dict[str, object] | CharacterWorkingMemoryState | None = None,
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
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle | None,
        control_mode: str,
        working_memory_state: dict[str, object] | CharacterWorkingMemoryState | None,
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
