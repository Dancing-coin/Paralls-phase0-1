from __future__ import annotations

from app.character_agent.skills.models import ActionSettlementResult, SkillEvaluationResult, SkillEvidence
from app.character_agent.skills.registry import CharacterSkillRegistry


_POSITIVE_OUTCOME_SCORES = {
    "blocked": 0.0,
    "failed": 0.01,
    "partial": 0.08,
    "success_with_cost": 0.12,
    "clean_success": 0.16,
    "misfire": 0.0,
}

_CONFIDENCE_OUTCOME_SCORES = {
    "blocked": 0.0,
    "failed": 0.0,
    "partial": 0.03,
    "success_with_cost": 0.05,
    "clean_success": 0.07,
    "misfire": 0.0,
}


class SkillEvidenceExtractor:
    def __init__(self, *, registry: CharacterSkillRegistry | None = None) -> None:
        self._registry = registry or CharacterSkillRegistry()

    def extract(
        self,
        *,
        actor_id: str,
        selected_skill_path: dict[str, object] | None,
        skill_evaluation_result: SkillEvaluationResult,
        settlement_result: ActionSettlementResult,
        source_settlement_id: str,
    ) -> SkillEvidence | None:
        policy = skill_evaluation_result.learning_policy_snapshot
        if not bool(policy.get("evidence_collection_enabled", True)):
            return None

        path = self._resolve_path(
            selected_skill_path=selected_skill_path,
            evaluation_result=skill_evaluation_result,
            settlement_result=settlement_result,
        )
        if not path:
            return None

        skill_id = str(path.get("skill_id", "")).strip()
        binding_id = str(path.get("binding_id", "")).strip()
        if not skill_id or not binding_id:
            return None

        binding = self._safe_binding(binding_id)
        learning = binding.learning if binding is not None else {}
        is_blocked = str(path.get("eligibility_status", "")) == "blocked" or settlement_result.outcome_band == "blocked"
        if is_blocked and not bool(learning.get("evidence_on_blocked", False)):
            return None
        if not is_blocked and not bool(learning.get("evidence_on_attempt", True)):
            return None

        evidence_channels = self._build_evidence_channels(
            path=path,
            settlement_result=settlement_result,
            blocked=is_blocked,
        )
        return SkillEvidence(
            evidence_id=f"skill_evidence:{source_settlement_id}:{binding_id}",
            actor_id=actor_id,
            skill_id=skill_id,
            action_id=skill_evaluation_result.action_id,
            binding_id=binding_id,
            source_settlement_id=source_settlement_id,
            outcome_band=settlement_result.outcome_band,
            primary_failure_domain=settlement_result.primary_failure_domain,
            failure_domains=list(settlement_result.failure_domains),
            evidence_channels=evidence_channels,
            eligible_for_candidate=bool(policy.get("candidate_generation_enabled", True)) and not is_blocked,
            eligible_for_promotion=False,
        )

    def _resolve_path(
        self,
        *,
        selected_skill_path: dict[str, object] | None,
        evaluation_result: SkillEvaluationResult,
        settlement_result: ActionSettlementResult,
    ) -> dict[str, object]:
        if selected_skill_path:
            return dict(selected_skill_path)
        if evaluation_result.selected_path:
            return dict(evaluation_result.selected_path)
        if settlement_result.outcome_band == "blocked" and evaluation_result.blocked_paths:
            return dict(evaluation_result.blocked_paths[0])
        return {}

    def _build_evidence_channels(
        self,
        *,
        path: dict[str, object],
        settlement_result: ActionSettlementResult,
        blocked: bool,
    ) -> dict[str, object]:
        improvement = 0.0 if blocked else _POSITIVE_OUTCOME_SCORES.get(settlement_result.outcome_band, 0.0)
        confidence = 0.0 if blocked else _CONFIDENCE_OUTCOME_SCORES.get(settlement_result.outcome_band, 0.0)
        specialization: dict[str, float] = {}
        for tag in path.get("skill_path_tags", []):
            specialization[str(tag)] = round(improvement / 2, 3)

        maladaptive_pattern: dict[str, float] = {}
        if settlement_result.primary_failure_domain != "none":
            maladaptive_pattern[settlement_result.primary_failure_domain] = 0.05 if blocked else 0.02

        return {
            "acquisition": 0.0,
            "improvement": improvement,
            "confidence": confidence,
            "specialization": specialization,
            "tool_familiarity": {},
            "maladaptive_pattern": maladaptive_pattern,
        }

    def _safe_binding(self, binding_id: str):
        try:
            return next(binding for binding in self._registry.bindings() if binding.binding_id == binding_id)
        except StopIteration:
            return None
