from __future__ import annotations

from app.character_agent.models.dynamic_state import CharacterDynamicState
from app.character_agent.models.event_memory import CharacterEventMemoryRecord
from app.character_agent.models.goal_runtime import CharacterGoalStateRecord
from app.character_agent.models.higher_order_memory import CharacterHigherOrderMemoryRecord
from app.character_agent.models.knowledge_memory import CharacterKnowledgeMemoryRecord
from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle
from app.character_agent.models.observation_memory import CharacterObservationMemoryRecord
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.character_agent.models.social_memory import CharacterSocialMemoryRecord
from app.models.observatory import ActorDramaticEvent, ActorDramaticState


class CharacterAgentDebugProjection:
    def project_snapshot(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        snapshot: CharacterPrivateWorldSnapshot,
        memory_bundle: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
        interpretation_summary: str,
        decision_summary: str,
        execution_summary: str,
        latest_outcome_summary: str,
        latest_siming_summary: str,
        cadence_summary: str = "",
        continuity_summary: str = "",
        scheduling_summary: str = "",
        dynamic_state_summary: str = "",
        dynamic_state: CharacterDynamicState | dict[str, object] | None = None,
        goal_state: CharacterGoalStateRecord | dict[str, object] | None = None,
    ) -> ActorDramaticState:
        focus_target = snapshot.current_attention_targets[0] if snapshot.current_attention_targets else ""
        current_intent = self._summary_or_empty(decision_summary).split(" and ", 1)[0]
        dynamic_state_record = self._dynamic_state_record(dynamic_state)
        typed_memory_bundle = self._memory_record_bundle(memory_bundle)
        perception_parts = snapshot.visible_entities + snapshot.audible_entities + snapshot.unresolved_signals
        memory_parts = [
            *[self._event_memory_summary(entry) for entry in typed_memory_bundle.event_memories],
            *[self._observation_memory_summary(entry) for entry in typed_memory_bundle.observation_memories],
            *[self._knowledge_memory_summary(entry) for entry in typed_memory_bundle.knowledge_memories],
            *[self._social_memory_summary(entry) for entry in typed_memory_bundle.social_memories],
            *[self._higher_order_memory_summary(entry) for entry in typed_memory_bundle.higher_order_memories],
        ]
        if dynamic_state_summary == "" and dynamic_state_record is not None:
            dynamic_state_summary = self._dynamic_state_summary(dynamic_state_record)
        if dynamic_state_summary != "":
            memory_parts.append(f"dynamic:{dynamic_state_summary}")
        participants = [actor_id]
        if focus_target != "":
            participants.append(focus_target)
        return ActorDramaticState(
            actor_id=actor_id,
            producer_ts=producer_ts,
            causation_id=f"character_debug_snapshot:{actor_id}:{producer_ts}",
            correlation_id=f"character_debug_snapshot:{actor_id}:{producer_ts}",
            participants=participants,
            current_intent=current_intent,
            focus_target=focus_target,
            state_label=snapshot.vigilance_level or "baseline",
            why_now_summary=interpretation_summary or decision_summary,
            perception_summary=" | ".join(filter(None, perception_parts)),
            memory_summary=" | ".join(filter(None, memory_parts)),
            interpretation_summary=interpretation_summary,
            decision_summary=decision_summary,
            execution_summary=execution_summary,
            latest_outcome_summary=latest_outcome_summary,
            latest_siming_summary=latest_siming_summary,
            cadence_summary=cadence_summary,
            continuity_summary=continuity_summary,
            scheduling_summary=scheduling_summary,
            dynamic_state=dynamic_state_record,
            goal_state=self._goal_state_record(goal_state),
        )

    def project_stage_event(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        stage: str,
        summary: str,
        focus_target: str,
        intent_label: str,
        participants: list[str],
        detail: dict[str, object] | None = None,
    ) -> ActorDramaticEvent:
        return ActorDramaticEvent(
            actor_id=actor_id,
            producer_ts=producer_ts,
            causation_id=f"{actor_id}:{stage}:{producer_ts}",
            correlation_id=f"{actor_id}:{stage}:{producer_ts}",
            participants=participants,
            stage=stage,
            summary=summary,
            focus_target=focus_target,
            intent_label=intent_label,
            detail=detail or {},
        )

    def _event_memory_summary(self, entry: CharacterEventMemoryRecord) -> str:
        return entry.summary

    def _observation_memory_summary(self, entry: CharacterObservationMemoryRecord) -> str:
        return entry.observation_summary

    def _knowledge_memory_summary(self, entry: CharacterKnowledgeMemoryRecord) -> str:
        return entry.proposition

    def _social_memory_summary(self, entry: CharacterSocialMemoryRecord) -> str:
        return entry.entity_id

    def _higher_order_memory_summary(self, entry: CharacterHigherOrderMemoryRecord) -> str:
        return entry.meta_belief

    def _summary_or_empty(self, value: str) -> str:
        return value.strip()

    def _dynamic_state_record(
        self,
        value: CharacterDynamicState | dict[str, object] | None,
    ) -> CharacterDynamicState | None:
        if isinstance(value, CharacterDynamicState):
            return value
        if isinstance(value, dict) and value:
            return CharacterDynamicState(**value)
        return None

    def _goal_state_record(
        self,
        value: CharacterGoalStateRecord | dict[str, object] | None,
    ) -> CharacterGoalStateRecord | None:
        if isinstance(value, CharacterGoalStateRecord):
            return value
        if isinstance(value, dict) and value:
            return CharacterGoalStateRecord(**value)
        return None

    def _dynamic_state_summary(self, value: CharacterDynamicState) -> str:
        ordered_pairs = [
            ("vigilance_level", value.vigilance_level),
            ("distraction_level", value.distraction_level),
            ("stress_load", value.stress_load),
            ("social_pressure", value.social_pressure),
            ("masking_pressure", value.masking_pressure),
        ]
        parts = [f"{key}={item}" for key, item in ordered_pairs if item is not None]
        return "|".join(parts)

    def _memory_bundle_mapping(
        self,
        value: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
    ) -> dict[str, list[dict[str, object]]]:
        if isinstance(value, CharacterMemoryRecordBundle):
            return {
                "working_memory": [],
                "event_memories": [item.model_dump() for item in value.event_memories],
                "observation_memories": [item.model_dump() for item in value.observation_memories],
                "episodic_memories": [item.model_dump() for item in value.event_memories],
                "knowledge_memories": [item.model_dump() for item in value.knowledge_memories],
                "social_memories": [item.model_dump() for item in value.social_memories],
                "higher_order_memories": [item.model_dump() for item in value.higher_order_memories],
            }
        return dict(value)

    def _memory_record_bundle(
        self,
        value: dict[str, list[dict[str, object]]] | CharacterMemoryRecordBundle,
    ) -> CharacterMemoryRecordBundle:
        if isinstance(value, CharacterMemoryRecordBundle):
            return value
        normalized = self._memory_bundle_mapping(value)
        return CharacterMemoryRecordBundle(
            event_memories=[
                CharacterEventMemoryRecord(**entry)
                for entry in normalized.get("event_memories", normalized.get("episodic_memories", []))
            ],
            observation_memories=[
                CharacterObservationMemoryRecord(**entry)
                for entry in normalized.get("observation_memories", [])
            ],
            knowledge_memories=[
                CharacterKnowledgeMemoryRecord(**entry)
                for entry in normalized.get("knowledge_memories", [])
            ],
            social_memories=[
                CharacterSocialMemoryRecord(**entry)
                for entry in normalized.get("social_memories", [])
            ],
            higher_order_memories=[
                CharacterHigherOrderMemoryRecord(**entry)
                for entry in normalized.get("higher_order_memories", [])
            ],
        )
