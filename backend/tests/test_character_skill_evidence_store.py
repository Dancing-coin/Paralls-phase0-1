from app.character_agent.skills.models import SkillEvidence
from app.character_agent.skills.store import SkillEvidenceStore


def _build_evidence(
    *,
    evidence_id: str,
    actor_id: str = "char_a",
    skill_id: str = "first_aid",
    action_id: str = "stabilize_injured_actor",
    binding_id: str = "first_aid_to_stabilize",
    source_settlement_id: str = "settlement:1",
) -> SkillEvidence:
    return SkillEvidence(
        evidence_id=evidence_id,
        actor_id=actor_id,
        skill_id=skill_id,
        action_id=action_id,
        binding_id=binding_id,
        source_settlement_id=source_settlement_id,
        outcome_band="partial",
        primary_failure_domain="skill_failure",
        failure_domains=["skill_failure"],
        evidence_channels={
            "improvement": 0.12,
            "context": {"skill_contributions": ["apply_pressure"]},
        },
        eligible_for_candidate=False,
        eligible_for_promotion=False,
    )


def test_store_queries_evidence_with_actor_scoped_filters() -> None:
    store = SkillEvidenceStore()
    first_aid = _build_evidence(
        evidence_id="skill_evidence:1",
        actor_id="char_a",
        skill_id="first_aid",
        action_id="stabilize_injured_actor",
        binding_id="first_aid_to_stabilize",
        source_settlement_id="settlement:1",
    )
    triage = _build_evidence(
        evidence_id="skill_evidence:2",
        actor_id="char_a",
        skill_id="triage",
        action_id="assess_patient",
        binding_id="triage_to_assess",
        source_settlement_id="settlement:2",
    )
    other_actor = _build_evidence(
        evidence_id="skill_evidence:3",
        actor_id="char_b",
        skill_id="first_aid",
        action_id="stabilize_injured_actor",
        binding_id="first_aid_to_stabilize",
        source_settlement_id="settlement:1",
    )

    store.append(first_aid)
    store.append(triage)
    store.append(other_actor)

    assert [e.evidence_id for e in store.query(actor_id="char_a")] == [
        "skill_evidence:1",
        "skill_evidence:2",
    ]
    assert [e.evidence_id for e in store.query(actor_id="char_a", skill_id="first_aid")] == [
        "skill_evidence:1"
    ]
    assert [e.evidence_id for e in store.query(actor_id="char_a", action_id="assess_patient")] == [
        "skill_evidence:2"
    ]
    assert [e.evidence_id for e in store.query(actor_id="char_a", binding_id="triage_to_assess")] == [
        "skill_evidence:2"
    ]
    assert [e.evidence_id for e in store.query(actor_id="char_a", source_settlement_id="settlement:1")] == [
        "skill_evidence:1"
    ]


def test_store_deduplicates_repeated_evidence_ids() -> None:
    store = SkillEvidenceStore()
    original = _build_evidence(evidence_id="skill_evidence:shared", actor_id="char_a")
    duplicate = _build_evidence(
        evidence_id="skill_evidence:shared",
        actor_id="char_a",
        skill_id="triage",
        action_id="assess_patient",
        binding_id="triage_to_assess",
        source_settlement_id="settlement:2",
    )

    store.append(original)
    store.append(duplicate)

    matches = store.query(actor_id="char_a")
    assert len(matches) == 1
    assert matches[0].skill_id == "first_aid"
    assert matches[0].action_id == "stabilize_injured_actor"


def test_store_can_query_exact_empty_binding_id() -> None:
    store = SkillEvidenceStore()
    unbound = _build_evidence(
        evidence_id="skill_evidence:unbound",
        actor_id="char_a",
        binding_id="",
    )
    bound = _build_evidence(
        evidence_id="skill_evidence:bound",
        actor_id="char_a",
        binding_id="first_aid_to_stabilize",
    )

    store.append(unbound)
    store.append(bound)

    assert [e.evidence_id for e in store.query(actor_id="char_a")] == [
        "skill_evidence:unbound",
        "skill_evidence:bound",
    ]
    assert [e.evidence_id for e in store.query(actor_id="char_a", binding_id="")] == [
        "skill_evidence:unbound"
    ]


def test_store_keeps_appended_evidence_immutable() -> None:
    store = SkillEvidenceStore()
    evidence = _build_evidence(evidence_id="skill_evidence:immutable", actor_id="char_a")

    store.append(evidence)
    evidence.evidence_channels["context"]["skill_contributions"].append("mutated_after_append")

    recalled = store.query(actor_id="char_a")
    assert recalled[0].evidence_channels["context"]["skill_contributions"] == ["apply_pressure"]

    recalled[0].evidence_channels["context"]["skill_contributions"].append("mutated_after_query")
    reread = store.query(actor_id="char_a")
    assert reread[0].evidence_channels["context"]["skill_contributions"] == ["apply_pressure"]
