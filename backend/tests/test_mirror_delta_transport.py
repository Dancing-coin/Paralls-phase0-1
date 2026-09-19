from copy import deepcopy
from dataclasses import replace

import pytest

from app.gameplay.godot_mirror_delivery import GameplayGodotMirrorSyncAdapter, GameplayMirrorDeltaEncoder
from app.gameplay.state_group_sync import StateGroupSyncError
from app.ws_protocol import GameplayMirrorDeliveryEnvelope
from test_gameplay_mirror_session_access_service import _projection_source


def _message(sequence, *, actor="actor:a", revision=1, epoch=1):
    view = _projection_source(actor)
    group = view.groups["resources"]
    view = replace(view, source_facade_revision=f"facade:{revision}",
                   groups={"resources": replace(group, projection_revision=f"resources:{revision}",
                                                payload={"current": revision})})
    sync = GameplayGodotMirrorSyncAdapter()
    snapshot = sync.snapshot(view)
    return {"message_type": "gameplay_mirror_delivery", "payload": GameplayMirrorDeliveryEnvelope(
        delivery_kind="snapshot", connection_epoch=epoch, delivery_sequence=sequence,
        actor_ref=actor, projection_schema=sync.schema_capabilities[0], facade_revision=snapshot.facade_revision,
        source_revision_vector=dict(snapshot.source_revision_vector), payload=sync.snapshot_payload(snapshot),
    ).model_dump(mode="json")}


def _send(encoder, message, **kwargs):
    wire, target = encoder.prepare(message, **kwargs)
    encoder.sent(wire, target)
    return wire


def test_delta_uses_only_actual_sent_base_and_preserves_full_snapshot_oracle():
    encoder = GameplayMirrorDeltaEncoder()
    first = _message(1)
    wire, pending = encoder.prepare(first)
    assert wire == first
    assert encoder.prepare(_message(2, revision=2))[0]["payload"]["delivery_kind"] == "snapshot"
    encoder.sent(wire, pending)
    second = _message(2, revision=2)
    delta = _send(encoder, second)
    outer = delta["payload"]
    assert outer["delivery_kind"] == "delta"
    assert outer["base_snapshot_checksum"] == first["payload"]["payload"]["snapshot_checksum"]
    assert outer["target_snapshot_checksum"] == second["payload"]["payload"]["snapshot_checksum"]
    assert outer["payload"]["canonical_snapshot_json"] == second["payload"]["payload"]["canonical_snapshot_json"]
    GameplayMirrorDeliveryEnvelope.model_validate(outer)
    sync = GameplayGodotMirrorSyncAdapter()
    base = sync.snapshot_from_payload(first["payload"]["payload"])
    target = sync.snapshot_from_payload(second["payload"]["payload"])
    assert sync.apply_delta(base, sync.delta(base, target)) == target


def test_shared_sequence_gap_clears_all_bases_and_stale_send_never_rewinds():
    encoder = GameplayMirrorDeltaEncoder()
    _send(encoder, _message(1))
    _send(encoder, _message(2, actor="actor:b"))
    gap = _send(encoder, _message(4, revision=4))
    assert gap["payload"]["delivery_kind"] == "snapshot"
    assert not encoder._bases
    assert _send(encoder, _message(5, actor="actor:b", revision=5))["payload"]["delivery_kind"] == "snapshot"
    _send(encoder, _message(3, actor="actor:b", revision=3))
    delta = _send(encoder, _message(6, actor="actor:b", revision=6))
    assert delta["payload"]["delivery_kind"] == "delta"
    assert delta["payload"]["base_facade_revision"] == "facade:5"


def test_resync_unsubscribe_epoch_and_explicit_snapshot_invalidate_exact_base():
    encoder = GameplayMirrorDeltaEncoder()
    _send(encoder, _message(1))
    assert _send(encoder, _message(2, revision=2), force_snapshot=True)["payload"]["delivery_kind"] == "snapshot"
    encoder.sent({"message_type": "gameplay_mirror_resync_required", "payload": {"actor_ref": "actor:a"}}, None)
    assert _send(encoder, _message(3, revision=3))["payload"]["delivery_kind"] == "snapshot"
    encoder.drop_actor("actor:a")
    assert _send(encoder, _message(4, revision=4))["payload"]["delivery_kind"] == "snapshot"
    assert _send(encoder, _message(1, epoch=2))["payload"]["delivery_kind"] == "snapshot"
    encoder.sent(_message(5, revision=5), None)
    assert _send(encoder, _message(2, epoch=2, revision=2))["payload"]["base_facade_revision"] == "facade:1"
    encoder.clear()
    assert _send(encoder, _message(1, epoch=3))["payload"]["delivery_kind"] == "snapshot"


def test_advisory_and_prediction_participate_in_shared_sequence_without_replacing_base():
    encoder = GameplayMirrorDeltaEncoder()
    _send(encoder, _message(1))
    for sequence, family in ((2, "government_drought_advisory_delivery"), (3, "gameplay_mirror_delivery")):
        message = {"message_type": family, "payload": {"connection_epoch": 1, "delivery_sequence": sequence,
                   "delivery_kind": "prediction", "actor_ref": "actor:a"}}
        assert _send(encoder, message) == message
    assert _send(encoder, _message(4, revision=4))["payload"]["base_facade_revision"] == "facade:1"


def test_base_storage_is_bounded_and_snapshot_decoder_rejects_tampering():
    encoder = GameplayMirrorDeltaEncoder()
    for index in range(161):
        _send(encoder, _message(index + 1, actor=f"actor:{index}"))
    assert len(encoder._bases) == 160
    assert "actor:0" not in encoder._bases
    body = _message(1)["payload"]["payload"]
    for field in ("groups", "canonical_snapshot_json", "snapshot_checksum"):
        changed = deepcopy(body)
        if field == "groups":
            changed[field]["resources"]["payload"]["current"] = 999
        else:
            changed[field] += "tampered"
        with pytest.raises((StateGroupSyncError, ValueError)):
            GameplayGodotMirrorSyncAdapter().snapshot_from_payload(changed)


def test_only_explicit_protocol_v2_delta_offer_enables_delta():
    from app.main import _select_gameplay_mirror_capability_profile
    from app.ws_protocol import GameplayMirrorCapabilityOffer
    assert not _select_gameplay_mirror_capability_profile(None).supports_delta
    for version, offered in ((1, True), (2, False), (2, True)):
        profile = _select_gameplay_mirror_capability_profile(GameplayMirrorCapabilityOffer(
            protocol_version=version, supports_snapshot=True, supports_delta=offered,
            projection_schemas=("gameplay_runtime_state.godot.v1",)))
        assert profile.supports_delta is (version >= 2 and offered)
