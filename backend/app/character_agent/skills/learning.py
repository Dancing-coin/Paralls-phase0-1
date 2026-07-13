from __future__ import annotations

from collections.abc import Collection as CollectionABC
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass
from typing import Collection, Mapping

from app.character_agent.skills.catalog import create_core_skill_registry
from app.character_agent.skills.models import Learnability, SkillDefinition, SkillLearningPolicy
from app.character_agent.skills.registry import CharacterSkillRegistry
from app.character_agent.skills.store import SkillEvidenceStore


MINIMUM_CANDIDATE_EVIDENCE = 2
MINIMUM_PROMOTION_EVIDENCE = 2
NON_OVERRIDABLE_BLOCKED_DOMAINS = frozenset({"authority", "special"})


@dataclass(frozen=True)
class SkillCandidate:
    actor_id: str
    skill_id: str
    learnability: Learnability
    domains: tuple[str, ...]
    action_ids: tuple[str, ...]
    binding_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    total_evidence_count: int
    promotion_evidence_count: int


@dataclass(frozen=True)
class SkillPromotionDecision:
    allowed: bool
    reasons: tuple[str, ...]


class SkillCandidateStore:
    def __init__(self, *, registry: CharacterSkillRegistry | None = None) -> None:
        self._registry = registry or create_core_skill_registry()
        self._by_actor: dict[str, dict[str, SkillCandidate]] = {}

    def rebuild_from_evidence(
        self,
        *,
        actor_id: str,
        evidence_store: SkillEvidenceStore,
    ) -> list[SkillCandidate]:
        grouped: dict[str, list[object]] = {}
        for evidence in evidence_store.query(actor_id=actor_id):
            if not (evidence.eligible_for_candidate or evidence.eligible_for_promotion):
                continue
            try:
                self._registry.skill(evidence.skill_id)
            except KeyError:
                continue
            grouped.setdefault(evidence.skill_id, []).append(evidence)

        candidates: dict[str, SkillCandidate] = {}
        for skill_id, entries in grouped.items():
            skill = self._registry.skill(skill_id)
            evidence_ids = tuple(sorted({entry.evidence_id for entry in entries}))
            action_ids = tuple(sorted({entry.action_id for entry in entries if entry.action_id}))
            binding_ids = tuple(sorted({entry.binding_id for entry in entries if entry.binding_id}))
            promotion_evidence_count = sum(1 for entry in entries if entry.eligible_for_promotion)

            candidates[skill_id] = SkillCandidate(
                actor_id=actor_id,
                skill_id=skill_id,
                learnability=skill.learnability,
                domains=tuple(skill.domains),
                action_ids=action_ids,
                binding_ids=binding_ids,
                evidence_ids=evidence_ids,
                total_evidence_count=len(evidence_ids),
                promotion_evidence_count=promotion_evidence_count,
            )

        self._by_actor[actor_id] = candidates
        return self.query(actor_id=actor_id)

    def query(self, *, actor_id: str, skill_id: str = "") -> list[SkillCandidate]:
        actor_candidates = self._by_actor.get(actor_id, {})
        if skill_id:
            candidate = actor_candidates.get(skill_id)
            return [candidate] if candidate is not None else []
        return [actor_candidates[key] for key in sorted(actor_candidates)]


class SkillPromotionGate:
    def evaluate(
        self,
        *,
        candidate: SkillCandidate,
        skill_definition: SkillDefinition,
        learning_policy: SkillLearningPolicy,
        authored_profile: Mapping[str, object],
        granted_skill_ids: Collection[str] | None = None,
        granted_domains: Collection[str] | None = None,
    ) -> SkillPromotionDecision:
        reasons: list[str] = []
        granted_skill_lookup = {str(item) for item in granted_skill_ids or ()}
        granted_domain_lookup = {str(item) for item in granted_domains or ()}
        explicit_skill_grant = self._has_explicit_skill_grant(
            candidate=candidate,
            granted_skill_lookup=granted_skill_lookup,
        )

        if not learning_policy.promotion_enabled:
            reasons.append("promotion policy disabled")
        if not learning_policy.auto_promotion_enabled:
            reasons.append("auto promotion disabled")

        if candidate.total_evidence_count < MINIMUM_CANDIDATE_EVIDENCE:
            reasons.append("insufficient candidate evidence")
        if candidate.promotion_evidence_count < MINIMUM_PROMOTION_EVIDENCE:
            reasons.append("insufficient promotion evidence")

        capability_layer = self._mapping(authored_profile.get("capability_constraint_layer"))
        authored_skill_ids = self._string_set(capability_layer.get("skills"))
        if candidate.skill_id in authored_skill_ids:
            reasons.append("skill already present in authored profile")

        profile_domains = self._string_set(capability_layer.get("knowledge_domains"))
        skill_domains = tuple(dict.fromkeys(skill_definition.domains))
        if profile_domains and skill_domains and not profile_domains.intersection(skill_domains):
            reasons.append("authored profile incompatible with skill domains")

        blocked_domains = (
            set(learning_policy.blocked_domains).union(NON_OVERRIDABLE_BLOCKED_DOMAINS)
        ).intersection(skill_domains)
        blocked_domain_grants_allowed = skill_definition.learnability in {"granted", "locked"}
        for domain in sorted(blocked_domains):
            domain_granted = blocked_domain_grants_allowed and (
                explicit_skill_grant or domain in granted_domain_lookup
            )
            if not domain_granted:
                reasons.append(f"blocked domain requires explicit grant: {domain}")

        if skill_definition.learnability in {"granted", "locked"} and not explicit_skill_grant:
            reasons.append(f"learnability requires explicit grant: {skill_definition.learnability}")

        return SkillPromotionDecision(
            allowed=not reasons,
            reasons=tuple(reasons),
        )

    def _has_explicit_skill_grant(
        self,
        *,
        candidate: SkillCandidate,
        granted_skill_lookup: set[str],
    ) -> bool:
        return candidate.skill_id in granted_skill_lookup

    def _mapping(self, value: object) -> dict[str, object]:
        return dict(value) if isinstance(value, MappingABC) else {}

    def _string_set(self, value: object) -> set[str]:
        if isinstance(value, (str, bytes, bytearray)) or isinstance(value, MappingABC):
            return set()
        if not isinstance(value, CollectionABC):
            return set()
        return {str(item).strip() for item in value if str(item).strip()}


__all__ = [
    "MINIMUM_CANDIDATE_EVIDENCE",
    "MINIMUM_PROMOTION_EVIDENCE",
    "SkillCandidate",
    "SkillCandidateStore",
    "SkillPromotionDecision",
    "SkillPromotionGate",
]
