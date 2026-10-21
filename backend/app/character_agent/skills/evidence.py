from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from app.character_agent.skills.models import (
    ActionSettlementResult,
    ImitationEpisode,
    LearningEpisode,
    SkillEvidence,
    SkillEvaluationResult,
)
from app.character_agent.skills.registry import CharacterSkillRegistry
from app.character_agent.skills.store import SkillEvidenceStore

__all__ = [
    "DIFFICULTY_FACTORS",
    "LEARNING_STAGES",
    "MASTERY_DIMENSIONS",
    "ImitationEpisode",
    "LearningEpisode",
    "SkillEvidenceExtractor",
]


LEARNING_STAGES = (
    "available",
    "noticed",
    "observed",
    "imitated",
    "structured",
    "practiced",
    "operational",
    "stable",
    "integrated",
    "personalized",
    "complete",
    "evolved",
)
MASTERY_DIMENSIONS = (
    "familiarity",
    "conceptual_understanding",
    "procedural_fluency",
    "motor_precision",
    "pressure_stability",
    "transfer_capacity",
    "insight",
    "personalization",
)
DIFFICULTY_FACTORS = (
    "complexity",
    "novelty",
    "precision",
    "pressure",
    "resource_load",
    "world_binding",
    "transfer_gap",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    def __init__(
        self,
        *,
        registry: CharacterSkillRegistry | None = None,
        store: SkillEvidenceStore | None = None,
    ) -> None:
        self._registry = registry or CharacterSkillRegistry()
        self._store = store

    def extract(
        self,
        *,
        actor_id: str,
        selected_skill_path: dict[str, object] | None,
        skill_evaluation_result: SkillEvaluationResult,
        settlement_result: ActionSettlementResult,
        source_settlement_id: str,
        episode: LearningEpisode | None = None,
        allowed_privacy_scopes: set[str] | None = None,
        now_ts: int | None = None,
        source_refs: Sequence[str] | None = None,
    ) -> SkillEvidence | None:
        if not str(source_settlement_id or "").strip():
            return None
        declared_source_refs = [
            str(ref).strip()
            for ref in (source_refs or (episode.source_refs if episode is not None else ()))
            if str(ref).strip()
        ]
        if episode is not None and not declared_source_refs:
            return None
        if episode is not None and episode.source_privacy_scope:
            allowed = set(allowed_privacy_scopes or set())
            if episode.source_privacy_scope not in allowed:
                return None
        if episode is not None and episode.expires_at is not None:
            effective_now = int(
                now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp()
            )
            if effective_now >= episode.expires_at:
                return None
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
            episode=episode,
        )
        evidence_id = f"skill_evidence:{source_settlement_id}:{binding_id}"
        if self._store is not None and self._store.contains(evidence_id):
            return None
        return SkillEvidence(
            evidence_id=evidence_id,
            actor_id=actor_id,
            skill_id=skill_id,
            action_id=skill_evaluation_result.action_id,
            binding_id=binding_id,
            source_settlement_id=source_settlement_id,
            source_refs=declared_source_refs,
            source_revision=episode.source_revision if episode is not None else "",
            context_revision=episode.context_revision if episode is not None else "",
            privacy_scope=episode.source_privacy_scope if episode is not None else "",
            expires_at=episode.expires_at if episode is not None else None,
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
        episode: LearningEpisode | None = None,
    ) -> dict[str, object]:
        improvement = 0.0 if blocked else _POSITIVE_OUTCOME_SCORES.get(settlement_result.outcome_band, 0.0)
        confidence = 0.0 if blocked else _CONFIDENCE_OUTCOME_SCORES.get(settlement_result.outcome_band, 0.0)
        specialization: dict[str, float] = {}
        for tag in path.get("skill_path_tags", []):
            specialization[str(tag)] = round(improvement / 2, 3)

        maladaptive_pattern: dict[str, float] = {}
        if settlement_result.primary_failure_domain != "none":
            maladaptive_pattern[settlement_result.primary_failure_domain] = 0.05 if blocked else 0.02

        mastery = self._project_mastery(settlement_result=settlement_result, episode=episode, blocked=blocked)
        difficulty = self._project_difficulty(episode=episode)
        provenance = self._project_provenance(episode=episode)
        failure = {
            "outcome_band": settlement_result.outcome_band,
            "primary_domain": settlement_result.primary_failure_domain,
            "domains": list(settlement_result.failure_domains),
            "preserved": bool(settlement_result.outcome_band in {"blocked", "failed", "misfire", "partial"}),
        }
        return {
            "acquisition": 0.0,
            "improvement": improvement,
            "confidence": confidence,
            "specialization": specialization,
            "tool_familiarity": {},
            "maladaptive_pattern": maladaptive_pattern,
            "stage": episode.stage if episode is not None else "available",
            "mastery": mastery,
            "difficulty": difficulty,
            "provenance": provenance,
            "failure": failure,
        }

    def _project_mastery(
        self,
        *,
        settlement_result: ActionSettlementResult,
        episode: LearningEpisode | None,
        blocked: bool,
    ) -> dict[str, dict[str, object]]:
        source = episode.mastery if episode is not None else {}
        outcome_value = _POSITIVE_OUTCOME_SCORES.get(settlement_result.outcome_band, 0.0)

        def source_value(dimension: str) -> float:
            raw = source.get(dimension, 0.0)
            if isinstance(raw, dict):
                raw = raw.get("value", 0.0)
            try:
                return float(raw)
            except (TypeError, ValueError):
                return 0.0

        return {
            dimension: {
                "value": round(max(0.0, min(1.0, source_value(dimension) + (0.0 if blocked else outcome_value))), 4),
                "confidence": round(0.0 if blocked else min(1.0, _CONFIDENCE_OUTCOME_SCORES.get(settlement_result.outcome_band, 0.0)), 4),
                "evidence_refs": list(episode.evidence_refs if episode is not None else []),
                "last_validated_at": _now(),
                "decay_policy": "source_validated",
            }
            for dimension in MASTERY_DIMENSIONS
        }

    def _project_difficulty(self, *, episode: LearningEpisode | None) -> dict[str, float]:
        source = episode.difficulty if episode is not None else {}
        return {
            factor: max(0.0, min(1.0, float(source.get(factor, 0.0))))
            for factor in DIFFICULTY_FACTORS
        }

    def _project_provenance(self, *, episode: LearningEpisode | None) -> dict[str, object]:
        if episode is None:
            return {"source_refs": [], "source_revision": "", "context_revision": "", "visible_context": {}}
        return {
            "source_id": episode.source_id,
            "source_refs": list(episode.source_refs),
            "evidence_refs": list(episode.evidence_refs),
            "source_revision": episode.source_revision,
            "context_revision": episode.context_revision,
            "visible_context": dict(episode.visible_context),
            "learning_method": episode.learning_method,
            "authority_status": episode.authority_status,
            "imitation_mode": getattr(episode, "imitation_mode", ""),
            "action_error": dict(getattr(episode, "action_error", {})),
            "resource_error": dict(getattr(episode, "resource_error", {})),
            "pressure": getattr(episode, "pressure", 0.0),
            "interruptions": int(getattr(episode, "interruptions", 0)),
            "feedback": list(episode.feedback),
            "authority_accepted": getattr(episode, "authority_accepted", None),
            "review_refs": list(getattr(episode, "review_refs", [])),
        }

    def _safe_binding(self, binding_id: str):
        try:
            return next(binding for binding in self._registry.bindings() if binding.binding_id == binding_id)
        except StopIteration:
            return None
