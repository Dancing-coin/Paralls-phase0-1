import json

import pytest

from app.gameplay.godot_mirror_delivery import GameplayMirrorDeltaEncoder
from scripts.verification.population_mixed_mirror import MixedMirrorReceiver
from test_mirror_delta_transport import _message, _send


def receive(client, packet):
    return client.receive(json.dumps(packet))


def test_connection_gap_discards_even_snapshot_and_requires_all_actor_bases_again():
    client = MixedMirrorReceiver({"actor:a", "actor:b"}, epoch=1)
    receive(client, _message(1))
    receive(client, _message(2, actor="actor:b"))
    gap = receive(client, _message(4, revision=4))
    assert gap == dict(applied=False, reason="sequence_gap", request_actor_refs=["actor:a", "actor:b"], recovered=False)
    assert not client.wire.snapshots and client.wire.sequence == 4
    assert receive(client, _message(3))["reason"] == "old_sequence"
    assert client.wire.sequence == 4
    assert not receive(client, _message(5, revision=5))["recovered"]
    assert receive(client, _message(6, actor="actor:b", revision=5))["recovered"]
    assert set(client.wire.snapshots) == {"actor:a", "actor:b"}


def test_actor_control_keeps_other_base_and_waiting_delta_never_applies():
    client = MixedMirrorReceiver({"actor:a", "actor:b"}, epoch=1)
    encoder = GameplayMirrorDeltaEncoder()
    receive(client, _send(encoder, _message(1)))
    receive(client, _send(encoder, _message(2, actor="actor:b")))
    control = receive(client, dict(message_type="gameplay_mirror_resync_required",
        payload=dict(actor_ref="actor:b", reason_code="mirror_backpressure")))
    assert control["request_actor_refs"] == ["actor:b"] and client.wire.sequence == 2
    assert set(client.wire.snapshots) == {"actor:a"}
    assert receive(client, _send(encoder, _message(3, revision=2)))["applied"]
    waiting = receive(client, _send(encoder, _message(4, actor="actor:b", revision=2)))
    assert waiting["reason"] == "awaiting_snapshot" and "actor:b" not in client.wire.snapshots
    assert receive(client, _send(encoder, _message(5, actor="actor:b", revision=3), force_snapshot=True))["recovered"]
    bad = _send(encoder, _message(6, revision=3))
    bad["payload"]["base_snapshot_checksum"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="cost_probe_delta_anchor_mismatch"):
        receive(client, bad)
    assert client.wire.sequence == 5


@pytest.mark.parametrize("packet", [_message(1, actor="actor:private"), _message(1, epoch=2),
    dict(message_type="gameplay_mirror_resync_required", payload=dict(actor_ref="actor:a", reason_code="unknown"))])
def test_scope_epoch_or_control_violation_does_not_become_recovery(packet):
    client = MixedMirrorReceiver({"actor:a"}, epoch=1)
    with pytest.raises(ValueError, match="mixed_mirror_"):
        receive(client, packet)
    assert client.wire.sequence == 0 and not client.wire.snapshots


def test_reconnected_receiver_cannot_reuse_previous_connection_delta_base():
    encoder = GameplayMirrorDeltaEncoder()
    first = _send(encoder, _message(1, epoch=2))
    second = _send(encoder, _message(2, epoch=2, revision=2))
    client = MixedMirrorReceiver({"actor:a"}, epoch=2)
    second["payload"]["delivery_sequence"] = 1
    with pytest.raises(ValueError, match="cost_probe_delta_base_missing"):
        receive(client, second)
    assert receive(client, first)["recovered"]


@pytest.mark.parametrize('mode', ['normal', 'gap', 'awaiting'])
@pytest.mark.parametrize('field', ['connection_epoch', 'delivery_sequence'])
@pytest.mark.parametrize('bad_type', ['bool', 'string', 'float'])
def test_malformed_cursor_is_rejected_before_any_recovery_state_change(mode, field, bad_type):
    client = MixedMirrorReceiver({'actor:a'}, epoch=1)
    encoder = GameplayMirrorDeltaEncoder()
    first = _send(encoder, _message(1))
    if mode == 'normal':
        packet = first
    else:
        receive(client, first)
        if mode == 'gap':
            packet = _message(3, revision=2)
        else:
            receive(client, dict(message_type='gameplay_mirror_resync_required',
                payload=dict(actor_ref='actor:a', reason_code='mirror_backpressure')))
            packet = _send(encoder, _message(2, revision=2))
    original = packet['payload'][field]
    packet['payload'][field] = {'bool': True, 'string': str(original), 'float': float(original)}[bad_type]
    def state():
        return json.dumps(dict(sequence=client.wire.sequence, epoch=client.wire.epoch,
            snapshots={actor: client.wire.sync.snapshot_payload(snapshot) for actor, snapshot in client.wire.snapshots.items()},
            awaiting=sorted(client.awaiting), bytes_received=client.wire.bytes_received,
            counts=dict(client.wire.counts)), sort_keys=True)

    before = state()
    with pytest.raises(ValueError, match='mixed_mirror_cursor_invalid'):
        receive(client, packet)
    assert state() == before
