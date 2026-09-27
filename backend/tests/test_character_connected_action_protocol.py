from __future__ import annotations

import pytest

from app.ws_protocol import (
    ActorActionRequest,
    ActorControlIntent,
    ConnectedActionProtocol,
    FutureBodyStreamEnvelope,
)


def control(**overrides: object) -> ActorControlIntent:
    payload = {
        "session_id": "session:1", "actor_ref": "character:hero", "connection_epoch": 1,
        "client_sequence": 1, "physics_tick": 10, "lease_revision": 2,
        "control_intents": [{"intent": "walk", "axis": [1, 0]}], "action_request_ids": [], "sent_at": 10,
    }
    payload.update(overrides)
    return ActorControlIntent.model_validate(payload)


def test_connected_transport_accepts_sequence_and_rejects_duplicate_gap_and_old_epoch() -> None:
    protocol = ConnectedActionProtocol()
    assert protocol.admit_control(control()).accepted
    duplicate = protocol.admit_control(control())
    assert duplicate.code == "duplicate_client_sequence"
    gap = protocol.admit_control(control(client_sequence=3))
    assert gap.code == "sequence_gap"
    protocol.reconnect()
    old = protocol.admit_control(control(client_sequence=2, connection_epoch=1))
    assert old.code == "connection_epoch_stale"


def test_action_request_rejects_client_truth_and_expired_action() -> None:
    with pytest.raises(ValueError, match="forbidden semantic action field"):
        ActorActionRequest.model_validate({
            "session_id": "session:1", "actor_ref": "character:hero", "connection_epoch": 1,
            "client_sequence": 1, "physics_tick": 10, "action_instance_id": "action:1",
            "idempotency_key": "idem:1", "expected_revisions": {},
            "request": {"action_family": "melee", "damage": 10},
        })
    protocol = ConnectedActionProtocol()
    expired = protocol.admit_action(ActorActionRequest.model_validate({
        "session_id": "session:1", "actor_ref": "character:hero", "connection_epoch": 1,
        "client_sequence": 1, "physics_tick": 10, "action_instance_id": "action:1",
        "idempotency_key": "idem:1", "expected_revisions": {},
        "request": {"action_family": "melee", "expires_at_tick": 9},
    }))
    assert expired.code == "action_expired"


def test_future_body_stream_is_defined_but_not_activated_and_separate_from_facade() -> None:
    body = FutureBodyStreamEnvelope.model_validate({
        "actor_ref": "character:hero", "authority_epoch": 1, "physics_tick": 10,
        "body_revision": 2, "base_body_revision": 1, "position": [0, 0, 0],
        "velocity": [0, 0, 0], "facing": [0, 0, 1], "grounded": True,
        "support_ref": "floor:1", "active_action_ids": [], "correction_reason": "",
        "snapshot_checksum": "sha256:x",
    })
    assert body.body_revision == 2
    assert ConnectedActionProtocol.mode == "B"
