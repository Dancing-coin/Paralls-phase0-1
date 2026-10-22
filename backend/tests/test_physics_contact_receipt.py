import hashlib
import hmac
import importlib
import json

import pytest

from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from test_street_combat_authority import attempt


_SECRET = "test-physics-runtime-shared-secret-material"
_AUTHORITY = "physics-runtime:street-server"


def _api():
    assert importlib.util.find_spec("app.gameplay.physics_contact_receipt"), (
        "authenticated physics contact receipt verifier is missing"
    )
    return importlib.import_module("app.gameplay.physics_contact_receipt")


def _signed_receipt(action_attempt, *, secret=_SECRET, **changes):
    api = _api()
    fields = dict(
        authority_ref=_AUTHORITY,
        actor_ref=action_attempt.actor_ref,
        target_ref=action_attempt.target_refs[0],
        connection_epoch=action_attempt.connection_epoch,
        attempt_id=action_attempt.attempt_id,
        physics_tick=action_attempt.physics_tick,
        target_incarnation_ref="character:char_a@1",
        action_descriptor_digest=action_attempt.action_descriptor_digest,
        attempt_payload_digest=action_attempt.payload_digest,
        contact_source_digest="sha256:" + "a" * 64,
    ) | changes
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    fields["signature"] = hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()
    return api.PhysicsContactReceipt.model_validate(fields)


def test_physics_contact_receipt_verifies_authenticated_source_and_frozen_attempt_pins():
    action_attempt = attempt("receipt-valid", actor="street_bandage", target="char_a")
    receipt = _signed_receipt(action_attempt)
    verifier = _api().PhysicsContactReceiptVerifier({_AUTHORITY: _SECRET})

    verified = verifier.verify(
        receipt,
        attempt=action_attempt,
        target_incarnation_ref="character:char_a@1",
    )

    assert verified is not None
    assert verified.authority_ref == _AUTHORITY
    assert verified.receipt_digest.startswith("sha256:")
    assert verified.attempt_id == action_attempt.attempt_id


@pytest.mark.parametrize(
    "receipt_changes,target_incarnation_ref",
    [
        ({"connection_epoch": 99}, "character:char_a@1"),
        ({"physics_tick": 99}, "character:char_a@1"),
        ({"attempt_payload_digest": "sha256:" + "b" * 64}, "character:char_a@1"),
        ({"action_descriptor_digest": "sha256:" + "c" * 64}, "character:char_a@1"),
        ({}, "character:char_a@2"),
    ],
)
def test_physics_contact_receipt_rejects_mismatched_frozen_pins(
    receipt_changes, target_incarnation_ref
):
    action_attempt = attempt("receipt-mismatch", actor="street_bandage", target="char_a")
    receipt = _signed_receipt(action_attempt, **receipt_changes)
    verifier = _api().PhysicsContactReceiptVerifier({_AUTHORITY: _SECRET})

    assert verifier.verify(
        receipt,
        attempt=action_attempt,
        target_incarnation_ref=target_incarnation_ref,
    ) is None


def test_physics_contact_receipt_rejects_untrusted_authority_and_invalid_signature():
    action_attempt = attempt("receipt-untrusted", actor="street_bandage", target="char_a")
    receipt = _signed_receipt(action_attempt)

    api = _api()
    assert api.PhysicsContactReceiptVerifier({}).verify(
        receipt, attempt=action_attempt, target_incarnation_ref="character:char_a@1"
    ) is None

    invalid_signature = receipt.model_copy(update={"signature": "0" * 64})
    assert api.PhysicsContactReceiptVerifier({_AUTHORITY: _SECRET}).verify(
        invalid_signature,
        attempt=action_attempt,
        target_incarnation_ref="character:char_a@1",
    ) is None


def test_physics_contact_receipt_rejects_malformed_source_digest():
    action_attempt = attempt("receipt-digest", actor="street_bandage", target="char_a")

    with pytest.raises(ValueError):
        _signed_receipt(action_attempt, contact_source_digest="client-contact")


def test_physics_contact_receipt_authority_persists_once_and_replays_exact_receipt(tmp_path):
    api = _api()
    action_attempt = attempt("receipt-durable", actor="street_bandage", target="char_a")
    receipt = _signed_receipt(action_attempt)
    path = tmp_path / "physics-contact.db"
    store = DurableGameplayEventStore(path)
    authority = api.PhysicsContactReceiptAuthority(
        store=store,
        verifier=api.PhysicsContactReceiptVerifier({_AUTHORITY: _SECRET}),
    )

    first = authority.record(
        receipt, attempt=action_attempt, target_incarnation_ref="character:char_a@1"
    )
    replay = authority.record(
        receipt, attempt=action_attempt, target_incarnation_ref="character:char_a@1"
    )

    assert first.committed is True
    assert replay.committed is True
    assert replay.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == 1
    store.close()

    reopened = DurableGameplayEventStore(path)
    recovered = api.PhysicsContactReceiptAuthority(
        store=reopened,
        verifier=api.PhysicsContactReceiptVerifier({_AUTHORITY: _SECRET}),
    ).receipt_for_attempt(action_attempt)
    assert recovered == receipt
    assert len(reopened.read_events()) == 1
    reopened.close()


def test_physics_contact_receipt_authority_rejects_changed_or_unauthenticated_attempt_without_writes():
    api = _api()
    action_attempt = attempt("receipt-conflict", actor="street_bandage", target="char_a")
    store = GameplayEventStore()
    verifier = api.PhysicsContactReceiptVerifier({_AUTHORITY: _SECRET})
    authority = api.PhysicsContactReceiptAuthority(store=store, verifier=verifier)
    original = _signed_receipt(action_attempt)
    changed = _signed_receipt(
        action_attempt, contact_source_digest="sha256:" + "b" * 64
    )

    assert authority.record(
        original, attempt=action_attempt, target_incarnation_ref="character:char_a@1"
    ).committed is True
    conflict = authority.record(
        changed, attempt=action_attempt, target_incarnation_ref="character:char_a@1"
    )
    unauthenticated = api.PhysicsContactReceiptAuthority(
        store=store, verifier=api.PhysicsContactReceiptVerifier({})
    ).record(original, attempt=action_attempt, target_incarnation_ref="character:char_a@1")

    assert conflict.committed is False
    assert conflict.failure.error_code == "contact_attempt_receipt_conflict"
    assert unauthenticated.committed is False
    assert unauthenticated.failure.error_code == "contact_receipt_unverified"
    assert len(store.read_events()) == 1
