from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.embodied_interaction import ActionAttempt
from app.services.embodied_authority_settlement_service import EmbodiedAuthoritySettlementService


def _contact_ref(attempt_id: str, physics_tick: int = 100, marker_id: str = "short_punch_contact_window") -> str:
    return f"contact:{attempt_id}:{physics_tick}:{marker_id}"


def _contact_digest(
    contact_ref: str,
    *,
    attempt_id: str,
    physics_tick: int = 100,
    marker_id: str = "short_punch_contact_window",
    actor_ref: str = "character:street_bandage",
    target_ref: str = "character:char_a",
) -> str:
    import hashlib

    canonical = (
        "street-contact-evidence:v1"
        f"|ref={contact_ref}|attempt={attempt_id}|tick={physics_tick}"
        f"|marker={marker_id}|actor={actor_ref}|target={target_ref}"
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def attempt(key: str, **changes: object) -> ActionAttempt:
    attempt_id = f"attempt:{key}"
    contact_ref = _contact_ref(attempt_id)
    payload: dict[str, object] = {
        "attempt_id": attempt_id,
        "actor_ref": "character:street_bandage",
        "action_instance_id": f"action:{key}",
        "semantic_action_id": "action:melee.unarmed_punch",
        "target_refs": ["character:char_a"],
        "contact_marker_id": "short_punch_contact_window",
        "physics_tick": 100,
        "physics_evidence_refs": [contact_ref],
        "physics_evidence_digest": _contact_digest(contact_ref, attempt_id=attempt_id),
        "action_descriptor_digest": "sha256:" + "0" * 64,
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
    assert service.record_street_pose("street_bandage", (0.0, 0.2, -9.8), physics_tick=100)
    assert service.record_street_pose("char_a", (-2.0, 0.2, -9.8), physics_tick=100)
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


def test_street_contact_evidence_is_bound_to_attempt_tick_marker_and_digest() -> None:
    service = positioned_service()
    contact_ref = _contact_ref("attempt:bad-evidence", physics_tick=99)
    result = service.settle_street_combat(
        attempt(
            "bad-evidence",
            physics_evidence_refs=[contact_ref],
            physics_evidence_digest=_contact_digest(
                contact_ref,
                attempt_id="attempt:bad-evidence",
                physics_tick=99,
            ),
        )
    )
    assert result.outcome == "rejected"
    assert result.failed_code == "physics_evidence_invalid"
    assert service.mutation_count == 0


def test_street_contact_evidence_requires_an_exact_tick_pose_snapshot() -> None:
    service = EmbodiedAuthoritySettlementService()
    assert service.record_street_pose("street_bandage", (0.0, 0.2, -9.8), physics_tick=60)
    assert service.record_street_pose("char_a", (-2.0, 0.2, -9.8), physics_tick=60)
    result = service.settle_street_combat(attempt("stale-evidence"))
    assert result.outcome == "rejected"
    assert result.failed_code == "physics_evidence_stale"
    assert service.mutation_count == 0


def test_street_contact_evidence_rejects_a_digest_mismatch() -> None:
    service = positioned_service()
    result = service.settle_street_combat(
        attempt("bad-digest", physics_evidence_digest="sha256:" + "f" * 64)
    )
    assert result.outcome == "rejected"
    assert result.failed_code == "physics_evidence_digest_mismatch"
    assert service.mutation_count == 0


def test_action_attempt_requires_transport_identity_and_attestation_digests() -> None:
    payload = attempt("required-fields").model_dump(mode="python")
    for field in ("connection_epoch", "client_sequence", "physics_evidence_digest", "action_descriptor_digest"):
        missing = dict(payload)
        missing.pop(field)
        with pytest.raises(ValidationError):
            ActionAttempt.model_validate(missing)
