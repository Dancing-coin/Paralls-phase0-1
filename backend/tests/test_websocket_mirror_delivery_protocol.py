from __future__ import annotations

import pytest
from pathlib import Path
from pydantic import ValidationError

from app.ws_protocol import (
    GameplayMirrorCapabilityOffer,
    GameplayMirrorDeliveryEnvelope,
    GameplayMirrorPredictionResolution,
    GameplayMirrorReceipt,
    GameplayMirrorProtocolError,
    WebSocketSessionRenewalRequest,
)
from app.services.websocket_session_auth_service import WebSocketSessionBinding
from app.gameplay.godot_mirror_delivery import GameplayMirrorReceiptLedger, GameplayMirrorDeliveryError


def test_renewal_request_cannot_carry_client_subject_scope_or_credential() -> None:
    with pytest.raises(ValidationError):
        WebSocketSessionRenewalRequest.model_validate(
            {
                "protocol_version": 2,
                "principal_ref": "principal:client",
                "allowed_actor_refs": ["actor:client"],
                "credential": "client-issued",
            }
        )


def test_delivery_envelope_requires_server_epoch_sequence_and_safe_snapshot_metadata() -> None:
    with pytest.raises(ValidationError):
        GameplayMirrorDeliveryEnvelope.model_validate(
            {
                "delivery_kind": "snapshot",
                "actor_ref": "actor:a",
                "projection_schema": "gameplay_runtime_state.godot.v1",
                "payload": {"projection_kind": "gameplay_runtime_state.godot.v1"},
            }
        )

    envelope = GameplayMirrorDeliveryEnvelope.model_validate(
        {
            "delivery_kind": "snapshot",
            "connection_epoch": 3,
            "delivery_sequence": 7,
            "actor_ref": "actor:a",
            "projection_schema": "gameplay_runtime_state.godot.v1",
            "facade_revision": "facade:7",
            "payload": {"projection_kind": "gameplay_runtime_state.godot.v1"},
        }
    )

    assert envelope.delivery_sequence == 7


def test_delta_envelope_requires_exact_base_checksum_and_target_revision_metadata() -> None:
    with pytest.raises(ValidationError):
        GameplayMirrorDeliveryEnvelope.model_validate(
            {
                "delivery_kind": "delta",
                "connection_epoch": 3,
                "delivery_sequence": 8,
                "actor_ref": "actor:a",
                "projection_schema": "gameplay_runtime_state.godot.v1",
                "facade_revision": "facade:8",
                "payload": {},
            }
        )

    delta = GameplayMirrorDeliveryEnvelope.model_validate(
        {
            "delivery_kind": "delta",
            "connection_epoch": 3,
            "delivery_sequence": 8,
            "actor_ref": "actor:a",
            "projection_schema": "gameplay_runtime_state.godot.v1",
            "facade_revision": "facade:8",
            "base_facade_revision": "facade:7",
            "base_snapshot_checksum": "sha256:base",
            "target_snapshot_checksum": "sha256:target",
            "source_revision_vector": {"stream:actor:a": 8},
            "payload": {},
        }
    )

    assert delta.base_facade_revision == "facade:7"


def test_receipt_and_capability_offer_reject_scope_or_projection_field_requests() -> None:
    with pytest.raises(ValidationError):
        GameplayMirrorReceipt.model_validate(
            {"connection_epoch": 3, "delivery_sequence": 7, "actor_ref": "actor:a"}
        )


def test_prediction_resolution_requires_a_server_result_without_client_world_state() -> None:
    confirmed = GameplayMirrorPredictionResolution.model_validate(
        {
            "prediction_id": "prediction:stamina:one",
            "command_id": "command:stamina:one",
            "resolution": "confirmed",
            "transaction_id": "tx:stamina:one",
        }
    )
    rejected = GameplayMirrorPredictionResolution.model_validate(
        {
            "prediction_id": "prediction:stamina:two",
            "command_id": "command:stamina:two",
            "resolution": "rejected",
            "error_code": "insufficient_stamina",
        }
    )

    assert confirmed.transaction_id == "tx:stamina:one"
    assert rejected.error_code == "insufficient_stamina"
    with pytest.raises(ValidationError):
        GameplayMirrorPredictionResolution.model_validate(
            {
                "prediction_id": "prediction:invalid",
                "command_id": "command:invalid",
                "resolution": "confirmed",
            }
        )
    with pytest.raises(ValidationError):
        GameplayMirrorPredictionResolution.model_validate(
            {
                "prediction_id": "prediction:invalid",
                "command_id": "command:invalid",
                "resolution": "rejected",
                "world_truth_claim": {"current": 1},
            }
        )


def test_binding_contract_exposes_backend_owned_lifecycle_epoch_and_lease_fields() -> None:
    binding = WebSocketSessionBinding(
        session_ref="ws_session:opaque",
        principal_ref="principal:backend-owned",
        allowed_actor_refs=("actor:a",),
    )

    assert binding.binding_state == "bound_active"
    assert binding.connection_epoch == 0
    assert binding.lease_expires_at == 0
    with pytest.raises(ValidationError):
        WebSocketSessionBinding.model_validate(
            {
                **binding.model_dump(),
                "client_selected_scope": ["actor:forbidden"],
            }
        )


def test_protocol_error_contract_has_finite_phase4_control_codes() -> None:
    error = GameplayMirrorProtocolError(code="mirror_receipt_unknown")

    assert error.code == "mirror_receipt_unknown"
    with pytest.raises(ValidationError):
        GameplayMirrorProtocolError(code="ad_hoc_handler_error")
    with pytest.raises(ValidationError):
        GameplayMirrorCapabilityOffer.model_validate(
            {
                "protocol_version": 2,
                "supports_snapshot": True,
                "projection_fields": ["private_mind_state"],
            }
        )


def test_godot_consumer_exposes_delivery_contract_without_treating_cache_as_truth() -> None:
    source = (
        Path(__file__).resolve().parents[2] / "scripts" / "interaction" / "GameplayRuntimeStateMirrorConsumer.gd"
    ).read_text(encoding="utf-8")

    assert "func consume_delivery(payload: Dictionary) -> Dictionary:" in source
    assert "resync_required" in source
    assert "connection_epoch" in source
    assert "last_delivery_sequence" in source


def test_receipt_ledger_rejects_foreign_stale_unknown_and_expired_sequences() -> None:
    ledger = GameplayMirrorReceiptLedger(connection_epoch=4, receipt_window=2)
    ledger.record_sent(10)
    ledger.record_sent(11)
    ledger.record_sent(12)

    assert ledger.acknowledge(GameplayMirrorReceipt(connection_epoch=4, delivery_sequence=12)) is True
    with pytest.raises(GameplayMirrorDeliveryError, match="mirror_receipt_stale_epoch"):
        ledger.acknowledge(GameplayMirrorReceipt(connection_epoch=3, delivery_sequence=12))
    with pytest.raises(GameplayMirrorDeliveryError, match="mirror_receipt_unknown"):
        ledger.acknowledge(GameplayMirrorReceipt(connection_epoch=4, delivery_sequence=13))
    with pytest.raises(GameplayMirrorDeliveryError, match="mirror_receipt_out_of_window"):
        ledger.acknowledge(GameplayMirrorReceipt(connection_epoch=4, delivery_sequence=10))
