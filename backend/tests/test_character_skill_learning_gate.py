from __future__ import annotations

from copy import deepcopy

from app.character_agent.skills.learning import SkillCandidateStore, SkillPromotionGate
from app.character_agent.skills.models import SkillDefinition, SkillEvidence, SkillLearningPolicy
from app.character_agent.skills.registry import CharacterSkillRegistry
from app.character_agent.skills.store import SkillEvidenceStore


def _build_registry(*, skill_id: str = "first_aid", domains: list[str] | None = None, learnability: str = "natural") -> CharacterSkillRegistry:
    return CharacterSkillRegistry(
        skills=[
            SkillDefinition(
                skill_id=skill_id,
                display_name="First Aid",
                settlement_categories=["cognitive", "tool"],
                domains=domains or ["medical"],
                learnability=learnability,
            )
        ]
    )


def _build_evidence(
    *,
    evidence_id: str,
    skill_id: str = "first_aid",
    actor_id: str = "char_a",
    action_id: str = "stabilize_injured_actor",
    eligible_for_candidate: bool = True,
    eligible_for_promotion: bool = False,
    source_settlement_id: str | None = None,
) -> SkillEvidence:
    return SkillEvidence(
        evidence_id=evidence_id,
        actor_id=actor_id,
        skill_id=skill_id,
        action_id=action_id,
        binding_id=f"{skill_id}_binding",
        source_settlement_id=source_settlement_id or f"settlement:{evidence_id}",
        outcome_band="partial",
        primary_failure_domain="skill_failure",
        failure_domains=["skill_failure"],
        evidence_channels={"improvement": 0.12, "confidence": 0.03},
        eligible_for_candidate=eligible_for_candidate,
        eligible_for_promotion=eligible_for_promotion,
    )


def _build_authored_profile(*, skills: list[str] | None = None, knowledge_domains: list[str] | None = None) -> dict[str, object]:
    return {
        "capability_constraint_layer": {
            "skills": list(skills or []),
            "knowledge_domains": list(knowledge_domains or []),
        }
    }


def test_candidate_store_aggregates_candidate_evidence_by_skill() -> None:
    evidence_store = SkillEvidenceStore()
    evidence_store.append(
        _build_evidence(
            evidence_id="skill_evidence:1",
            action_id="stabilize_injured_actor",
            eligible_for_candidate=True,
            eligible_for_promotion=False,
        )
    )
    evidence_store.append(
        _build_evidence(
            evidence_id="skill_evidence:2",
            action_id="assess_patient",
            eligible_for_candidate=True,
            eligible_for_promotion=True,
        )
    )
    evidence_store.append(
        _build_evidence(
            evidence_id="skill_evidence:3",
            action_id="ignore_me",
            eligible_for_candidate=False,
            eligible_for_promotion=False,
        )
    )

    store = SkillCandidateStore(registry=_build_registry())
    candidates = store.rebuild_from_evidence(actor_id="char_a", evidence_store=evidence_store)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.actor_id == "char_a"
    assert candidate.skill_id == "first_aid"
    assert candidate.learnability == "natural"
    assert candidate.domains == ("medical",)
    assert candidate.total_evidence_count == 2
    assert candidate.promotion_evidence_count == 1
    assert candidate.evidence_ids == ("skill_evidence:1", "skill_evidence:2")
    assert candidate.action_ids == ("assess_patient", "stabilize_injured_actor")
    assert [item.skill_id for item in store.query(actor_id="char_a")] == ["first_aid"]


def test_promotion_gate_rejects_when_promotion_policy_disabled() -> None:
    evidence_store = SkillEvidenceStore()
    evidence_store.append(
        _build_evidence(
            evidence_id="skill_evidence:1",
            skill_id="first_aid",
            eligible_for_promotion=True,
        )
    )
    evidence_store.append(
        _build_evidence(
            evidence_id="skill_evidence:2",
            skill_id="first_aid",
            eligible_for_promotion=True,
        )
    )

    candidate = SkillCandidateStore(registry=_build_registry()).rebuild_from_evidence(
        actor_id="char_a",
        evidence_store=evidence_store,
    )[0]

    decision = SkillPromotionGate().evaluate(
        candidate=candidate,
        skill_definition=_build_registry().skill("first_aid"),
        learning_policy=SkillLearningPolicy(),
        authored_profile=_build_authored_profile(knowledge_domains=["medical"]),
    )

    assert decision.allowed is False
    assert "promotion policy disabled" in decision.reasons


def test_promotion_gate_rejects_blocked_authority_domain_without_explicit_grant() -> None:
    evidence_store = SkillEvidenceStore()
    evidence_store.append(
        _build_evidence(
            evidence_id="skill_evidence:1",
            skill_id="command_voice",
            eligible_for_promotion=True,
        )
    )
    evidence_store.append(
        _build_evidence(
            evidence_id="skill_evidence:2",
            skill_id="command_voice",
            eligible_for_promotion=True,
        )
    )

    registry = _build_registry(skill_id="command_voice", domains=["authority"], learnability="trained")
    candidate = SkillCandidateStore(registry=registry).rebuild_from_evidence(
        actor_id="char_a",
        evidence_store=evidence_store,
    )[0]

    decision = SkillPromotionGate().evaluate(
        candidate=candidate,
        skill_definition=registry.skill("command_voice"),
        learning_policy=SkillLearningPolicy(promotion_enabled=True, auto_promotion_enabled=True),
        authored_profile=_build_authored_profile(knowledge_domains=["authority"]),
    )

    assert decision.allowed is False
    assert "blocked domain requires explicit grant: authority" in decision.reasons


def test_promotion_gate_requires_explicit_grant_for_granted_or_locked_skills() -> None:
    evidence_store = SkillEvidenceStore()
    evidence_store.append(
        _build_evidence(
            evidence_id="skill_evidence:1",
            skill_id="seal_access",
            eligible_for_promotion=True,
        )
    )
    evidence_store.append(
        _build_evidence(
            evidence_id="skill_evidence:2",
            skill_id="seal_access",
            eligible_for_promotion=True,
        )
    )

    registry = _build_registry(skill_id="seal_access", domains=["ritual"], learnability="granted")
    candidate = SkillCandidateStore(registry=registry).rebuild_from_evidence(
        actor_id="char_a",
        evidence_store=evidence_store,
    )[0]

    rejected = SkillPromotionGate().evaluate(
        candidate=candidate,
        skill_definition=registry.skill("seal_access"),
        learning_policy=SkillLearningPolicy(promotion_enabled=True, auto_promotion_enabled=True),
        authored_profile=_build_authored_profile(knowledge_domains=["ritual"]),
    )

    assert rejected.allowed is False
    assert "learnability requires explicit grant: granted" in rejected.reasons

    allowed = SkillPromotionGate().evaluate(
        candidate=candidate,
        skill_definition=registry.skill("seal_access"),
        learning_policy=SkillLearningPolicy(promotion_enabled=True, auto_promotion_enabled=True),
        authored_profile=_build_authored_profile(knowledge_domains=["ritual"]),
        granted_skill_ids={"seal_access"},
    )

    assert allowed.allowed is True
    assert allowed.reasons == ()


def test_promotion_gate_rejects_authored_profile_incompatible_candidate_and_insufficient_evidence() -> None:
    evidence_store = SkillEvidenceStore()
    evidence_store.append(
        _build_evidence(
            evidence_id="skill_evidence:1",
            skill_id="field_surgery",
            eligible_for_promotion=False,
        )
    )

    registry = _build_registry(skill_id="field_surgery", domains=["medical"], learnability="natural")
    candidate = SkillCandidateStore(registry=registry).rebuild_from_evidence(
        actor_id="char_a",
        evidence_store=evidence_store,
    )[0]

    decision = SkillPromotionGate().evaluate(
        candidate=candidate,
        skill_definition=registry.skill("field_surgery"),
        learning_policy=SkillLearningPolicy(promotion_enabled=True, auto_promotion_enabled=True),
        authored_profile=_build_authored_profile(knowledge_domains=["court"]),
    )

    assert decision.allowed is False
    assert "insufficient promotion evidence" in decision.reasons
    assert "authored profile incompatible with skill domains" in decision.reasons


def test_promotion_gate_does_not_mutate_authored_profile() -> None:
    evidence_store = SkillEvidenceStore()
    evidence_store.append(
        _build_evidence(
            evidence_id="skill_evidence:1",
            skill_id="field_surgery",
            eligible_for_promotion=True,
        )
    )
    evidence_store.append(
        _build_evidence(
            evidence_id="skill_evidence:2",
            skill_id="field_surgery",
            eligible_for_promotion=True,
        )
    )

    registry = _build_registry(skill_id="field_surgery", domains=["medical"], learnability="natural")
    candidate = SkillCandidateStore(registry=registry).rebuild_from_evidence(
        actor_id="char_a",
        evidence_store=evidence_store,
    )[0]
    authored_profile = _build_authored_profile(skills=["observation"], knowledge_domains=["medical"])
    profile_before = deepcopy(authored_profile)

    decision = SkillPromotionGate().evaluate(
        candidate=candidate,
        skill_definition=registry.skill("field_surgery"),
        learning_policy=SkillLearningPolicy(promotion_enabled=True, auto_promotion_enabled=True),
        authored_profile=authored_profile,
    )

    assert decision.allowed is True
    assert authored_profile == profile_before
