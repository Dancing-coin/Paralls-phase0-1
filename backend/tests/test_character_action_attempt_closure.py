from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.embodied_interaction import ActionAttempt
from app.services.embodied_authority_settlement_service import EmbodiedAuthoritySettlementService


def attempt(key: str, **changes: object) -> ActionAttempt:
    payload: dict[str, object] = {
        "attempt_id": f"attempt:{key}",
        "actor_ref": "character:street_bandage",
        "action_instance_id": f"action:{key}",
        "semantic_action_id": "action:melee.unarmed_punch",
        "target_refs": ["character:char_a"],
        "contact_marker_id": "short_punch_contact_window",
        "physics_tick": 100,
        "physics_evidence_refs": [f"contact:{key}"],
        "authority_route": "esm",
        "expected_revisions": {},
        "idempotency_key": f"street:{key}",
        "command_version": "v1",
        "causation_id": f"cause:{key}",
        "correlation_id": f"corr:{key}",
        "source": "player",
        "privacy_scope": "public",
        "connection_epoch": 1,
        "client_sequence": 1,
    }
    payload.update(changes)
    return ActionAttempt.model_validate(payload)


def positioned_service() -> EmbodiedAuthoritySettlementService:
    service = EmbodiedAuthoritySettlementService()
    assert service.record_street_pose("street_bandage", (0.0, 0.2, -9.8), physics_tick=60)
    assert service.record_street_pose("char_a", (-2.0, 0.2, -9.8), physics_tick=60)
    return service


def test_action_attempt_has_transport_identity_and_digest() -> None:
    value = attempt("contract")
    assert value.connection_epoch == 1
    assert value.client_sequence == 1
    assert value.payload_digest.startswith("sha256:")
    assert value.request_digest == value.payload_digest


def test_accepted_hit_duplicate_and_changed_duplicate_are_zero_write() -> None:
    service = positioned_service()
    first = service.settle_street_combat(attempt("accepted"))
    assert first.outcome == "committed"
    duplicate = service.settle_street_combat(attempt("accepted"))
    assert duplicate.transaction_id == first.transaction_id
    changed = service.settle_street_combat(attempt("accepted", semantic_action_id="action:melee.short_punch"))
    assert changed.outcome == "rejected"
    assert changed.failed_code == "idempotency_key_reused"
    assert service.mutation_count == 1


def test_stale_revision_and_missing_contact_evidence_do_not_write() -> None:
    service = positioned_service()
    stale = service.settle_street_combat(attempt("stale", expected_revisions={"actor:character:street_bandage": 99}))
    assert stale.outcome == "rejected"
    assert stale.failed_code == "revision_conflict"
    missing = service.settle_street_combat(attempt("missing", physics_evidence_refs=[], client_sequence=2))
    assert missing.outcome == "rejected"
    assert missing.failed_code == "action_unsupported"
    assert service.mutation_count == 0


def test_disconnected_transport_requires_reconnect_snapshot_and_resync() -> None:
    service = positioned_service()
    service.disconnect_street_transport()
    disconnected = service.settle_street_combat(attempt("offline"))
    assert disconnected.failed_code == "transport_disconnected"
    epoch = service.reconnect_street_transport()
    blocked = service.settle_street_combat(attempt("blocked", connection_epoch=epoch, client_sequence=1))
    assert blocked.failed_code == "recovery_required"
    assert service.accept_street_snapshot(epoch, snapshot_digest="sha256:snapshot", resync_marker="resync:1")
    accepted = service.settle_street_combat(attempt("recovered", connection_epoch=epoch, client_sequence=1))
    assert accepted.outcome == "committed"


def test_stale_epoch_rejected_before_authority_submission() -> None:
    service = positioned_service()
    epoch = service.reconnect_street_transport()
    assert service.accept_street_snapshot(epoch, snapshot_digest="sha256:snapshot", resync_marker="resync:1")
    stale = service.settle_street_combat(attempt("old", connection_epoch=1, client_sequence=1))
    assert stale.outcome == "rejected"
    assert stale.failed_code == "connection_epoch_stale"
    assert service.mutation_count == 0


def test_explicit_client_sequence_rejects_gap_and_duplicate() -> None:
    service = positioned_service()
    first = service.settle_street_combat(attempt("sequence-1", client_sequence=1))
    assert first.outcome == "committed"
    gap = service.settle_street_combat(attempt("sequence-3", client_sequence=3))
    assert gap.failed_code == "client_sequence_gap"
    duplicate = service.settle_street_combat(attempt("sequence-2", client_sequence=1))
    assert duplicate.failed_code == "client_sequence_stale"
    assert service.mutation_count == 1


def test_action_attempt_rejects_forbidden_client_truth() -> None:
    with pytest.raises(ValidationError):
        attempt("client-truth", damage=20)
