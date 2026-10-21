from app.character_agent.skills.evidence import LearningEpisode
from app.character_agent.skills.learning import (
    SkillCandidateStore,
    SkillLearningGate,
    SkillPromotionGate,
)
from app.character_agent.skills.models import SkillDefinition, SkillEvidence, SkillLearningPolicy
from app.character_agent.skills.registry import CharacterSkillRegistry


def _evidence(*, evidence_id: str, skill_id: str, improvement: float = 0.12, confidence: float = 0.04) -> SkillEvidence:
    return SkillEvidence(
        evidence_id=evidence_id,
        actor_id="char_a",
        skill_id=skill_id,
        action_id="stabilize_injured_actor",
        binding_id=f"{skill_id}_binding",
        source_settlement_id=f"settlement:{evidence_id}",
        outcome_band="partial",
        primary_failure_domain="skill_failure",
        evidence_channels={
            "improvement": improvement,
            "confidence": confidence,
            "specialization": {"medical": 0.06},
        },
        eligible_for_candidate=True,
        eligible_for_promotion=False,
    )


def test_candidate_store_aggregates_only_candidate_eligible_evidence() -> None:
    registry = CharacterSkillRegistry(
        skills=[SkillDefinition(skill_id="first_aid", display_name="First Aid", domains=["medical"], learnability="trained")]
    )
    store = SkillCandidateStore(registry=registry)

    candidate = store.observe(_evidence(evidence_id="skill_evidence:1", skill_id="first_aid"))
    store.observe(_evidence(evidence_id="skill_evidence:2", skill_id="first_aid"))

    assert candidate is not None
    latest = store.candidate(actor_id="char_a", skill_id="first_aid")
    assert latest is not None
    assert latest.evidence_count == 2
    assert latest.improvement_score > 0.2
    assert latest.learnability == "trained"


def test_candidate_store_does_not_double_count_replayed_evidence() -> None:
    registry = CharacterSkillRegistry(
        skills=[SkillDefinition(skill_id="first_aid", display_name="First Aid", domains=["medical"], learnability="trained")]
    )
    store = SkillCandidateStore(registry=registry)
    evidence = _evidence(evidence_id="skill_evidence:1", skill_id="first_aid")

    store.observe(evidence)
    store.observe(evidence)
    candidate = store.candidate(actor_id="char_a", skill_id="first_aid")

    assert candidate is not None
    assert candidate.evidence_count == 1
    assert candidate.improvement_score == 0.12
    assert candidate.confidence_score == 0.04


def test_promotion_gate_rejects_disabled_policy_blocked_domains_and_missing_grants() -> None:
    registry = CharacterSkillRegistry(
        skills=[
            SkillDefinition(skill_id="command_presence", display_name="Command Presence", domains=["authority"], learnability="granted")
        ]
    )
    store = SkillCandidateStore(registry=registry)
    candidate = store.observe(_evidence(evidence_id="skill_evidence:1", skill_id="command_presence"))
    assert candidate is not None

    authored_profile = {
        "capability_constraint_layer": {
            "skill_learning_blacklist": ["command_presence"],
        }
    }
    before = authored_profile.copy()
    decision = SkillPromotionGate(policy=SkillLearningPolicy()).evaluate(
        candidate,
        authored_profile=authored_profile,
        minimum_evidence_count=1,
    )

    assert decision.approved is False
    assert "promotion_disabled" in decision.reasons
    assert "blocked_domain" in decision.reasons
    assert "missing_required_grant" in decision.reasons
    assert "authored_profile_incompatible" in decision.reasons
    assert authored_profile == before


def test_promotion_gate_allows_nonblocked_trained_skill_when_policy_and_evidence_match() -> None:
    registry = CharacterSkillRegistry(
        skills=[SkillDefinition(skill_id="first_aid", display_name="First Aid", domains=["medical"], learnability="trained")]
    )
    store = SkillCandidateStore(registry=registry)
    store.observe(_evidence(evidence_id="skill_evidence:1", skill_id="first_aid"))
    store.observe(_evidence(evidence_id="skill_evidence:2", skill_id="first_aid"))
    store.observe(_evidence(evidence_id="skill_evidence:3", skill_id="first_aid"))
    candidate = store.candidate(actor_id="char_a", skill_id="first_aid")
    assert candidate is not None

    policy = SkillLearningPolicy(
        promotion_enabled=True,
        allowed_domains=["medical"],
        blocked_domains=["authority", "special"],
    )
    decision = SkillPromotionGate(policy=policy).evaluate(
        candidate,
        authored_profile={
            "capability_constraint_layer": {
                "skill_learning_whitelist": ["first_aid"],
            }
        },
    )

    assert decision.approved is True
    assert decision.status == "approved"
    assert decision.reasons == []


def test_learning_gate_rejects_missing_prerequisite_privacy_and_stale_source_without_state_write() -> None:
    episode = LearningEpisode(
        episode_id="episode:1",
        learner_id="char_a",
        object_id="first_aid.basic_bandage@2",
        skill_id="first_aid",
        source_id="teacher:medic",
        source_revision="teacher:medic@1",
        expected_source_revision="teacher:medic@1",
        source_privacy_scope="private:teacher",
        stage="observed",
        source_refs=["observation:1"],
    )
    result = SkillLearningGate().evaluate(
        episode,
        prerequisites_met=False,
        allowed_privacy_scopes={"public"},
        current_source_revision="teacher:medic@2",
    )

    assert result.accepted is False
    assert {"missing_prerequisite", "privacy_mismatch", "stale_source"}.issubset(result.reasons)
    assert result.proposal is None


def test_learning_gate_allows_non_linear_reentry_and_requires_owner_for_evolution() -> None:
    gate = SkillLearningGate()
    episode = LearningEpisode(
        episode_id="episode:2",
        learner_id="char_a",
        object_id="first_aid.basic_bandage@2",
        skill_id="first_aid",
        source_id="teacher:medic",
        source_revision="teacher:medic@2",
        stage="stable",
        source_refs=["observation:2"],
    )
    reentry = gate.transition(episode, "practiced")
    assert reentry.accepted is True
    assert reentry.stage == "practiced"

    evolved = gate.transition(episode.model_copy(update={"stage": "complete"}), "evolved")
    assert evolved.accepted is False
    assert "authority_required" in evolved.reasons


def test_learning_gate_accepts_declared_prerequisites_when_prerequisites_are_met() -> None:
    episode = LearningEpisode(
        episode_id="episode:3",
        learner_id="char_a",
        object_id="first_aid.advanced@1",
        skill_id="first_aid",
        source_id="teacher:medic",
        source_revision="teacher:medic@2",
        stage="practiced",
        prerequisites=["first_aid.basic@1"],
        source_refs=["observation:3"],
    )

    result = SkillLearningGate().evaluate(
        episode,
        prerequisites_met=True,
        allowed_privacy_scopes=set(),
        current_source_revision="teacher:medic@2",
    )

    assert result.accepted is True
    assert result.proposal is not None
