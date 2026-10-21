from __future__ import annotations

from copy import deepcopy

from app.character_agent.gateway.context_builder import CharacterContextBuilder
from app.character_agent.mind.affordances import CharacterMindAffordanceAdapter
from app.character_agent.mind.graph_projection import (
    GraphMemoryProjectionProvider,
    NoopGraphMemoryProjectionProvider,
)
from app.character_agent.mind.projectors import (
    AffectiveBodyStateProjector,
    DossierProjectionProjector,
    EffectiveProfileProjector,
    GoalContextProjector,
    MemoryActivationProjector,
    NeedPressureProjector,
    RelationshipContextProjector,
    SupervisionProjector,
    UnresolvedTensionProjector,
)
from app.character_agent.models.mind_frame import (
    CharacterMindFrame,
    CharacterMindFrameTrigger,
    CognitionWorkspace,
    MentalFactorProjectionCard,
    MindFrameLayer,
    MindFrameProvenance,
)
from app.character_agent.models.turn_context import CharacterTurnContext
from app.character_agent.models.self_state_snapshot import SelfStateSnapshot
from app.character_agent.models.external_percept_snapshot import ExternalPerceptSnapshot
from app.character_agent.models.action_execution_state import ActionExecutionState
from app.character_agent.skills.models import StableAbilitySnapshot
from app.character_agent.mind.regulation_projection import project_mental_regulation


class CharacterMindFrameBuilder:
    def __init__(
        self,
        graph_projection_provider: GraphMemoryProjectionProvider | None = None,
    ) -> None:
        self._effective_profile_projector = EffectiveProfileProjector()
        self._dossier_projection_projector = DossierProjectionProjector()
        self._memory_activation_projector = MemoryActivationProjector()
        self._relationship_context_projector = RelationshipContextProjector()
        self._need_pressure_projector = NeedPressureProjector()
        self._affective_body_state_projector = AffectiveBodyStateProjector()
        self._goal_context_projector = GoalContextProjector()
        self._unresolved_tension_projector = UnresolvedTensionProjector()
        self._supervision_projector = SupervisionProjector()
        self._affordance_adapter = CharacterMindAffordanceAdapter()
        self._graph_projection_provider = (
            graph_projection_provider
            if graph_projection_provider is not None
            else NoopGraphMemoryProjectionProvider()
        )

    def build_frame(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        turn_context: CharacterTurnContext | None = None,
        self_state_snapshot: SelfStateSnapshot | None = None,
        external_percepts: list[ExternalPerceptSnapshot] | None = None,
        action_execution_state: ActionExecutionState | None = None,
        event_inbox: list[dict[str, object]] | None = None,
        trigger_event: dict[str, object] | None = None,
        snapshot: dict[str, object] | None = None,
        effective_profile: dict[str, object] | None = None,
        memory_bundle: dict[str, list[dict[str, object]]] | None = None,
        need_tension_state: dict[str, object] | None = None,
        dynamic_state: dict[str, object] | None = None,
        current_goal_state: dict[str, object] | None = None,
        goal_state_history: list[dict[str, object]] | None = None,
        unresolved_tensions: list[dict[str, object]] | None = None,
        supervision_state: dict[str, object] | None = None,
        skill_affordance_summary: dict[str, object] | None = None,
        stable_ability_snapshot: StableAbilitySnapshot | dict[str, object] | None = None,
        action_affordance_summary: dict[str, object] | None = None,
        environment_affordance_summary: dict[str, object] | None = None,
        equipment_affordance_summary: dict[str, object] | None = None,
        physical_feasibility_summary: dict[str, object] | None = None,
        dossier_projection: dict[str, object] | None = None,
        source_refs: list[str] | None = None,
    ) -> CharacterMindFrame:
        trigger_payload = trigger_event or {}
        normalized_memory = self._snapshot_mapping(
            CharacterContextBuilder.normalize_memory_bundle(memory_bundle)
        )
        graph_projection = self._snapshot_mapping(
            self._graph_projection_provider.project_memory_context(
                actor_id=actor_id,
                memory_bundle=deepcopy(normalized_memory),
            )
        )
        effective_profile_payload = self._snapshot_mapping(effective_profile)
        snapshot_payload = self._snapshot_mapping(snapshot)
        need_payload = self._snapshot_mapping(need_tension_state)
        dynamic_payload = self._snapshot_mapping(dynamic_state)
        goal_payload = self._snapshot_mapping(current_goal_state)
        goal_history_payload = self._snapshot_list(goal_state_history)
        tensions_payload = self._snapshot_list(unresolved_tensions)
        supervision_payload = self._snapshot_mapping(supervision_state)
        dossier_projection_payload = self._snapshot_mapping(dossier_projection)
        mind_turn_id = f"mind_turn:{actor_id}:{producer_ts}"

        workspace = self._working_workspace(
            actor_id=actor_id,
            self_state=self_state_snapshot,
            external_percepts=external_percepts or [],
            action_execution=action_execution_state,
            event_inbox=event_inbox or [],
        )
        frame = CharacterMindFrame(
            actor_id=actor_id,
            mind_turn_id=mind_turn_id,
            producer_ts=producer_ts,
            trigger=CharacterMindFrameTrigger(
                event_id=str(
                    trigger_payload.get("event_id", "")
                    or trigger_payload.get("source_event_id", "")
                    or ""
                ),
                event_type=str(
                    trigger_payload.get("event_type", "")
                    or trigger_payload.get("type", "")
                    or ""
                ),
                source_stage=str(trigger_payload.get("source_stage", "") or ""),
            ),
            enduring_truth=self._enduring_truth_layer(
                actor_id,
                effective_profile_payload,
                dossier_projection_payload,
            ),
            memory_evidence=self._memory_evidence_layer(
                actor_id,
                normalized_memory,
                graph_projection,
                dossier_projection_payload,
            ),
            runtime_state=self._runtime_state_layer(
                actor_id=actor_id,
                snapshot=snapshot_payload,
                need_tension_state=need_payload,
                dynamic_state=dynamic_payload,
                current_goal_state=goal_payload,
                goal_state_history=goal_history_payload,
                unresolved_tensions=tensions_payload,
                supervision_state=supervision_payload,
            ),
            affordances=self._affordance_layer(
                effective_profile=effective_profile_payload,
                skill_affordance_summary=skill_affordance_summary,
                stable_ability_snapshot=stable_ability_snapshot,
                action_affordance_summary=action_affordance_summary,
                environment_affordance_summary=environment_affordance_summary,
                equipment_affordance_summary=equipment_affordance_summary,
                physical_feasibility_summary=physical_feasibility_summary,
                dossier_projection=dossier_projection_payload,
            ),
            cognition_workspace=workspace,
            provenance=MindFrameProvenance(
                source_refs=self._source_refs(
                    actor_id,
                    normalized_memory,
                    goal_payload,
                    dossier_projection_payload,
                    source_refs=source_refs,
                ),
            ),
        )
        if turn_context is not None:
            return frame.bind_to_turn(turn_context)
        return frame

    def _enduring_truth_layer(
        self,
        actor_id: str,
        effective_profile: dict[str, object],
        dossier_projection: dict[str, object],
    ) -> MindFrameLayer:
        cards = self._effective_profile_projector.project(
            actor_id=actor_id,
            effective_profile=effective_profile,
        )
        if dossier_projection:
            cards.extend(
                self._dossier_projection_projector.project_enduring_truth(dossier_projection)
            )
        return MindFrameLayer(cards=cards, summary={"profile_actor_id": actor_id})

    def _memory_evidence_layer(
        self,
        actor_id: str,
        memory: dict[str, list[dict[str, object]]],
        graph_projection: dict[str, object],
        dossier_projection: dict[str, object],
    ) -> MindFrameLayer:
        event_memories = memory.get("event_memories", [])
        observation_memories = memory.get("observation_memories", [])
        knowledge_memories = memory.get("knowledge_memories", [])
        social_memories = memory.get("social_memories", [])
        higher_order_memories = memory.get("higher_order_memories", [])
        cards = self._memory_activation_projector.project(
            memory,
            graph_projection=graph_projection,
        )
        cards.extend(
            self._relationship_context_projector.project(
                actor_id=actor_id,
                social_memories=social_memories,
                graph_projection=graph_projection,
            )
        )
        if dossier_projection:
            cards.extend(
                self._dossier_projection_projector.project_memory_evidence(
                    dossier_projection
                )
            )
        return MindFrameLayer(
            cards=cards,
            summary={
                "event_memory_count": len(event_memories),
                "observation_memory_count": len(observation_memories),
                "knowledge_memory_count": len(knowledge_memories),
                "social_memory_count": len(social_memories),
                "higher_order_memory_count": len(higher_order_memories),
            },
        )

    def _runtime_state_layer(
        self,
        *,
        actor_id: str,
        snapshot: dict[str, object],
        need_tension_state: dict[str, object],
        dynamic_state: dict[str, object],
        current_goal_state: dict[str, object],
        goal_state_history: list[dict[str, object]],
        unresolved_tensions: list[dict[str, object]],
        supervision_state: dict[str, object],
    ) -> MindFrameLayer:
        focus_target = str(
            snapshot.get("current_focus_target", "") or snapshot.get("attention_target", "") or ""
        )
        perception_payload = deepcopy(snapshot)
        perception_payload["focus_target"] = focus_target
        cards = [
            MentalFactorProjectionCard(
                factor_type="perception_context",
                layer="runtime_state",
                summary=focus_target,
                payload=perception_payload,
                source_refs=[],
            ),
        ]
        cards.extend(self._need_pressure_projector.project(need_tension_state))
        cards.extend(self._affective_body_state_projector.project(dynamic_state))
        regulation = project_mental_regulation(actor_id=actor_id, snapshot=snapshot, dynamic_state=dynamic_state)
        cards.append(MentalFactorProjectionCard(
            factor_type="mental_regulation", layer="runtime_state", scope="actor_private",
            summary=regulation.rationality_band or "unknown: regulation policy unregistered",
            payload=regulation.model_dump(mode="json"),
            source_refs=[f"{name}:{revision}" for name, revision in regulation.source_revisions],
            risk_notes=list(regulation.diagnostics),
        ))
        cards.extend(
            self._goal_context_projector.project(
                current_goal_state=current_goal_state,
                goal_state_history=goal_state_history,
            )
        )
        cards.extend(self._unresolved_tension_projector.project(unresolved_tensions))
        cards.extend(self._supervision_projector.project(supervision_state))
        return MindFrameLayer(
            cards=cards,
            summary={
                "focus_target": focus_target,
                "dominant_need": str(need_tension_state.get("dominant_need", "") or ""),
                "primary_goal": str(current_goal_state.get("primary_goal", "") or ""),
                "unresolved_tension_count": len(unresolved_tensions),
            },
        )

    def _affordance_layer(
        self,
        *,
        effective_profile: dict[str, object],
        skill_affordance_summary: dict[str, object],
        stable_ability_snapshot: StableAbilitySnapshot | dict[str, object] | None = None,
        action_affordance_summary: dict[str, object],
        environment_affordance_summary: dict[str, object] | None = None,
        equipment_affordance_summary: dict[str, object] | None = None,
        physical_feasibility_summary: dict[str, object] | None = None,
        dossier_projection: dict[str, object] | None = None,
    ) -> MindFrameLayer:
        summaries = self._affordance_adapter.build_summary(
            effective_profile=effective_profile,
            supplied_skill_affordance_summary=skill_affordance_summary,
            stable_ability_snapshot=stable_ability_snapshot,
            supplied_action_affordance_summary=action_affordance_summary,
            environment_affordance_summary=environment_affordance_summary,
            equipment_affordance_summary=equipment_affordance_summary,
            physical_feasibility_summary=physical_feasibility_summary,
        )
        cards = self._affordance_adapter.project_cards(summaries)
        if dossier_projection:
            cards.extend(
                self._dossier_projection_projector.project_affordances(dossier_projection)
            )
        return MindFrameLayer(
            cards=cards,
            summary={
                "has_skill_affordance": bool(summaries["skill_affordance"]),
                "has_action_affordance": bool(summaries["action_affordance"]),
                "has_environment_affordance": bool(summaries["environment_affordance"]),
                "has_equipment_affordance": bool(summaries["equipment_affordance"]),
                "has_physical_feasibility": bool(summaries["physical_feasibility"]),
            },
        )

    def _source_refs(
        self,
        actor_id: str,
        memory: dict[str, list[dict[str, object]]],
        current_goal_state: dict[str, object],
        dossier_projection: dict[str, object],
        *,
        source_refs: list[str] | None = None,
    ) -> list[str]:
        refs = [f"profile:{actor_id}"]
        refs.extend(self._memory_refs("event_memory", memory.get("event_memories", [])))
        refs.extend(self._memory_refs("knowledge_memory", memory.get("knowledge_memories", [])))
        refs.extend(
            self._memory_refs("higher_order_memory", memory.get("higher_order_memories", []))
        )
        refs.extend(
            [
                f"social_memory:{actor_id}:{entry.get('entity_id', '')}"
                for entry in memory.get("social_memories", [])
                if str(entry.get("entity_id", "") or "")
            ]
        )
        if current_goal_state:
            refs.append(f"goal_state:{actor_id}:current")
        raw_dossier_refs = dossier_projection.get("source_refs", [])
        if isinstance(raw_dossier_refs, list):
            refs.extend(str(ref) for ref in raw_dossier_refs if str(ref))
        refs.extend(str(ref) for ref in (source_refs or []) if str(ref))
        return refs

    def _working_workspace(
        self,
        *,
        actor_id: str,
        self_state: SelfStateSnapshot | None,
        external_percepts: list[ExternalPerceptSnapshot],
        action_execution: ActionExecutionState | None,
        event_inbox: list[dict[str, object]],
    ) -> CognitionWorkspace:
        self_payload: dict[str, object] = {}
        uncertainty: list[dict[str, object]] = []
        if self_state is not None:
            if self_state.actor_id != actor_id or self_state.visibility != "actor_private":
                raise ValueError("self state projection is outside actor-private scope")
            self_payload = self_state.model_dump(mode="json")
            if self_state.uncertainty != "known" or self_state.freshness in {"stale", "expired", "unknown"}:
                uncertainty.append({"source": self_state.source, "state": self_state.uncertainty,
                                    "freshness": self_state.freshness, "revision": self_state.revision})
        if action_execution is not None:
            if action_execution.actor_id != actor_id or action_execution.visibility != "actor_private":
                raise ValueError("action execution projection is outside actor-private scope")
            self_payload["action_execution"] = action_execution.model_dump(mode="json")
        external_payloads: list[dict[str, object]] = []
        for percept in external_percepts:
            if percept.actor_id != actor_id or percept.visibility != "actor_private":
                raise ValueError("external percept projection is outside actor-private scope")
            payload = percept.model_dump(mode="json")
            external_payloads.append(payload)
            if percept.uncertainty != "known" or percept.freshness in {"stale", "expired", "unknown"}:
                uncertainty.append({"subject_ref": percept.subject_ref, "source": percept.source,
                                    "state": percept.uncertainty, "freshness": percept.freshness,
                                    "revision": percept.revision, "conflict_refs": list(percept.conflict_refs)})
        normalized_events = []
        for event in event_inbox:
            if event.get("visibility", "actor_private") != "actor_private":
                continue
            normalized_events.append(deepcopy(event))
        return CognitionWorkspace(
            self_state=self_payload,
            external_state=external_payloads,
            event_inbox=normalized_events,
            uncertainty=uncertainty,
        )

    @staticmethod
    def _snapshot_mapping(value: object) -> dict[str, object]:
        if not isinstance(value, dict):
            return {}
        return deepcopy(value)

    @staticmethod
    def _snapshot_list(value: object) -> list[dict[str, object]]:
        if not isinstance(value, list):
            return []
        return [deepcopy(entry) for entry in value if isinstance(entry, dict)]

    @staticmethod
    def _memory_refs(prefix: str, entries: list[dict[str, object]]) -> list[str]:
        refs: list[str] = []
        for entry in entries:
            value = str(
                entry.get("memory_id", "")
                or entry.get("source_event_id", "")
                or entry.get("proposition_key", "")
                or ""
            )
            if value:
                refs.append(f"{prefix}:{value}")
        return refs
