from __future__ import annotations

from typing import Any

from app.character_agent.skills.models import (
    SkillCandidate,
    SkillDefinition,
    SkillEvidence,
    SkillLearningPolicy,
    SkillPromotionDecision,
)
from app.character_agent.skills.registry import CharacterSkillRegistry


class SkillCandidateStore:
    def __init__(self, *, registry: CharacterSkillRegistry | None = None) -> None:
        self._registry = registry or CharacterSkillRegistry()
        self._candidates: dict[tuple[str, str], SkillCandidate] = {}

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
