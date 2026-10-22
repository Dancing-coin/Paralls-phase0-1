"""Combat owner receipts and their pinned source cut in common replay."""
from copy import deepcopy
import hashlib
import hmac

import pytest

from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.physics_contact_receipt import (
    PhysicsContactReceipt,
    PhysicsContactReceiptAuthority,
    PhysicsContactReceiptVerifier,
)
from app.gameplay.combat_durable_adapter import DurableEmbodiedCombatAdapter
from app.world_runtime import replay_participants
from test_combat_settlement_threat_consumer import _attempt, _begin_encounter, _owner, _sources


def _signed_contact(attempt, target_incarnation_ref):
    secret = "test-physics-authority-secret"
    receipt = PhysicsContactReceipt(
        authority_ref="physics:test-runtime",
        actor_ref=attempt.actor_ref,
        target_ref=attempt.target_refs[0],
        connection_epoch=attempt.connection_epoch,
        attempt_id=attempt.attempt_id,
        physics_tick=attempt.physics_tick,
        target_incarnation_ref=target_incarnation_ref,
        action_descriptor_digest=attempt.action_descriptor_digest,
        attempt_payload_digest=attempt.payload_digest,
        contact_source_digest="sha256:" + "a" * 64,
        signature="0" * 64,
    )
    return receipt.model_copy(update={
        "signature": hmac.new(secret.encode(), receipt.canonical_bytes(), hashlib.sha256).hexdigest()
    }), secret


def _validate(store, saved, **kwargs):
    return replay_participants._validate_combat_participant(store, saved, **kwargs)


def test_empty_combat_participant_is_explicit_read_only():
    store = GameplayEventStore()
    before = store.export_snapshot()

    saved = replay_participants._combat_participant(store)

    assert saved["event_refs"] == []
    assert saved["source_refs"] == []
    _validate(store, saved)
    assert store.export_snapshot() == before


def test_combat_participant_captures_owner_receipts_sources_and_contact(tmp_path):
    path = tmp_path / "combat-replay.sqlite3"
    store = DurableGameplayEventStore(path)
    source = _sources(store)
    owner = _owner(store)
    attempt = _attempt("replay")
    contact, secret = _signed_contact(attempt, source.target_incarnation_ref)
    contact_owner = PhysicsContactReceiptAuthority(
        store=store,
        verifier=PhysicsContactReceiptVerifier({contact.authority_ref: secret}),
    )
    assert contact_owner.record(
        contact, attempt=attempt, target_incarnation_ref=source.target_incarnation_ref
    ).committed
    durable = DurableEmbodiedCombatAdapter(authority=owner, store=store)
    owner_receipt = owner.settle_street_combat(attempt)
    assert owner_receipt.outcome == "committed"
    assert _begin_encounter(store, source, attempt, owner_receipt).committed
    settled = durable.record_committed_settlement(
        attempt, authority_result=owner_receipt, source=source,
        command_id="combat:replay", idempotency_key="combat:replay", contact_receipt=contact,
    )
    assert settled.append_result is not None and settled.append_result.committed
    assert durable.consume_committed_hit(
        attempt, source=source, command_id="threat:replay", idempotency_key="threat:replay"
    ).committed

    saved = replay_participants._combat_participant(store)
    assert {row["principal_ref"] for row in saved["event_refs"]} >= {
        "authority:combat:physics-contact-receipt",
        "authority:combat:faction-relation",
        "authority:combat:encounter",
        "authority:embodied:street-combat-settlement",
        "authority:combat:threat-relation",
        "authority:embodied:street-owner",
    }
    assert all(row["receipt_digest"] and row["transaction_digest"] for row in saved["event_refs"])
    assert any(row["event_id"] == source.faction_source_event_id for row in saved["source_refs"])
    assert secret not in repr(saved)
    _validate(store, saved)
    store.close()

    reopened = DurableGameplayEventStore(path)
    try:
        assert replay_participants._combat_participant(reopened) == saved
        _validate(reopened, saved)
    finally:
        reopened.close()


def test_scoped_checkpoint_and_tail_capture_combat_owner_manifest(tmp_path):
    from app.world_runtime.replay_checkpoint import (
        capture_scoped_checkpoint,
        capture_scoped_tail,
    )

    store = DurableGameplayEventStore(tmp_path / "combat-scoped-replay.sqlite3")
    source = _sources(store)
    owner = _owner(store)
    attempt = _attempt("scoped-tail")
    owner_receipt = owner.settle_street_combat(attempt)
    assert owner_receipt.outcome == "committed"
    assert _begin_encounter(store, source, attempt, owner_receipt).committed

    def participants():
        return dict(
            schema_version=1,
            versions={
                "participant_manifest": 1,
                "batch_input": 1,
                "batch_operation": 1,
                "population_recovery": 1,
                "status_events": 1,
                "migration_events": 1,
                "combat": 1,
            },
            timeline={},
            profile={},
            mapping={},
            confirmed_tick=0,
            window_ticks=1,
            owner_revisions={},
            batches={"batch:combat": {}},
            external_dependencies={},
            random_context={},
            population={"schema_version": 1},
            status={"schema_version": 1},
            migration={"schema_version": 1},
            combat=replay_participants._combat_participant(store),
        )

    cut = capture_scoped_checkpoint(
        store=store,
        checkpoint_ref="replay:combat-scoped",
        batch_refs=("batch:combat",),
        participants=participants,
    )
    assert cut.status == "consistent", cut.diagnostics
    assert {row["event_type"] for row in cut.checkpoint.state["participants"]["combat"]["event_refs"]} == {
        "gameplay.combat.encounter_begun",
        "gameplay.combat.faction_relation_recorded",
        "gameplay.embodied.street_settled@1",
    }

    contact, secret = _signed_contact(attempt, source.target_incarnation_ref)
    contact_owner = PhysicsContactReceiptAuthority(
        store=store,
        verifier=PhysicsContactReceiptVerifier({contact.authority_ref: secret}),
    )
    assert contact_owner.record(
        contact, attempt=attempt, target_incarnation_ref=source.target_incarnation_ref
    ).committed
    durable = DurableEmbodiedCombatAdapter(authority=owner, store=store)
    settled = durable.record_committed_settlement(
        attempt,
        authority_result=owner_receipt,
        source=source,
        command_id="combat:scoped-tail",
        idempotency_key="combat:scoped-tail",
        contact_receipt=contact,
    )
    assert settled.append_result is not None and settled.append_result.committed
    assert durable.consume_committed_hit(
        attempt,
        source=source,
        command_id="threat:scoped-tail",
        idempotency_key="threat:scoped-tail",
    ).committed

    tail = capture_scoped_tail(store=store, checkpoint_ref="replay:combat-scoped", participants=participants)
    assert tail.status == "verified", tail.diagnostics
    assert {row["event_type"] for row in tail.payload["participants"]["combat"]["event_refs"]} >= {
        "gameplay.combat.physics_contact_receipt_recorded",
        "gameplay.combat.embodied_settlement_recorded",
        "gameplay.combat.threat_relation_recorded",
    }
    assert {event["event_type"] for event in tail.payload["events"]} >= {
        "gameplay.combat.physics_contact_receipt_recorded",
        "gameplay.combat.embodied_settlement_recorded",
        "gameplay.combat.threat_relation_recorded",
    }
    store.close()


@pytest.mark.parametrize("fault", ["event", "receipt", "source", "omitted"])
def test_combat_participant_rejects_tampering_without_writes(tmp_path, fault):
    store = DurableGameplayEventStore(tmp_path / f"combat-replay-{fault}.sqlite3")
    source = _sources(store)
    owner = _owner(store)
    attempt = _attempt(f"tamper-{fault}")
    durable = DurableEmbodiedCombatAdapter(authority=owner, store=store)
    owner_receipt = owner.settle_street_combat(attempt)
    assert owner_receipt.outcome == "committed"
    assert _begin_encounter(store, source, attempt, owner_receipt).committed
    settled = durable.record_committed_settlement(
        attempt, authority_result=owner_receipt, source=source,
        command_id=f"combat:{fault}", idempotency_key=f"combat:{fault}"
    )
    assert settled.append_result is not None and settled.append_result.committed
    assert durable.consume_committed_hit(
        attempt, source=source, command_id=f"threat:{fault}", idempotency_key=f"threat:{fault}"
    ).committed
    saved = replay_participants._combat_participant(store)
    bad = deepcopy(saved)
    if fault == "event":
        bad["event_refs"][0]["event_digest"] = "forged"
    elif fault == "receipt":
        bad["event_refs"][0]["receipt_digest"] = "forged"
    elif fault == "source":
        bad["source_refs"][0]["transaction_digest"] = "forged"
    else:
        bad = None
    before = store.export_snapshot()

    with pytest.raises(ValueError):
        _validate(store, bad)

    assert store.export_snapshot() == before
    store.close()


def test_combat_participant_historical_cut_excludes_later_owners(tmp_path):
    store = DurableGameplayEventStore(tmp_path / "combat-replay-cut.sqlite3")
    source = _sources(store)
    cut = store.get_last_global_sequence()
    first = replay_participants._combat_participant(store, boundary_sequence=cut)
    owner = _owner(store)
    attempt = _attempt("historical")
    durable = DurableEmbodiedCombatAdapter(authority=owner, store=store)
    owner_receipt = owner.settle_street_combat(attempt)
    assert owner_receipt.outcome == "committed"

    assert replay_participants._combat_participant(store, boundary_sequence=cut) == first
    _validate(store, first, boundary_sequence=cut)
    store.close()


def test_common_manifest_admits_current_combat_participant_and_legacy_absence():
    from app.world_runtime.replay_checkpoint import _manifest

    value = dict(schema_version=1,
        versions={"participant_manifest": 1, "batch_input": 1, "batch_operation": 1,
            "population_recovery": 1, "status_events": 1, "migration_events": 1,
            "combat": 1},
        batches={}, population={"schema_version": 1}, status={"schema_version": 1},
        migration={"schema_version": 1}, external_dependencies={}, random_context={},
        combat=replay_participants._combat_participant(GameplayEventStore()))

    assert _manifest(value, ()) == value

    legacy = deepcopy(value)
    legacy["versions"].pop("combat")
    legacy.pop("combat")
    assert _manifest(legacy, ()) == legacy
