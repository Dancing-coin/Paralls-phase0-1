from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any


class CharacterBehaviorEvaluationService:
    """Builds a read-only behavior score and policy candidate from one turn."""

    _CHAIN_TYPES = (
        "l2_reasoning_request",
        "character_interpretation_event",
        "goal_state_event",
        "character_agent_execution_request",
    )

    def evaluate(
        self,
        *,
        actor_id: str,
        settlement_event: dict[str, object],
        timeline: list[dict[str, object]],
    ) -> dict[str, object]:
        settlement_payload = settlement_event.get("payload", {})
        if not isinstance(settlement_payload, dict):
            settlement_payload = {}
        chain = self._latest_chain(timeline, settlement_event.get("producer_ts", 0))
        reasoning = chain.get("l2_reasoning_request", {})
        reasoning_payload = reasoning.get("payload", {}) if isinstance(reasoning, dict) else {}
        context = reasoning_payload.get("context", {}) if isinstance(reasoning_payload, dict) else {}
        if not isinstance(context, dict):
            context = {}
        recall = context.get("memory_recall", {})
        if not isinstance(recall, dict):
            recall = {}
        interpretation = chain.get("character_interpretation_event", {})
        interpretation_payload = interpretation.get("payload", {}) if isinstance(interpretation, dict) else {}
        if not isinstance(interpretation_payload, dict):
            interpretation_payload = {}
        goal = chain.get("goal_state_event", {})
        goal_payload = goal.get("payload", {}) if isinstance(goal, dict) else {}
        if not isinstance(goal_payload, dict):
            goal_payload = {}
        execution = chain.get("character_agent_execution_request", {})
        execution_payload = execution.get("payload", {}) if isinstance(execution, dict) else {}
        if not isinstance(execution_payload, dict):
            execution_payload = {}
        proposal = execution_payload.get("composite_action_proposal", {})
        if not isinstance(proposal, dict):
            proposal = {}
        failed_intent = str(
            execution_payload.get("selected_intent", "")
            or proposal.get("source_intent", "")
            or ""
        )

        metadata = settlement_payload.get("action_settlement_result", {})
        if not isinstance(metadata, dict):
            metadata = {}
        failure_domains = [
            str(value)
            for value in metadata.get("failure_domains", settlement_payload.get("failure_domains", []))
            if str(value)
        ] if isinstance(metadata.get("failure_domains", settlement_payload.get("failure_domains", [])), list) else []
        outcome_band = str(metadata.get("outcome_band", "") or "")
        settlement_status = str(settlement_payload.get("settlement_status", "") or settlement_payload.get("resolution_status", "") or "")
        score = self._score(outcome_band, settlement_status, failure_domains)
        candidate = self._candidate_policy(
            actor_id=actor_id,
            score=score,
            failure_domains=failure_domains,
            recall=recall,
            settlement_payload=settlement_payload,
            failed_intent=failed_intent,
        )
        source_refs = [
            str(event.get("event_id", ""))
            for event in chain.values()
            if isinstance(event, dict) and str(event.get("event_id", ""))
        ]
        source_refs.append(str(settlement_event.get("event_id", "")))
        return {
            "actor_id": actor_id,
            "behavior_score": score,
            "outcome_band": outcome_band,
            "failure_domains": failure_domains,
            "context_hash": str(recall.get("context_hash", "") or ""),
            "selected_memory_refs": list(recall.get("selected_memory_refs", [])) if isinstance(recall.get("selected_memory_refs", []), list) else [],
            "memory_budget": {
                "token_budget": int(recall.get("token_budget", 0) or 0),
                "estimated_tokens": int(recall.get("estimated_tokens", 0) or 0),
                "truncated": bool(recall.get("truncated", False)),
            },
            "interpretation": {
                "event_id": str(interpretation.get("event_id", "") if isinstance(interpretation, dict) else ""),
                "summary": str(interpretation_payload.get("interpreted_summary", "") or ""),
                "attention_target": str(interpretation_payload.get("attention_target", "") or ""),
            },
            "selected_intent": str(goal_payload.get("dominant_goal_id", "") or execution_payload.get("selected_intent", "") or ""),
            "failed_intent": failed_intent,
            "execution_event_id": str(execution.get("event_id", "") if isinstance(execution, dict) else ""),
            "settlement_event_id": str(settlement_event.get("event_id", "") or ""),
            "source_refs": source_refs,
            "candidate_policy": candidate,
        }

    def _latest_chain(self, timeline: list[dict[str, object]], producer_ts: object) -> dict[str, dict[str, object]]:
        timestamp = int(producer_ts or 0)
        result: dict[str, dict[str, object]] = {}
        for event in timeline:
            if not isinstance(event, dict) or int(event.get("producer_ts", 0) or 0) > timestamp:
                continue
            event_type = str(event.get("event_type", "") or "")
            if event_type in self._CHAIN_TYPES:
                result[event_type] = deepcopy(event)
        return result

    def _score(self, outcome_band: str, settlement_status: str, failure_domains: list[str]) -> float:
        if outcome_band == "clean_success" or settlement_status in {"accepted", "applied", "observed"}:
            return 0.85 if failure_domains else 1.0
        if outcome_band == "success_with_cost":
            return 0.8
        if outcome_band == "partial":
            return 0.5
        if outcome_band in {"blocked", "failed", "misfire"} or settlement_status in {"rejected", "blocked", "denied"}:
            return 0.2
        return 0.5

    def _candidate_policy(
        self,
        *,
        actor_id: str,
        score: float,
        failure_domains: list[str],
        recall: dict[str, object],
        settlement_payload: dict[str, object],
        failed_intent: str,
    ) -> dict[str, object] | None:
        if score >= 0.75 and not bool(recall.get("truncated", False)):
            return None
        if not recall.get("selected_memory_refs"):
            policy_type = "context_recall_policy"
        elif "world_constraint" in failure_domains or "missing_requirement" in failure_domains:
            policy_type = "recovery_policy"
        elif "skill_failure" in failure_domains:
            policy_type = "skill_calibration_policy"
        else:
            policy_type = "cadence_policy"
        payload = {
            "actor_id": actor_id,
            "policy_type": policy_type,
            "status": "candidate_only",
            "score_before": score,
            "failure_domains": failure_domains,
            "failed_intent": failed_intent,
            "hypothesis": self._hypothesis(policy_type),
            "evidence": {
                "settlement_status": str(settlement_payload.get("settlement_status", "") or ""),
                "selected_memory_refs": list(recall.get("selected_memory_refs", [])) if isinstance(recall.get("selected_memory_refs", []), list) else [],
                "context_hash": str(recall.get("context_hash", "") or ""),
            },
        }
        candidate_id = sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        return {"candidate_id": f"character-policy:{actor_id}:{candidate_id}", **payload}

    def _hypothesis(self, policy_type: str) -> str:
        return {
            "context_recall_policy": "increase relevant memory coverage before cognition",
            "recovery_policy": "add a bounded recovery step after an authoritative constraint",
            "skill_calibration_policy": "prefer an available skill path before repeating the failed intent",
            "cadence_policy": "preserve continuity by refreshing the actor before the next decision",
        }[policy_type]


__all__ = ["CharacterBehaviorEvaluationService"]
