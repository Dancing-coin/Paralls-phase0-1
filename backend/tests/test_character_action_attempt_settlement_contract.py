from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.embodied_interaction import ActionAttempt, AuthorityResult
from app.services.embodied_authority_settlement_service import EmbodiedAuthoritySettlementService


def valid_attempt(**overrides: object) -> ActionAttempt:
    payload: dict[str, object] = {
        "attempt_id": "attempt:1",
        "actor_ref": "character:hero",
        "action_instance_id": "action:1",
        "semantic_action_id": "melee:slash",
        "target_refs": ["object:crate"],
        "contact_marker_id": "marker:contact",
        "physics_tick": 10,
        "physics_evidence_refs": ["contact:1"],
        "physics_evidence_digest": "sha256:" + "0" * 64,
        "action_descriptor_digest": "sha256:" + "1" * 64,
        "connection_epoch": 1,
        "client_sequence": 1,
        "authority_route": "esm",
        "expected_revisions": {"actor:character:hero": 0},
        "idempotency_key": "idem:1",
        "command_version": "v1",
        "causation_id": "cause:1",
        "correlation_id": "corr:1",
        "source": "player",
        "privacy_scope": "public",
    }
    payload.update(overrides)
    return ActionAttempt.model_validate(payload)


def test_action_attempt_canonical_payload_excludes_audit_timestamp() -> None:
    attempt = valid_attempt(submitted_at=123)
    assert "submitted_at" not in attempt.canonical_payload()
    assert attempt.canonical_payload()["idempotency_key"] == "idem:1"


def test_settlement_duplicate_replays_original_transaction() -> None:
    service = EmbodiedAuthoritySettlementService()
    first = service.settle(valid_attempt())
    second = service.settle(valid_attempt(submitted_at=999))
    assert first.outcome == "committed"
    assert second.outcome == "committed"
    assert second.transaction_id == first.transaction_id
    assert second.committed_event_ids == first.committed_event_ids


def test_duplicate_key_with_changed_payload_is_rejected_without_write() -> None:
    service = EmbodiedAuthoritySettlementService()
    first = service.settle(valid_attempt())
    second = service.settle(valid_attempt(target_refs=["object:other"]))
    assert first.outcome == "committed"
    assert second.outcome == "rejected"
    assert second.failed_code == "idempotency_key_reused"
    assert service.mutation_count == 1


def test_stale_revision_is_typed_rejection() -> None:
    service = EmbodiedAuthoritySettlementService()
    service.settle(valid_attempt())
    stale = service.settle(valid_attempt(attempt_id="attempt:2", action_instance_id="action:2", idempotency_key="idem:2"))
    assert stale.outcome == "rejected"
    assert stale.failed_code in {"revision_conflict", "precondition_failed"}


def test_unauthorized_route_is_rejected() -> None:
    with pytest.raises(ValidationError):
        valid_attempt(authority_route="client")


def test_client_damage_and_ballistic_truth_are_rejected() -> None:
    with pytest.raises(ValidationError):
        valid_attempt(damage=10)
    with pytest.raises(ValidationError):
        valid_attempt(hit_confirmed=True)
    with pytest.raises(ValidationError):
        valid_attempt(projectile_id="projectile:1")


def test_payload_limits_reject_without_truncation() -> None:
    with pytest.raises(ValidationError, match="target_refs_limit"):
        valid_attempt(target_refs=[f"object:{i}" for i in range(9)])
    with pytest.raises(ValidationError, match="physics_evidence_refs_limit"):
        valid_attempt(physics_evidence_refs=[f"e:{i}" for i in range(9)])


def test_composite_rejection_has_zero_partial_write() -> None:
    service = EmbodiedAuthoritySettlementService()
    result = service.settle(valid_attempt(authority_route="composite", semantic_action_id="composite:bad"))
    assert isinstance(result, AuthorityResult)
    assert result.outcome == "rejected"
    assert result.failed_code == "composite_atomic_validation_failed"
    assert service.mutation_count == 0


def test_melee_and_hitscan_are_semantic_authority_routes() -> None:
    service = EmbodiedAuthoritySettlementService()
    melee = service.settle(valid_attempt())
    hitscan = service.settle(
        valid_attempt(
            attempt_id="attempt:hitscan",
            action_instance_id="action:hitscan",
            semantic_action_id="hitscan:fire",
            idempotency_key="idem:hitscan",
            authority_route="gameplay",
            weapon_ref="weapon:rifle",
            expected_revisions={},
        )
    )
    assert melee.outcome == "committed"
    assert hitscan.outcome == "committed"
    assert hitscan.committed_projection.get("client_damage_truth") is None
