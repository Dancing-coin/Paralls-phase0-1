from __future__ import annotations

from app.character_agent.models.cognition_update import CharacterCognitionUpdate
from app.character_agent.models.cognition_delta import (
    CharacterBeliefDelta,
    CharacterDynamicStateDelta,
    CharacterHigherOrderDelta,
    CharacterSocialDelta,
)
from app.character_agent.models.goal_runtime import CharacterGoalHint


class CharacterCognitionEngine:
    def build_reasoning_output(
        self,
        *,
        actor_id: str,
        snapshot: dict[str, object],
        event: dict[str, object],
        memory: dict[str, object],
    ) -> dict[str, object]:
        if not isinstance(snapshot.get("body_state_hints", []), list):
            body_state_hints: list[object] = []
        else:
            body_state_hints = list(snapshot.get("body_state_hints", []))
        summary = str(
            event.get("perceived_summary", "")
            or event.get("presentation_hint", "")
            or snapshot.get("perceived_summary", "")
            or "state_change"
        )
        interpretation_type = "state_change"
        if str(event.get("body_state_class", "") or ""):
            interpretation_type = "body_state"
        elif body_state_hints:
            interpretation_type = "body_state"
        elif str(event.get("percept_channel", "") or "") == "auditory":
            interpretation_type = "social_signal"
        elif "visual_fact" in summary:
            interpretation_type = "opportunity"

        attention_targets = snapshot.get("attention_targets", [])
        if not isinstance(attention_targets, list):
            attention_targets = []
        attention_target = str(
            attention_targets[0]
            if attention_targets
            else event.get("target_actor_id", "") or event.get("target_object_id", "") or event.get("target_environment_id", "") or ""
        )
        social_memories = memory.get("social_memories", [])
        if not isinstance(social_memories, list):
            social_memories = []
        relational_memories = memory.get("relational_memories", [])
        if not isinstance(relational_memories, list):
            relational_memories = []
        guarded_attention_target = self._is_guarded_attention_target(
            attention_target,
            relational_memories,
            social_memories,
        )
        salience_score = float(event.get("clarity_score", snapshot.get("clarity_score", 0.5)) or 0.5)
        salience_boost = event.get("salience_boost")
        if isinstance(salience_boost, (int, float)):
            salience_score = max(salience_score, min(1.0, max(0.0, float(salience_boost))))
        opportunity_level = "medium" if interpretation_type in {"opportunity", "social_signal"} else "low"
        recent_world_changes = snapshot.get("recent_world_changes", [])
        if not isinstance(recent_world_changes, list):
            recent_world_changes = []
        last_siming_catalyst = str(snapshot.get("last_siming_catalyst", "") or "")
        vigilance_level = str(snapshot.get("vigilance_level", "") or "")
        if recent_world_changes or last_siming_catalyst != "" or vigilance_level == "elevated" or salience_score >= 0.75:
            opportunity_level = "medium"
        risk_level = "medium" if interpretation_type == "body_state" else "low"
        active_anomalies = snapshot.get("active_anomalies", [])
        if not isinstance(active_anomalies, list):
            active_anomalies = []
        recent_constraint_results = snapshot.get("recent_constraint_results", [])
        if not isinstance(recent_constraint_results, list):
            recent_constraint_results = []
        pressure_hint = str(event.get("pressure_hint", "") or "")
        if active_anomalies or recent_constraint_results or guarded_attention_target or pressure_hint != "":
            risk_level = "medium"
        ambiguity_level = "medium" if float(event.get("certainty_score", snapshot.get("certainty_score", 1.0)) or 1.0) < 0.7 else "low"
        distraction_level = str(snapshot.get("distraction_level", "") or "")
        if distraction_level == "elevated" or pressure_hint != "":
            ambiguity_level = "medium"

        update = self.build_update(
            actor_id=actor_id,
            summary=summary,
            interpretation_type=interpretation_type,
            salience_score=salience_score,
            ambiguity_level=ambiguity_level,
            risk_level=risk_level,
            opportunity_level=opportunity_level,
            attention_target=attention_target,
            snapshot=snapshot,
            event=event,
            memory=memory,
        )
        return {
            "interpreted_summary": summary,
            "interpretation_type": interpretation_type,
            "salience_score": salience_score,
            "ambiguity_level": ambiguity_level,
            "risk_level": risk_level,
            "opportunity_level": opportunity_level,
            "attention_target": attention_target or None,
            "inner_prompt_candidate": update.reasoning_trace_summary or f"{actor_id}:{summary}",
            "belief_deltas": [item.model_dump() for item in update.belief_deltas],
            "social_deltas": [item.model_dump() for item in update.social_deltas],
            "higher_order_deltas": [item.model_dump() for item in update.higher_order_deltas],
            "dynamic_state_delta": update.dynamic_state_delta.as_mapping(),
            "goal_hints": [item.model_dump() for item in update.goal_hints],
            "reasoning_trace_summary": update.reasoning_trace_summary or f"{actor_id}:{summary}",
        }

    def build_update(
        self,
        *,
        actor_id: str,
        summary: str,
        interpretation_type: str,
        salience_score: float,
        ambiguity_level: str,
        risk_level: str,
        opportunity_level: str,
        attention_target: str,
        snapshot: dict[str, object],
        event: dict[str, object],
        memory: dict[str, object],
    ) -> CharacterCognitionUpdate:
        relational_memories = memory.get("relational_memories", [])
        if not isinstance(relational_memories, list):
            relational_memories = []
        social_memories = memory.get("social_memories", [])
        if not isinstance(social_memories, list):
            social_memories = []
        higher_order_memories = memory.get("higher_order_memories", [])
        if not isinstance(higher_order_memories, list):
            higher_order_memories = []
        active_anomalies = snapshot.get("active_anomalies", [])
        if not isinstance(active_anomalies, list):
            active_anomalies = []
        recent_constraint_results = snapshot.get("recent_constraint_results", [])
        if not isinstance(recent_constraint_results, list):
            recent_constraint_results = []
        pressure_hint = str(event.get("pressure_hint", "") or "")
        body_state_class = str(event.get("body_state_class", "") or "body_state")
        reason_scope = str(event.get("reason_scope", "") or "")
        target_is_meta_suspicious = any(
            isinstance(entry, dict)
            and str(entry.get("subject_actor_id", "") or "") == attention_target
            for entry in higher_order_memories
        )
        target_knowledge_confidence = self._target_knowledge_confidence(attention_target, memory)
        guarded_attention_target = self._is_guarded_attention_target(
            attention_target,
            relational_memories,
            social_memories,
        )

        belief_deltas: list[CharacterBeliefDelta] = []
        social_deltas: list[CharacterSocialDelta] = []
        higher_order_deltas: list[CharacterHigherOrderDelta] = []
        dynamic_state_delta: dict[str, float] = {}
        goal_hints: list[CharacterGoalHint] = []

        if interpretation_type == "social_signal" and attention_target != "":
            confidence = max(0.55, min(0.85, salience_score))
            belief_deltas.append(
                CharacterBeliefDelta(
                    proposition_key=f"{attention_target}:is_probing",
                    proposition=f"{attention_target} may be probing",
                    state="suspected",
                    confidence=confidence,
                )
            )
            social_deltas.append(
                CharacterSocialDelta(
                    entity_id=attention_target,
                    trust_baseline=0.3 if guarded_attention_target else 0.45,
                    suspicion_baseline=0.82 if guarded_attention_target else 0.6,
                    intimacy=0.0,
                    dependency=0.0,
                    unresolved_tension=0.45 if guarded_attention_target else 0.2,
                    shared_secret_refs=[],
                )
            )
            higher_order_deltas.append(
                CharacterHigherOrderDelta(
                    subject_actor_id=attention_target,
                    proposition_key="social_probe:knowledge_asymmetry",
                    meta_belief=f"{attention_target} suspects {actor_id} knows more",
                    confidence=confidence,
                )
            )
            dynamic_state_delta["social_pressure"] = 0.7 if guarded_attention_target else 0.55
            dynamic_state_delta["masking_pressure"] = 0.55 if guarded_attention_target or ambiguity_level == "medium" else 0.35
            if target_is_meta_suspicious:
                dynamic_state_delta["social_pressure"] = max(dynamic_state_delta["social_pressure"], 0.65)
                dynamic_state_delta["masking_pressure"] = max(dynamic_state_delta["masking_pressure"], 0.6)
            if guarded_attention_target or target_is_meta_suspicious:
                evidence_tags: list[str] = []
                if guarded_attention_target:
                    evidence_tags.append("guarded_attention")
                if target_is_meta_suspicious:
                    evidence_tags.append("target_meta_suspicion")
                goal_hints.append(
                    CharacterGoalHint(
                        goal="protect_secret",
                        source="social_signal",
                        strength=0.85,
                        evidence_tags=evidence_tags,
                    )
                )
            clarify_strength = max(0.55, min(0.95, 0.45 + target_knowledge_confidence))
            goal_hints.append(
                CharacterGoalHint(
                    goal="clarify_intent",
                    source="social_signal",
                    strength=clarify_strength,
                    evidence_tags=["social_probe", "knowledge_confidence"],
                )
            )

        if (
            str(event.get("percept_channel", "") or "") != "siming"
            and interpretation_type in {"opportunity", "state_change"}
            and attention_target != ""
            and (
                attention_target.startswith("env_") or attention_target.startswith("obj_") or bool(snapshot.get("recent_world_changes"))
            )
        ):
            confidence = max(0.65, min(0.95, salience_score))
            belief_deltas.append(
                CharacterBeliefDelta(
                    proposition_key=f"{attention_target}:state_change",
                    proposition=f"{attention_target} appears to have changed state",
                    state="believed",
                    confidence=confidence,
                )
            )
            dynamic_state_delta["vigilance_level"] = max(dynamic_state_delta.get("vigilance_level", 0.0), 0.6)
            goal_hints.append(
                CharacterGoalHint(
                    goal="stabilize_situation",
                    source="world_change",
                    strength=0.7,
                    evidence_tags=["world_change_detected"],
                )
            )

        if interpretation_type == "body_state":
            confidence = max(0.7, min(0.95, salience_score))
            belief_deltas.append(
                CharacterBeliefDelta(
                    proposition_key=f"self:{body_state_class}",
                    proposition=f"self is in {body_state_class}",
                    state="believed",
                    confidence=confidence,
                )
            )
            dynamic_state_delta["stress_load"] = max(dynamic_state_delta.get("stress_load", 0.0), 0.65)
            dynamic_state_delta["vigilance_level"] = max(dynamic_state_delta.get("vigilance_level", 0.0), 0.55)
            goal_hints.append(
                CharacterGoalHint(
                    goal="protect_self",
                    source="body_state",
                    strength=0.82,
                    evidence_tags=["body_alarm"],
                )
            )

        if active_anomalies or recent_constraint_results or pressure_hint != "":
            dynamic_state_delta["stress_load"] = 0.65 if recent_constraint_results else 0.55
            goal_hints.append(
                CharacterGoalHint(
                    goal="protect_self",
                    source="pressure",
                    strength=0.72,
                    evidence_tags=["constraint_pressure" if recent_constraint_results else "anomaly_pressure"],
                )
            )

        vigilance_level = str(snapshot.get("vigilance_level", "") or "")
        distraction_level = str(snapshot.get("distraction_level", "") or "")
        if vigilance_level == "elevated":
            dynamic_state_delta["vigilance_level"] = 0.8
        if distraction_level == "elevated":
            dynamic_state_delta["distraction_level"] = 0.75
        if pressure_hint != "":
            dynamic_state_delta["distraction_level"] = max(dynamic_state_delta.get("distraction_level", 0.0), 0.75)
            goal_hints.append(
                CharacterGoalHint(
                    goal="preserve_optionality",
                    source="siming_pressure",
                    strength=0.76,
                    evidence_tags=["siming_pressure"],
                )
            )

        reasoning_trace = ":".join(part for part in (actor_id, reason_scope, pressure_hint, summary) if part)
        deduped_goal_hints: list[CharacterGoalHint] = []
        seen_goal_hints: set[tuple[str, str]] = set()
        for hint in goal_hints:
            key = (hint.goal, hint.source)
            if key in seen_goal_hints or hint.goal == "":
                continue
            seen_goal_hints.add(key)
            deduped_goal_hints.append(hint)

        return CharacterCognitionUpdate(
            interpreted_situation=summary,
            belief_deltas=belief_deltas,
            social_deltas=social_deltas,
            higher_order_deltas=higher_order_deltas,
            dynamic_state_delta=CharacterDynamicStateDelta(**dynamic_state_delta),
            goal_hints=deduped_goal_hints,
            reasoning_trace_summary=reasoning_trace or f"{actor_id}:{summary}",
        )

    def _target_knowledge_confidence(self, attention_target: str, memory: dict[str, object]) -> float:
        if attention_target == "":
            return 0.25
        knowledge_memories = memory.get("knowledge_memories", [])
        if not isinstance(knowledge_memories, list):
            return 0.25
        for entry in knowledge_memories:
            if not isinstance(entry, dict):
                continue
            proposition_key = str(entry.get("proposition_key", "") or "")
            if proposition_key.startswith(f"{attention_target}:"):
                value = entry.get("confidence", 0.25)
                if isinstance(value, (int, float)):
                    return float(value)
        return 0.25

    def _is_guarded_relational_target(self, attention_target: str, relational_memories: list[object]) -> bool:
        if attention_target == "":
            return False
        for entry in relational_memories:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("entity_id", "") or "") != attention_target:
                continue
            if str(entry.get("belief_type", "") or "") != "trust_level":
                continue
            if str(entry.get("value", "") or "") == "guarded":
                return True
        return False

    def _is_guarded_attention_target(
        self,
        attention_target: str,
        relational_memories: list[object],
        social_memories: list[object],
    ) -> bool:
        if self._is_guarded_relational_target(attention_target, relational_memories):
            return True
        if attention_target == "":
            return False
        for entry in social_memories:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("entity_id", "") or "") != attention_target:
                continue
            suspicion = entry.get("suspicion_baseline")
            if isinstance(suspicion, (int, float)) and float(suspicion) >= 0.75:
                return True
        return False
