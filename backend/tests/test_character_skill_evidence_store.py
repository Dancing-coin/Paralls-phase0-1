from app.character_agent.skills.models import SkillEvidence
from app.character_agent.skills.store import SkillEvidenceStore


def _evidence(*, evidence_id: str, actor_id: str = "char_a", skill_id: str = "first_aid") -> SkillEvidence:
    return SkillEvidence(
        evidence_id=evidence_id,
        actor_id=actor_id,
        skill_id=skill_id,
        action_id="stabilize_injured_actor",
        binding_id="first_aid_to_stabilize",
        source_settlement_id=f"settlement:{evidence_id}",
        outcome_band="partial",
        primary_failure_domain="skill_failure",
        evidence_channels={"improvement": 0.1},
    )


def test_store_deduplicates_and_returns_immutable_copies() -> None:
    store = SkillEvidenceStore()
    first = store.append(_evidence(evidence_id="skill_evidence:1"))
    duplicate = store.append(_evidence(evidence_id="skill_evidence:1"))

    first.evidence_channels["improvement"] = 9.9
    stored = store.query(actor_id="char_a")

    assert duplicate.evidence_id == "skill_evidence:1"
    assert len(stored) == 1
    assert stored[0].evidence_channels["improvement"] == 0.1


def test_store_queries_are_actor_scoped_and_filterable() -> None:
    store = SkillEvidenceStore()
    store.append(_evidence(evidence_id="skill_evidence:1", actor_id="char_a", skill_id="first_aid"))
    store.append(_evidence(evidence_id="skill_evidence:2", actor_id="char_a", skill_id="triage"))
    store.append(_evidence(evidence_id="skill_evidence:3", actor_id="char_b", skill_id="first_aid"))

    first_aid = store.query(actor_id="char_a", skill_id="first_aid")
    by_binding = store.query(actor_id="char_a", binding_id="first_aid_to_stabilize")
    other_actor = store.query(actor_id="char_b")

    assert [item.skill_id for item in first_aid] == ["first_aid"]
    assert len(by_binding) == 2
    assert [item.actor_id for item in other_actor] == ["char_b"]
