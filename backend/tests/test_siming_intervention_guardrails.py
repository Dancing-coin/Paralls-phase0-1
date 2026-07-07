from app.models.siming_event import FairnessStateSnapshot
from app.models.siming_narrative import InterventionSeed
from app.services.siming_intervention_guardrails import SimingInterventionGuardrails


def make_snapshot() -> FairnessStateSnapshot:
    return FairnessStateSnapshot(
        snapshot_id="fairness:1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="cause",
        correlation_id="corr",
        known_fact_ids=["fact:1"],
        eligible_actor_ids=["char_b"],
        blocked_actor_ids=[],
        recent_intervention_ids=[],
        dimensions={},
    )


def make_seed(**overrides: object) -> InterventionSeed:
    payload = {
        "seed_id": "seed:1",
        "seed_type": "unresolved_reveal",
        "basis_snapshot_ref": "narrative:1",
        "basis_obligation_refs": ["fact:1"],
        "target_refs": ["char_b"],
        "suggested_band": "fact_reveal",
        "risk_tags": [],
        "explanation": "surface fact",
    }
    payload.update(overrides)
    return InterventionSeed.model_validate(payload)


def test_guardrails_reject_phase2_projection_seed() -> None:
    result = SimingInterventionGuardrails().evaluate_seed(
        make_seed(risk_tags=["phase2_projection_required"]),
        snapshot=make_snapshot(),
    )

    assert result.accepted is False
    assert "phase2_projection_required" in result.reasons


def test_guardrails_reject_unknown_fact_reference() -> None:
    result = SimingInterventionGuardrails().evaluate_seed(
        make_seed(basis_obligation_refs=["unknown_fact"]),
        snapshot=make_snapshot(),
    )

    assert result.accepted is False
    assert "unknown_fact_reference" in result.reasons


def test_guardrails_accept_seed_and_convert_to_candidate() -> None:
    result = SimingInterventionGuardrails().evaluate_seed(make_seed(), snapshot=make_snapshot())

    candidate = result.to_candidate(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="cause",
        correlation_id="corr",
    )

    assert result.accepted is True
    assert candidate.proposed_band == "fact_reveal"
    assert candidate.target_actor_id == "char_b"
    assert candidate.established_fact_ids == ["fact:1"]
    assert "guardrail_checked" in candidate.reason_tags
