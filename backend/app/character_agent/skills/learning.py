from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.character_agent.skills.evidence import LEARNING_STAGES, LearningEpisode
from app.character_agent.skills.models import (
    SkillCandidate,
    SkillDefinition,
    SkillEvidence,
    SkillLearningPolicy,
    SkillPromotionDecision,
)
from app.character_agent.skills.registry import CharacterSkillRegistry


class LearningProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    idempotency_key: str
    actor_id: str
    skill_id: str
    object_id: str
    episode_id: str
    stage: str
    operation: Literal["upgrade", "branch", "mutation", "fusion", "evolution"] = "upgrade"
    evidence_refs: list[str] = Field(default_factory=list)
    source_revision: str = ""
    failure_refs: list[str] = Field(default_factory=list)


class LearningGateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool = False
    stage: str
    reasons: list[str] = Field(default_factory=list)
    proposal: LearningProposal | None = None


class SkillLearningGate:
    """Validates progress without mutating authored or learned skill state."""

    def evaluate(
        self,
        episode: LearningEpisode,
        *,
        prerequisites_met: bool = True,
        allowed_privacy_scopes: set[str] | None = None,
        current_source_revision: str = "",
        current_context_revision: str = "",
        authority_settled: bool = False,
        operation: Literal["upgrade", "branch", "mutation", "fusion", "evolution"] = "upgrade",
    ) -> LearningGateResult:
        reasons: list[str] = []
        if not prerequisites_met:
            reasons.append("missing_prerequisite")
        allowed = set(allowed_privacy_scopes or set())
        if episode.source_privacy_scope and episode.source_privacy_scope not in allowed:
            reasons.append("privacy_mismatch")
        if current_source_revision and episode.source_revision and episode.source_revision != current_source_revision:
            reasons.append("stale_source")
        elif episode.expected_source_revision and episode.expected_source_revision != current_source_revision:
            reasons.append("stale_source")
        if current_context_revision and episode.context_revision and episode.context_revision != current_context_revision:
            reasons.append("stale_context")
        if not episode.source_refs:
            reasons.append("missing_source_evidence")
        if operation not in {"upgrade", "branch", "mutation", "fusion", "evolution"}:
            reasons.append("unknown_learning_operation")
        if episode.stage == "evolved" and not authority_settled:
            reasons.append("authority_required")
        if reasons:
            return LearningGateResult(accepted=False, stage=episode.stage, reasons=_unique(reasons))
        proposal = LearningProposal(
            proposal_id=f"learning:{episode.episode_id}",
            idempotency_key=f"learning:{episode.learner_id}:{episode.object_id}:{episode.episode_id}",
            actor_id=episode.learner_id,
            skill_id=episode.skill_id,
            object_id=episode.object_id,
            episode_id=episode.episode_id,
            stage=episode.stage,
            operation=operation,
            evidence_refs=list(dict.fromkeys(episode.source_refs + episode.evidence_refs)),
            source_revision=episode.source_revision,
        )
        return LearningGateResult(accepted=True, stage=episode.stage, proposal=proposal)

    def transition(
        self,
        episode: LearningEpisode,
        target_stage: str,
        *,
        authority_settled: bool = False,
        operation: Literal["upgrade", "branch", "mutation", "fusion", "evolution"] = "upgrade",
    ) -> LearningGateResult:
        if target_stage not in LEARNING_STAGES:
            return LearningGateResult(accepted=False, stage=episode.stage, reasons=["unknown_learning_stage"])
        if target_stage == "evolved" and not authority_settled:
            return LearningGateResult(accepted=False, stage=episode.stage, reasons=["authority_required"])
        updated = episode.model_copy(update={"stage": target_stage})
        return self.evaluate(updated, authority_settled=authority_settled, operation=operation)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


class SkillCandidateStore:
    def __init__(self, *, registry: CharacterSkillRegistry | None = None) -> None:
        self._registry = registry or CharacterSkillRegistry()
        self._candidates: dict[tuple[str, str], SkillCandidate] = {}
        self._progress: dict[tuple[str, str], dict[str, Any]] = {}

    def observe(self, evidence: SkillEvidence) -> SkillCandidate | None:
        if not evidence.eligible_for_candidate:
            return None

        skill_definition = self._safe_skill(evidence.skill_id)
        key = (evidence.actor_id, evidence.skill_id)
        current = self._candidates.get(key)
        if current is None:
            current = SkillCandidate(
                actor_id=evidence.actor_id,
                skill_id=evidence.skill_id,
                domains=self._candidate_domains(skill_definition),
                learnability=skill_definition.learnability if skill_definition is not None else "natural",
                blocked_domains=self._candidate_blocked_domains(skill_definition),
                required_grants=self._required_grants(skill_definition),
            )

        if evidence.evidence_id in current.evidence_refs:
            return current.model_copy(deep=True)

        evidence_refs = self._merge(current.evidence_refs, [evidence.evidence_id])
        action_ids = self._merge(current.action_ids, [evidence.action_id])
        binding_ids = self._merge(current.binding_ids, [evidence.binding_id] if evidence.binding_id else [])
        specialization = dict(current.specialization)
        for key_name, value in evidence.evidence_channels.get("specialization", {}).items():
            specialization[str(key_name)] = specialization.get(str(key_name), 0.0) + float(value)

        updated = current.model_copy(
            update={
                "evidence_refs": evidence_refs,
                "action_ids": action_ids,
                "binding_ids": binding_ids,
                "evidence_count": len(evidence_refs),
                "improvement_score": current.improvement_score + float(evidence.evidence_channels.get("improvement", 0.0)),
                "confidence_score": current.confidence_score + float(evidence.evidence_channels.get("confidence", 0.0)),
                "specialization": specialization,
                "latest_evidence_id": evidence.evidence_id,
            },
            deep=True,
        )
        self._candidates[key] = updated
        progress = self._progress.setdefault(
            key,
            {"stage": "available", "mastery": {}, "evidence_refs": []},
        )
        stage = evidence.evidence_channels.get("stage")
        if isinstance(stage, str) and stage in LEARNING_STAGES:
            progress["stage"] = stage
        mastery = evidence.evidence_channels.get("mastery")
        if isinstance(mastery, dict):
            progress["mastery"] = dict(mastery)
        progress["evidence_refs"] = list(evidence_refs)
        return updated.model_copy(deep=True)

    def candidate(self, *, actor_id: str, skill_id: str) -> SkillCandidate | None:
        candidate = self._candidates.get((actor_id, skill_id))
        return candidate.model_copy(deep=True) if candidate is not None else None

    def all_for_actor(self, *, actor_id: str) -> list[SkillCandidate]:
        return [
            candidate.model_copy(deep=True)
            for (candidate_actor_id, _), candidate in self._candidates.items()
            if candidate_actor_id == actor_id
        ]

    def progress(self, *, actor_id: str, skill_id: str) -> dict[str, Any] | None:
        value = self._progress.get((actor_id, skill_id))
        return dict(value) if value is not None else None

    def _safe_skill(self, skill_id: str) -> SkillDefinition | None:
        try:
            return self._registry.skill(skill_id)
        except KeyError:
            return None

    def _candidate_domains(self, skill_definition: SkillDefinition | None) -> list[str]:
        if skill_definition is None:
            return []
        return self._merge(skill_definition.domains, list(skill_definition.settlement_categories))

    def _candidate_blocked_domains(self, skill_definition: SkillDefinition | None) -> list[str]:
        if skill_definition is None:
            return []
        blocked = []
        for domain in self._candidate_domains(skill_definition):
            if domain in {"authority", "special"} and domain not in blocked:
                blocked.append(domain)
        return blocked

    def _required_grants(self, skill_definition: SkillDefinition | None) -> list[str]:
        if skill_definition is None or skill_definition.learnability not in {"granted", "locked"}:
            return []
        return [skill_definition.skill_id]

    def _merge(self, current: list[str], additions: list[str]) -> list[str]:
        merged = list(current)
        for item in additions:
            if item and item not in merged:
                merged.append(item)
        return merged


class SkillPromotionGate:
    def __init__(self, *, policy: SkillLearningPolicy | None = None) -> None:
        self._policy = policy or SkillLearningPolicy()

    def evaluate(
        self,
        candidate: SkillCandidate,
        *,
        authored_profile: dict[str, Any] | None = None,
        human_grants: set[str] | None = None,
        scripted_grants: set[str] | None = None,
        minimum_evidence_count: int = 3,
    ) -> SkillPromotionDecision:
        reasons: list[str] = []
        status = "approved"
        grants = set(human_grants or set()) | set(scripted_grants or set())
        authored_profile = dict(authored_profile or {})
        capability_layer = authored_profile.get("capability_constraint_layer")
        if not isinstance(capability_layer, dict):
            capability_layer = {}

        if not self._policy.promotion_enabled:
            reasons.append("promotion_disabled")
        if candidate.learnability not in {"natural", "trained", "granted", "locked"}:
            reasons.append("unsupported_learnability")
        if candidate.learnability == "locked":
            reasons.append("locked_skill_requires_explicit_grant")
            status = "needs_grant"
        if candidate.learnability == "granted" and candidate.skill_id not in grants:
            reasons.append("granted_skill_requires_explicit_grant")
            status = "needs_grant"
        if candidate.evidence_count < minimum_evidence_count:
            reasons.append("insufficient_evidence")
        if candidate.improvement_score <= 0.0:
            reasons.append("non_positive_improvement_signal")

        blocked_domains = set(self._policy.blocked_domains)
        if self._policy.allowed_domains:
            allowed_domains = set(self._policy.allowed_domains)
            if not any(domain in allowed_domains for domain in candidate.domains):
                reasons.append("domain_not_allowed")
        if any(domain in blocked_domains for domain in candidate.domains + candidate.blocked_domains):
            reasons.append("blocked_domain")

        whitelist = capability_layer.get("skill_learning_whitelist")
        if isinstance(whitelist, list) and whitelist and candidate.skill_id not in {str(item) for item in whitelist}:
            reasons.append("authored_profile_incompatible")
        blacklist = capability_layer.get("skill_learning_blacklist")
        if isinstance(blacklist, list) and candidate.skill_id in {str(item) for item in blacklist}:
            reasons.append("authored_profile_incompatible")

        required_grants = set(candidate.required_grants)
        if required_grants and not required_grants.issubset(grants):
            reasons.append("missing_required_grant")
            status = "needs_grant"

        approved = not reasons and self._policy.promotion_enabled
        if not approved and status == "approved":
            status = "rejected"
        if approved:
            status = "approved"

        return SkillPromotionDecision(
            actor_id=candidate.actor_id,
            skill_id=candidate.skill_id,
            approved=approved,
            status=status,
            reasons=reasons,
            evidence_refs=list(candidate.evidence_refs),
        )
