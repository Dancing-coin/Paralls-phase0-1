from __future__ import annotations

from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.models.observatory import ActorDramaticEvent, ActorDramaticState


class CharacterAgentDebugProjection:
    def project_snapshot(
        self,
        *,
        actor_id: str,
        producer_ts: int,
        snapshot: CharacterPrivateWorldSnapshot,
        memory_bundle: dict[str, list[dict[str, object]]],
        interpretation_summary: str,
        decision_summary: str,
        execution_summary: str,
        latest_outcome_summary: str,
        latest_siming_summary: str,
    ) -> ActorDramaticState:
        focus_target = snapshot.current_attention_targets[0] if snapshot.current_attention_targets else ""
        current_intent = self._summary_or_empty(decision_summary).split(" and ", 1)[0]
        perception_parts = snapshot.visible_entities + snapshot.audible_entities + snapshot.unresolved_signals
        memory_parts = [
            *[self._entry_summary(entry) for entry in memory_bundle.get("working_memory", [])],
            *[self._entry_summary(entry) for entry in memory_bundle.get("episodic_memories", [])],
        ]
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

    def _entry_summary(self, entry: dict[str, object]) -> str:
        summary = str(entry.get("summary", "") or "")
        return summary

    def _summary_or_empty(self, value: str) -> str:
        return value.strip()
