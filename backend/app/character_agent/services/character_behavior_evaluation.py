from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

from app.character_agent.models.behavior_evaluation import BehaviorEvaluation
from app.character_agent.models.turn_context import CharacterTurnContext


class CharacterBehaviorEvaluationService:
    """Build deterministic, evidence-backed evaluation for one character turn."""

    _CHAIN_TYPES = (
        "l2_reasoning_request",
        "character_interpretation_event",
        "goal_state_event",
        "character_agent_execution_request",
    )

    def evaluate(
        self,
        *,
        settlement_event: dict[str, object],
        timeline: list[dict[str, object]],
        turn: CharacterTurnContext | None = None,
        actor_id: str | None = None,
    ) -> BehaviorEvaluation:
        """Evaluate a canonical turn, retaining a legacy actor/timeline reader."""
        settlement_payload = self._payload(settlement_event.get("payload", {}))
        resolved_actor_id = turn.actor_id if turn is not None else str(actor_id or "")
        if not resolved_actor_id:
            resolved_actor_id = str(settlement_payload.get("actor_id", "") or "unknown")
        chain = self._latest_chain(
            timeline,
            settlement_event.get("producer_ts", 0),
            correlation_id=turn.correlation_id if turn is not None else str(
                settlement_payload.get("correlation_id", "") or ""
            ),
        )
        stages = self._stage_payloads(turn, chain)
        context = self._payload(stages.get("context", {}))
        recall = self._payload(context.get("memory_recall", {}))
        interpretation_payload = self._payload(stages.get("interpretation", {}))
        goal_payload = self._payload(stages.get("goal", {}))
        execution_payload = self._payload(stages.get("execution", {}))
        proposal = self._payload(execution_payload.get("composite_action_proposal", {}))
        failed_intent = str(
            execution_payload.get("selected_intent", "")
            or proposal.get("source_intent", "")
            or ""
        )
        metadata = self._payload(settlement_payload.get("action_settlement_result", {}))
        raw_failure_domains = metadata.get(
            "failure_domains", settlement_payload.get("failure_domains", [])
        )
        failure_domains = (
            [str(value) for value in raw_failure_domains if str(value)]
            if isinstance(raw_failure_domains, list)
            else []
        )
        outcome_band = str(metadata.get("outcome_band", "") or "")
        settlement_status = str(
            settlement_payload.get("settlement_status", "")
            or settlement_payload.get("resolution_status", "")
            or ""
        )
        settlement_event_id = str(settlement_event.get("event_id", "") or "")
        unknown_reasons: dict[str, str] = {}
        turn_id = turn.turn_id if turn is not None else str(settlement_payload.get("turn_id", "") or "")
        correlation_id = turn.correlation_id if turn is not None else str(settlement_payload.get("correlation_id", "") or "")
        scoped_timeline = self._scoped_timeline(timeline, turn_id, correlation_id)
        source_refs = self._source_refs(turn, chain, settlement_event)
        source_refs.extend(
            str(event.get("event_id", ""))
            for event in scoped_timeline
            if str(event.get("event_id", ""))
        )
        source_refs = list(dict.fromkeys(source_refs))
        scores = {
            "comprehension": self._comprehension_score(interpretation_payload, settlement_payload, unknown_reasons),
            "goal_progress": self._goal_progress_score(goal_payload, settlement_status, unknown_reasons),
            "role_consistency": self._role_consistency_score(scoped_timeline, unknown_reasons),
            "execution_quality": self._execution_quality_score(settlement_status, outcome_band, failure_domains, unknown_reasons),
            "social_consequence": self._social_consequence_score(settlement_payload, scoped_timeline, unknown_reasons),
            "recovery_quality": self._recovery_quality_score(turn, scoped_timeline, unknown_reasons),
        }
        unknown_dimensions = [name for name, score in scores.items() if score is None]
        known_scores = [score for score in scores.values() if score is not None]
        compatibility_score = (
            round(sum(known_scores) / len(known_scores), 4)
            if known_scores
            else self._score(outcome_band, settlement_status, failure_domains)
        )
        confidence = self._confidence(
            source_refs, len(known_scores), len(unknown_dimensions), failure_domains, settlement_payload
        )
        candidate = self._candidate_policy(
            actor_id=resolved_actor_id,
            turn_id=turn.turn_id if turn is not None else str(settlement_payload.get("turn_id", "") or ""),
            score=compatibility_score,
            confidence=confidence,
            unknown_dimensions=unknown_dimensions,
            failure_domains=failure_domains,
            recall=recall,
            settlement_payload=settlement_payload,
            failed_intent=failed_intent,
            source_refs=source_refs,
            settlement_event_id=settlement_event_id,
            settlement_status=settlement_status,
        )
        return BehaviorEvaluation(
            actor_id=resolved_actor_id,
            turn_id=turn.turn_id if turn is not None else str(settlement_payload.get("turn_id", "") or ""),
            behavior_score=compatibility_score,
            outcome_band=outcome_band,
            failure_domains=failure_domains,
            comprehension_score=scores["comprehension"],
            goal_progress_score=scores["goal_progress"],
            role_consistency_score=scores["role_consistency"],
            execution_quality_score=scores["execution_quality"],
            social_consequence_score=scores["social_consequence"],
            recovery_quality_score=scores["recovery_quality"],
            confidence=confidence,
            evidence_refs=source_refs,
            unknown_dimensions=unknown_dimensions,
            unknown_reasons=unknown_reasons,
            candidate_policy=candidate,
            context_hash=str(recall.get("context_hash", "") or ""),
            selected_memory_refs=list(recall.get("selected_memory_refs", [])) if isinstance(recall.get("selected_memory_refs", []), list) else [],
            memory_budget={
                "token_budget": int(recall.get("token_budget", 0) or 0),
                "estimated_tokens": int(recall.get("estimated_tokens", 0) or 0),
                "truncated": bool(recall.get("truncated", False)),
            },
            interpretation={
                "event_id": str(stages.get("interpretation_event_id", "") or ""),
                "summary": str(interpretation_payload.get("interpreted_summary", "") or ""),
                "attention_target": str(interpretation_payload.get("attention_target", "") or ""),
            },
            selected_intent=str(goal_payload.get("dominant_goal_id", "") or execution_payload.get("selected_intent", "") or ""),
            failed_intent=failed_intent,
            execution_event_id=str(stages.get("execution_event_id", "") or ""),
            settlement_event_id=settlement_event_id,
            source_refs=source_refs,
        )

    @staticmethod
    def _payload(value: object) -> dict[str, object]:
        return deepcopy(value) if isinstance(value, dict) else {}

    def _stage_payloads(self, turn: CharacterTurnContext | None, chain: dict[str, dict[str, object]]) -> dict[str, object]:
        if turn is None:
            def legacy(name: str) -> dict[str, object]:
                return self._payload(self._payload(chain.get(name, {})).get("payload", {}))
            return {
                "context": self._payload(self._payload(chain.get("l2_reasoning_request", {})).get("payload", {})).get("context", {}),
                "interpretation": legacy("character_interpretation_event"),
                "interpretation_event_id": str(chain.get("character_interpretation_event", {}).get("event_id", "")),
                "goal": legacy("goal_state_event"),
                "execution": legacy("character_agent_execution_request"),
                "execution_event_id": str(chain.get("character_agent_execution_request", {}).get("event_id", "")),
            }
        events = turn.stage_events
        def stage_payload(name: str) -> dict[str, object]:
            event = events.get(name)
            return self._payload(event.payload if event is not None else {})
        return {
            "context": stage_payload("context"),
            "interpretation": stage_payload("interpretation"),
            "interpretation_event_id": turn.stage_refs.get("interpretation", ""),
            "goal": stage_payload("goal"),
            "execution": stage_payload("execution"),
            "execution_event_id": turn.stage_refs.get("execution", ""),
        }

    def _latest_chain(self, timeline: list[dict[str, object]], producer_ts: object, *, correlation_id: str = "") -> dict[str, dict[str, object]]:
        timestamp = int(producer_ts or 0)
        result: dict[str, dict[str, object]] = {}
        for event in timeline:
            if not isinstance(event, dict) or int(event.get("producer_ts", 0) or 0) > timestamp:
                continue
            event_type = str(event.get("event_type", "") or "")
            if event_type not in self._CHAIN_TYPES:
                continue
            payload = self._payload(event.get("payload", {}))
            event_correlation = str(payload.get("correlation_id", "") or payload.get("causation_id", "") or "")
            if correlation_id and event_correlation and event_correlation != correlation_id:
                continue
            result[event_type] = deepcopy(event)
        return result

    @staticmethod
    def _source_refs(turn: CharacterTurnContext | None, chain: dict[str, dict[str, object]], settlement_event: dict[str, object]) -> list[str]:
        refs = [str(ref) for ref in turn.stage_refs.values() if str(ref)] if turn is not None else [str(event.get("event_id", "")) for event in chain.values() if str(event.get("event_id", ""))]
        settlement_ref = str(settlement_event.get("event_id", "") or "")
        if settlement_ref:
            refs.append(settlement_ref)
        return list(dict.fromkeys(refs))

    @staticmethod
    def _scoped_timeline(
        timeline: list[dict[str, object]], turn_id: str, correlation_id: str
    ) -> list[dict[str, object]]:
        if not turn_id and not correlation_id:
            return []
        scoped: list[dict[str, object]] = []
        for event in timeline:
            if not isinstance(event, dict):
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            event_turn = str(payload.get("turn_id", "") or "")
            event_correlation = str(
                payload.get("correlation_id", "")
                or payload.get("causation_id", "")
                or ""
            )
            if (turn_id and event_turn == turn_id) or (
                correlation_id and event_correlation == correlation_id
            ):
                scoped.append(event)
        return scoped

    @staticmethod
    def _comprehension_score(interpretation: dict[str, object], settlement: dict[str, object], unknown: dict[str, str]) -> float | None:
        if not interpretation:
            unknown["comprehension"] = "interpretation_evidence_absent"
            return None
        action_metadata = settlement.get("action_settlement_result")
        substantive = any(
            str(settlement.get(key, "") or "")
            for key in ("result_type", "constraint_summary", "change_summary", "stable_state_summary")
        ) or (isinstance(action_metadata, dict) and bool(action_metadata))
        if not substantive:
            unknown["comprehension"] = "authority_outcome_evidence_absent"
            return None
        status = str(settlement.get("settlement_status", "") or settlement.get("resolution_status", ""))
        return 1.0 if status in {"accepted", "applied", "observed"} else 0.2

    @staticmethod
    def _goal_progress_score(goal: dict[str, object], status: str, unknown: dict[str, str]) -> float | None:
        if not goal:
            unknown["goal_progress"] = "active_goal_transition_absent"
            return None
        if any(
            key in goal and goal.get(key) not in (None, "", [], {}, ())
            for key in ("transition", "progress", "goal_status", "status")
        ):
            return 1.0 if status in {"accepted", "applied", "observed"} else 0.2
        unknown["goal_progress"] = "active_goal_transition_unproven"
        return None

    @staticmethod
    def _role_consistency_score(timeline: list[dict[str, object]], unknown: dict[str, str]) -> float | None:
        for event in timeline:
            payload = event.get("payload") if isinstance(event, dict) else None
            if not isinstance(payload, dict):
                continue
            role_value = payload.get("role_consistency")
            if role_value not in (None, "") and any(key in payload for key in ("profile_constraints", "supervision_constraints", "role_consistency")):
                try:
                    return max(0.0, min(1.0, float(role_value)))
                except (TypeError, ValueError):
                    break
        unknown["role_consistency"] = "profile_or_supervision_evidence_absent"
        return None

    @staticmethod
    def _execution_quality_score(status: str, outcome_band: str, failure_domains: list[str], unknown: dict[str, str]) -> float | None:
        if not status and not outcome_band:
            unknown["execution_quality"] = "settlement_evidence_absent"
            return None
        if status in {"accepted", "applied", "observed"} or outcome_band == "clean_success":
            return 0.85 if failure_domains else 1.0
        if outcome_band == "success_with_cost":
            return 0.8
        if outcome_band == "partial":
            return 0.5
        if status in {"rejected", "blocked", "denied"} or outcome_band in {"blocked", "failed", "misfire"}:
            return 0.2
        unknown["execution_quality"] = "settlement_outcome_unresolved"
        return None

    @staticmethod
    def _social_consequence_score(settlement: dict[str, object], timeline: list[dict[str, object]], unknown: dict[str, str]) -> float | None:
        evidence = settlement.get("relationship_effect") or settlement.get("social_consequence") or settlement.get("relationship_evidence")
        if evidence is None:
            for event in timeline:
                payload = event.get("payload") if isinstance(event, dict) else None
                if isinstance(payload, dict) and any(key in payload for key in ("relationship_effect", "social_consequence", "relationship_evidence")):
                    evidence = payload.get("relationship_effect") or payload.get("social_consequence") or payload.get("relationship_evidence")
                    break
        if evidence is None:
            unknown["social_consequence"] = "authorized_relationship_evidence_absent"
            return None
        return 1.0 if evidence not in (False, "negative", "harmful") else 0.0

    @staticmethod
    def _recovery_quality_score(turn: CharacterTurnContext | None, timeline: list[dict[str, object]], unknown: dict[str, str]) -> float | None:
        turn_id = turn.turn_id if turn is not None else ""
        for event in timeline:
            payload = event.get("payload") if isinstance(event, dict) else None
            if not isinstance(payload, dict) or (turn_id and payload.get("turn_id") != turn_id):
                continue
            if event.get("event_type") in {"character_turn_recovery_completed", "character_turn_recovery_recorded"} or payload.get("recovery_status") == "completed":
                return 1.0
        unknown["recovery_quality"] = "completed_recovery_record_absent"
        return None

    @staticmethod
    def _confidence(source_refs: list[str], known_count: int, unknown_count: int, failure_domains: list[str], settlement: dict[str, object]) -> float:
        if len(source_refs) < 2:
            return 0.0
        if failure_domains and any(str(settlement.get(key, "") or "") for key in ("result_type", "constraint_summary", "change_summary", "stable_state_summary")):
            return 0.9
        if known_count >= 3 and unknown_count <= 2:
            return 0.85
        return 0.6

    def _candidate_policy(self, *, actor_id: str, turn_id: str, score: float, confidence: float, unknown_dimensions: list[str], failure_domains: list[str], recall: dict[str, object], settlement_payload: dict[str, object], failed_intent: str, source_refs: list[str], settlement_event_id: str, settlement_status: str) -> dict[str, object] | None:
        if not unknown_dimensions and not failure_domains and not bool(recall.get("truncated", False)):
            return None
        policy_type = "recovery" if settlement_status in {"rejected", "blocked", "denied"} or failure_domains else "recall" if not recall.get("selected_memory_refs") else "cadence"
        complete = bool(failure_domains) and bool(settlement_event_id) and len(source_refs) >= 2
        qualified = complete and confidence >= 0.8 and not (unknown_dimensions and policy_type != "recovery")
        payload = {
            "actor_id": actor_id,
            "turn_id": turn_id,
            "policy_type": policy_type,
            "status": "candidate",
            "score_before": score,
            "failure_domains": failure_domains,
            "failed_intent": failed_intent,
            "hypothesis": self._hypothesis(policy_type),
            "evidence": {
                "settlement_status": str(settlement_payload.get("settlement_status", "") or settlement_payload.get("resolution_status", "") or ""),
                "settlement_event_id": settlement_event_id,
                "evidence_refs": list(source_refs),
                "selected_memory_refs": list(recall.get("selected_memory_refs", [])) if isinstance(recall.get("selected_memory_refs", []), list) else [],
                "context_hash": str(recall.get("context_hash", "") or ""),
                "confidence": confidence,
                "unknown_dimensions": list(unknown_dimensions),
                "complete": complete,
                "qualified": qualified,
            },
        }
        candidate_id = sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        return {"candidate_id": f"character-policy:{actor_id}:{candidate_id}", **payload}

    @staticmethod
    def _score(outcome_band: str, settlement_status: str, failure_domains: list[str]) -> float:
        if outcome_band == "clean_success" or settlement_status in {"accepted", "applied", "observed"}:
            return 0.85 if failure_domains else 1.0
        if outcome_band == "success_with_cost":
            return 0.8
        if outcome_band == "partial":
            return 0.5
        if outcome_band in {"blocked", "failed", "misfire"} or settlement_status in {"rejected", "blocked", "denied"}:
            return 0.2
        return 0.0

    @staticmethod
    def _hypothesis(policy_type: str) -> str:
        return {
            "recall": "increase relevant memory coverage before cognition",
            "recovery": "add a bounded recovery step after an authoritative constraint",
            "skill_calibration": "prefer an available skill path before repeating the failed intent",
            "cadence": "preserve continuity by refreshing the actor before the next decision",
        }[policy_type]


__all__ = ["CharacterBehaviorEvaluationService"]
