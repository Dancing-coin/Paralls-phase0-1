import pytest
from pydantic import ValidationError

from app.models.siming_adaptive_bridge import (
    AdaptiveBridgeNodeProposal,
    AdaptiveBridgeValidationResult,
    GeneratedAdaptiveBridgeProposalBatch,
    SimingLlmProposalAudit,
)


def realization_request() -> dict[str, object]:
    return {
        "node_id": "runtime:bridge:private-confrontation:1",
        "actor_bindings": {"speaker": "char_b", "listener": "char_c"},
        "target_object_id": "obj_letter",
        "target_environment_id": "env_lamp",
        "required_realization_keys": ["look_at_target", "focus_attention"],
        "camera_pattern": "two_actor_confrontation",
        "semantic_purpose": "private_confrontation",
        "location_state": "throne_room:letter_removed",
    }


def proposal_payload(*, pattern: str = "private_confrontation") -> dict[str, object]:
    return {
        "proposal_id": "proposal:private-confrontation:1",
        "pattern": pattern,
        "correlation_id": "corr:destroy:1",
        "causal_gap_ref": "fact:letter:destroyed",
        "title": "Private confrontation after the letter is destroyed",
        "target_actor_id": "char_b",
        "supporting_fact_refs": ["fact:letter:destroyed"],
        "required_actor_memory_refs": ["observation:char_b:letter:destroyed"],
        "obligation_refs": ["O6"],
        "attractor_refs": ["A1"],
        "realization_request": realization_request(),
        "autonomy_reason": "char_b chooses to confront the player",
    }


def audit() -> SimingLlmProposalAudit:
    return SimingLlmProposalAudit(
        provider="fake",
        route_id="test-route",
        model="test-model",
        request_id="request:1",
        correlation_id="corr:destroy:1",
        latency_ms=1,
        response_artifact_hash="a" * 64,
    )


def test_bridge_rejects_unapproved_pattern() -> None:
    with pytest.raises(ValidationError, match="pattern"):
        AdaptiveBridgeNodeProposal.model_validate(
            proposal_payload(pattern="time_travel_reset")
        )


@pytest.mark.parametrize(
    "field", ["world_fact_write", "actor_memory_write", "catalyst", "chain_of_thought"]
)
def test_bridge_rejects_authority_and_reasoning_fields(field: str) -> None:
    payload = proposal_payload()
    payload[field] = "forbidden"

    with pytest.raises(ValidationError):
        AdaptiveBridgeNodeProposal.model_validate(payload)


def test_typed_proposal_batch_carries_safe_audit_only() -> None:
    batch = GeneratedAdaptiveBridgeProposalBatch(
        proposals=[AdaptiveBridgeNodeProposal.model_validate(proposal_payload())],
        audit=audit(),
    )

    assert batch.proposals[0].pattern == "private_confrontation"
    assert batch.audit.response_artifact_hash == "a" * 64
    assert "api_key" not in batch.model_dump_json()


def test_validation_result_uses_optional_graph_commit_references() -> None:
    result = AdaptiveBridgeValidationResult(
        accepted=True,
        proposal_id="proposal:private-confrontation:1",
        graph_transaction_ref="tx:bridge:1",
        runtime_node_ref="runtime:bridge:proposal:private-confrontation:1",
    )

    assert result.reason_codes == []
