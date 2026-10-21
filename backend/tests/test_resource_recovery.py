import json
import hashlib
import pytest
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.models import GameplayOutboxEntry
from app.gameplay.resource_body_runtime import ResourceBodyRuntimeProjector
from app.gameplay.resource_recovery import ResourceRecoveryAuthorityService
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch
from app.world_runtime.temporal_contracts import TemporalAuthorization


def _pins(tick=20):
    base = {"timeline_id": "timeline", "sampled_at": tick, "received_at": tick,
            "input_cutoff": tick, "confirmation_boundary": tick,
            "temporal_authorization_issuer_ref": "world_runtime.population_cadence:world", "late_input_policy_ref": "reject_after_cutoff",
            "ordering_policy_ref": "source_revision_then_event_ref", "temporal_authorization_valid_until": tick}
    grant = TemporalAuthorization(authorization_ref="authorization:resource", revision="v1", issuer_ref="world_runtime.population_cadence:world",
        timeline_id="timeline", participant_scope=("actor_gameplay.resource_domain",), input_cutoff=tick,
        confirmation_boundary=tick, late_input_policy_ref="reject_after_cutoff",
        ordering_policy_ref="source_revision_then_event_ref", valid_until=tick)
    base["temporal_authorizations"] = json.dumps({"resource": {**grant.payload(), "digest": grant.digest}}, sort_keys=True, separators=(",", ":"))
    inventory = TemporalAuthorization(authorization_ref="authorization:inventory", revision="v1", issuer_ref="world_runtime.population_cadence:world",
        timeline_id="timeline", participant_scope=("actor_gameplay.inventory_domain",), input_cutoff=tick,
        confirmation_boundary=tick, late_input_policy_ref="reject_after_cutoff", ordering_policy_ref="source_revision_then_event_ref", valid_until=tick)
    base.update(temporal_authorization_ref=inventory.authorization_ref, temporal_authorization_revision=inventory.revision,
        settlement_participant_scope="actor_gameplay.inventory_domain", temporal_authorization_digest=inventory.digest)
    return base


def _append(store, stream, specs, key, principal="test"):
    batch = build_multi_stream_atomic_event_batch(
        command_id=f"cmd:{key}", principal_ref=principal,
        expected_revisions={stream: store.get_stream_head(stream)}, event_specs={stream: specs},
        idempotency_key=key, causation_id=f"cause:{key}", correlation_id=f"corr:{key}",
        event_visibility_policies={stream: ["authority_only"] * len(specs)},
    )
    return store.append_batch(batch)


def _cadence(store, tick=20):
    record = {"cadence": {"cadence_id": f"cadence:world:{tick}", "world_ref": "world", "window_end": tick}, "time_pins": _pins(tick)}
    record["record_digest"] = "sha256:" + hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch
    batch = build_multi_stream_atomic_event_batch(command_id=f"population-runtime:cadence:world:{tick}", principal_ref="world_runtime.cadence",
        expected_revisions={"population-cadence:world": store.get_stream_head("population-cadence:world")}, event_specs={"population-cadence:world": [("population.cadence.admitted", record)]},
        idempotency_key=f"population-runtime:cadence:world:{tick}", causation_id="c", correlation_id="c")
    event = batch.events[0]
    batch.outbox_entries.append(GameplayOutboxEntry(outbox_id=f"outbox:cadence:{tick}", transaction_id=batch.transaction_id, event_id=event.event_id,
        global_sequence=0, topic="population_cadence_event", audience="broadcast", payload_projection={}))
    result = store.append_batch(batch)
    assert result.committed
    store.mark_outbox_delivered(f"outbox:cadence:{tick}")
    return result


def _store():
    store = GameplayEventStore()
    _cadence(store)
    _append(store, "gameplay:resources:char", [("gameplay.resource.materialized", {
        "actor_ref": "char", "resource_id": "core.stamina", "minimum": 0, "maximum": 10,
        "current": 2, "definition_version": "v1", "materialized_world_tick": 0, "world_ref": "world", "timeline_ref": "timeline",
        "recovery_amount": 3, "recovery_period_world_ticks": 5,
    }), ("gameplay.resource.materialized", {
        "actor_ref": "char", "resource_id": "core.mana", "minimum": 0, "maximum": 10,
        "current": 10, "definition_version": "v1", "materialized_world_tick": 0, "world_ref": "world", "timeline_ref": "timeline",
        "recovery_amount": 2, "recovery_period_world_ticks": 5,
    })], "materialize")
    return store


def test_recovery_rejects_revocation_racing_final_append(monkeypatch):
    store = _store()
    append = store.append_batch

    def revoke_before_commit(batch):
        if batch.idempotency_record.principal_ref == "resource_recovery_authority":
            cadence = store.read_stream("population-cadence:world")[0]
            revocation = build_multi_stream_atomic_event_batch(
                command_id="race:revoke", principal_ref="world_admin",
                expected_revisions={"population-cadence-revocation:world": 0},
                event_specs={"population-cadence-revocation:world": [
                    ("population.cadence.revoked", {"source_cadence_event_id": cadence.event_id})
                ]}, idempotency_key="race:revoke", causation_id="race", correlation_id="race",
            )
            assert append(revocation).committed
        return append(batch)

    monkeypatch.setattr(store, "append_batch", revoke_before_commit)
    result = ResourceRecoveryAuthorityService(store=store).recover(
        actor_ref="char", world_ref="world", timeline_ref="timeline",
        confirmed_world_tick=20, idempotency_key="race:recovery", expected_revision=2,
    )
    assert not result.committed
    assert store.get_stream_head("gameplay:resources:char") == 2


def test_recovery_uses_confirmed_population_boundary_and_replays():
    store = _store()
    owner = ResourceRecoveryAuthorityService(store=store)
    result = owner.recover(actor_ref="char", world_ref="world", timeline_ref="timeline",
                           confirmed_world_tick=20, idempotency_key="r1", expected_revision=2)
    assert result.committed
    duplicate = owner.recover(actor_ref="char", world_ref="world", timeline_ref="timeline",
                              confirmed_world_tick=20, idempotency_key="r1", expected_revision=2)
    assert duplicate.idempotency_status == "duplicate_replayed"
    projection = ResourceBodyRuntimeProjector().rebuild_resources("char", store.read_stream("gameplay:resources:char"))
    assert projection.entries["core.stamina"].current == 10
    assert projection.entries["core.mana"].current == 10


def test_recovery_rejects_modifier_without_effective_time_without_writing():
    store = GameplayEventStore()
    _cadence(store)
    _append(store, "gameplay:resources:char", [("gameplay.resource.materialized", {
        "actor_ref": "char", "resource_id": "core.stamina", "minimum": 0, "maximum": 100,
        "current": 2, "definition_version": "v2", "materialized_world_tick": 0,
        "world_ref": "world", "timeline_ref": "timeline", "recovery_amount": 3,
        "recovery_period_world_ticks": 5, "resource_schema": "resource.v2",
        "capacity": 100, "base_capacity": 100, "locked": 0, "debt": 0, "debt_ceiling": 0,
        "modifier_ledger": [], "modifier_ledger_digest": "sha256:" + hashlib.sha256(b"[]").hexdigest(),
    }), ("gameplay.resource.modifier_attached", {"actor_ref": "char", "resource_id": "core.stamina",
        "modifier": {"modifier_ref": "mod:late", "operation": "recovery_delta", "amount": 5,
                     "source_event_id": "evt:late-source", "template_id": "recovery:late@1"}})], "late-modifier")
    before = store.export_snapshot()
    with pytest.raises(ValueError, match="resource_recovery_modifier_temporal_contract_required"):
        ResourceRecoveryAuthorityService(store=store).recover(
            actor_ref="char", world_ref="world", timeline_ref="timeline",
            confirmed_world_tick=20, idempotency_key="late-modifier-recover", expected_revision=2)
    assert store.export_snapshot() == before


def _recovery_store_with_modifier(*, modifier_events):
    store = GameplayEventStore()
    _cadence(store)
    _append(store, "gameplay:resources:char", [("gameplay.resource.materialized", {
        "actor_ref": "char", "resource_id": "core.stamina", "minimum": 0, "maximum": 100,
        "current": 2, "definition_version": "v2", "materialized_world_tick": 0,
        "world_ref": "world", "timeline_ref": "timeline", "recovery_amount": 3,
        "recovery_period_world_ticks": 5, "resource_schema": "resource.v2",
        "capacity": 100, "base_capacity": 100, "locked": 0, "debt": 0, "debt_ceiling": 0,
        "modifier_ledger": [], "modifier_ledger_digest": "sha256:" + hashlib.sha256(b"[]").hexdigest(),
    })], "materialize")
    _append(store, "gameplay:resources:char", modifier_events, "modifier-history")
    return store


def test_recovery_applies_modifier_only_to_periods_after_attach_tick():
    store = _recovery_store_with_modifier(modifier_events=[
        ("gameplay.resource.modifier_attached", {"actor_ref": "char", "resource_id": "core.stamina",
            "modifier": {"modifier_ref": "mod:late", "operation": "recovery_delta", "amount": 5,
                          "effective_world_tick": 15, "source_event_id": "evt:late", "template_id": "recovery:late@1"}}),
    ])
    result = ResourceRecoveryAuthorityService(store=store).recover(
        actor_ref="char", world_ref="world", timeline_ref="timeline", confirmed_world_tick=20,
        idempotency_key="segmented-attach", expected_revision=2)
    assert result.committed
    projection = ResourceBodyRuntimeProjector().rebuild_resources("char", store.read_stream("gameplay:resources:char"))
    assert projection.entries["core.stamina"].current == 24


def test_recovery_stops_modifier_at_detach_tick():
    modifier = {"modifier_ref": "mod:temporary", "operation": "recovery_delta", "amount": 5,
                "effective_world_tick": 10, "source_event_id": "evt:temporary", "template_id": "recovery:temporary@1"}
    store = _recovery_store_with_modifier(modifier_events=[
        ("gameplay.resource.modifier_attached", {"actor_ref": "char", "resource_id": "core.stamina", "modifier": modifier}),
        ("gameplay.resource.modifier_detached", {"actor_ref": "char", "resource_id": "core.stamina",
            "effective_world_tick": 15, "modifier": modifier}),
    ])
    result = ResourceRecoveryAuthorityService(store=store).recover(
        actor_ref="char", world_ref="world", timeline_ref="timeline", confirmed_world_tick=20,
        idempotency_key="segmented-detach", expected_revision=3)
    assert result.committed
    projection = ResourceBodyRuntimeProjector().rebuild_resources("char", store.read_stream("gameplay:resources:char"))
    assert projection.entries["core.stamina"].current == 19


def test_recovery_ignores_future_modifier_periods():
    store = _recovery_store_with_modifier(modifier_events=[
        ("gameplay.resource.modifier_attached", {"actor_ref": "char", "resource_id": "core.stamina",
            "modifier": {"modifier_ref": "mod:future", "operation": "recovery_delta", "amount": 5,
                          "effective_world_tick": 25, "source_event_id": "evt:future", "template_id": "recovery:future@1"}}),
    ])
    result = ResourceRecoveryAuthorityService(store=store).recover(
        actor_ref="char", world_ref="world", timeline_ref="timeline", confirmed_world_tick=20,
        idempotency_key="segmented-future", expected_revision=2)
    assert result.committed
    projection = ResourceBodyRuntimeProjector().rebuild_resources("char", store.read_stream("gameplay:resources:char"))
    assert projection.entries["core.stamina"].current == 14


def test_recovery_rejects_detach_without_effective_time_without_writing():
    modifier = {"modifier_ref": "mod:temporary", "operation": "recovery_delta", "amount": 5,
                "effective_world_tick": 10, "source_event_id": "evt:temporary", "template_id": "recovery:temporary@1"}
    store = _recovery_store_with_modifier(modifier_events=[
        ("gameplay.resource.modifier_attached", {"actor_ref": "char", "resource_id": "core.stamina", "modifier": modifier}),
        ("gameplay.resource.modifier_detached", {"actor_ref": "char", "resource_id": "core.stamina",
            "modifier": modifier, "effective_world_tick": None}),
    ])
    before = store.export_snapshot()
    with pytest.raises(ValueError, match="resource_recovery_modifier_temporal_contract_required"):
        ResourceRecoveryAuthorityService(store=store).recover(
            actor_ref="char", world_ref="world", timeline_ref="timeline",
            confirmed_world_tick=20, idempotency_key="segmented-bad-detach", expected_revision=3)
    assert store.export_snapshot() == before


@pytest.mark.parametrize("applied_through", [None, True, -1, 25])
def test_recovery_rejects_malformed_prior_recovery_boundary_without_writing(applied_through):
    store = _store()
    _append(store, "gameplay:resources:char", [("gameplay.resource.recovered", {
        "actor_ref": "char", "resource_id": "core.stamina", "delta": 1,
        "periods": 1, "applied_through_world_tick": applied_through,
        "confirmed_world_tick": 20, "world_ref": "world", "timeline_ref": "timeline",
    })], "malformed-prior-recovery")
    before = store.export_snapshot()
    with pytest.raises(ValueError, match="resource_recovery_history_invalid"):
        ResourceRecoveryAuthorityService(store=store).recover(
            actor_ref="char", world_ref="world", timeline_ref="timeline", confirmed_world_tick=20,
            idempotency_key=f"invalid-prior-{applied_through}", expected_revision=3)
    assert store.export_snapshot() == before


def test_recovery_rejects_modifier_detached_before_effective_attach_without_writing():
    modifier = {"modifier_ref": "mod:reversed", "operation": "recovery_delta", "amount": 5,
                "effective_world_tick": 20, "source_event_id": "evt:reversed", "template_id": "recovery:reversed@1"}
    store = _recovery_store_with_modifier(modifier_events=[
        ("gameplay.resource.modifier_attached", {"actor_ref": "char", "resource_id": "core.stamina", "modifier": modifier}),
        ("gameplay.resource.modifier_detached", {"actor_ref": "char", "resource_id": "core.stamina",
            "modifier": modifier, "effective_world_tick": 10}),
    ])
    before = store.export_snapshot()
    with pytest.raises(ValueError, match="resource_recovery_modifier_history_invalid"):
        ResourceRecoveryAuthorityService(store=store).recover(
            actor_ref="char", world_ref="world", timeline_ref="timeline", confirmed_world_tick=20,
            idempotency_key="reversed-modifier-history", expected_revision=3)
    assert store.export_snapshot() == before


def test_recovery_rejects_unconfirmed_or_changed_boundary_without_write():
    store = _store()
    owner = ResourceRecoveryAuthorityService(store=store)
    before = store.get_stream_head("gameplay:resources:char")
    for tick in (19, 21):
        try:
            owner.recover(actor_ref="char", world_ref="world", timeline_ref="timeline",
                          confirmed_world_tick=tick, idempotency_key=f"bad-{tick}", expected_revision=before)
        except ValueError:
            pass
        else:
            raise AssertionError("unconfirmed boundary accepted")
    assert store.get_stream_head("gameplay:resources:char") == before


def test_recovery_requires_materialization_and_conflicting_revision():
    store = GameplayEventStore()
    _cadence(store)
    owner = ResourceRecoveryAuthorityService(store=store)
    try:
        owner.recover(actor_ref="char", world_ref="world", timeline_ref="timeline",
                      confirmed_world_tick=20, idempotency_key="x", expected_revision=0)
    except ValueError as exc:
        assert str(exc) == "resource_recovery_before_materialization"
    else:
        raise AssertionError("recovery before materialization accepted")


def test_recovery_rejects_tampered_population_record_and_materialization_scope():
    store = _store()
    bad = GameplayEventStore()
    _append(bad, "population-cadence:world", [("population.cadence.admitted", {"cadence": {"world_ref": "world", "window_end": 20}})], "bad")
    owner = ResourceRecoveryAuthorityService(store=store)
    try:
        ResourceRecoveryAuthorityService(store=bad).recover(actor_ref="char", world_ref="world", timeline_ref="timeline", confirmed_world_tick=20,
                      idempotency_key="tampered", expected_revision=2)
    except ValueError as exc:
        assert str(exc) in {"resource_recovery_population_record_tampered", "resource_recovery_population_record_digest_missing", "resource_recovery_temporal_boundary_mismatch"}
    else:
        raise AssertionError("tampered cadence accepted")


def test_changed_duplicate_is_rejected():
    store = _store()
    owner = ResourceRecoveryAuthorityService(store=store)
    owner.recover(actor_ref="char", world_ref="world", timeline_ref="timeline", confirmed_world_tick=20,
                  idempotency_key="same", expected_revision=2)
    try:
        owner.recover(actor_ref="char", world_ref="world", timeline_ref="timeline", confirmed_world_tick=19,
                      idempotency_key="same", expected_revision=4)
    except ValueError as exc:
        assert str(exc) == "idempotency_key_reused"
    else:
        raise AssertionError("changed duplicate accepted")


def test_wrong_materialization_scope_is_rejected():
    store = GameplayEventStore()
    _cadence(store)
    _append(store, "gameplay:resources:char", [("gameplay.resource.materialized", {
        "actor_ref": "char", "resource_id": "core.stamina", "minimum": 0, "maximum": 10,
        "current": 1, "definition_version": "v1", "materialized_world_tick": 0,
        "world_ref": "other-world", "timeline_ref": "timeline", "recovery_amount": 1,
        "recovery_period_world_ticks": 5,
    })], "materialize")
    try:
        ResourceRecoveryAuthorityService(store=store).recover(actor_ref="char", world_ref="world", timeline_ref="timeline",
            confirmed_world_tick=20, idempotency_key="scope", expected_revision=1)
    except ValueError as exc:
        assert str(exc) == "resource_recovery_materialization_scope_invalid"
    else:
        raise AssertionError("wrong materialization scope accepted")


def test_recovery_survives_durable_reopen_and_checkpoint_tail_matches(tmp_path):
    path = tmp_path / "resource-recovery.sqlite3"
    store = DurableGameplayEventStore(path)
    _cadence(store)
    _append(store, "gameplay:resources:char", [("gameplay.resource.materialized", {
        "actor_ref": "char", "resource_id": "core.stamina", "minimum": 0, "maximum": 20,
        "current": 1, "definition_version": "v1", "materialized_world_tick": 0, "world_ref": "world", "timeline_ref": "timeline",
        "recovery_amount": 2, "recovery_period_world_ticks": 5,
    })], "materialize")
    first = ResourceRecoveryAuthorityService(store=store).recover(
        actor_ref="char", world_ref="world", timeline_ref="timeline", confirmed_world_tick=20,
        idempotency_key="r-durable", expected_revision=1,
    )
    store.close()
    reopened = DurableGameplayEventStore(path)
    retry = ResourceRecoveryAuthorityService(store=reopened).recover(
        actor_ref="char", world_ref="world", timeline_ref="timeline", confirmed_world_tick=20,
        idempotency_key="r-durable", expected_revision=1,
    )
    assert retry.idempotency_status == "duplicate_replayed"
    events = reopened.read_stream("gameplay:resources:char")
    projector = ResourceBodyRuntimeProjector()
    full = projector.rebuild_resources("char", events)
    checkpointed = projector.rebuild_resources("char", events[1:], checkpoint=projector.rebuild_resources("char", events[:1]))
    assert checkpointed == full
    assert full.entries["core.stamina"].current == 9
    assert retry.committed_event_ids == first.committed_event_ids
    reopened.close()


@pytest.mark.parametrize("damage", ["refs", "second_payload", "missing_transaction", "result_digest"])
def test_recovery_duplicate_checks_entire_owner_transaction(monkeypatch, damage):
    store = _store()
    owner = ResourceRecoveryAuthorityService(store=store)
    args = dict(actor_ref="char", world_ref="world", timeline_ref="timeline",
                confirmed_world_tick=20, idempotency_key="complete-batch", expected_revision=2)
    receipt = owner.recover(**args)
    assert receipt.committed and len(receipt.committed_event_ids) == 2
    lookup = store.get_by_idempotency
    transaction = store.get_transaction
    event_lookup = store.get_event
    if damage == "refs":
        monkeypatch.setattr(store, "get_by_idempotency", lambda principal, key:
            receipt.model_copy(update={"committed_event_ids": receipt.committed_event_ids[:1]})
            if principal == "resource_recovery_authority" else lookup(principal, key))
    elif damage == "second_payload":
        second_id = receipt.committed_event_ids[1]
        def altered(event_id):
            event = event_lookup(event_id)
            return event.model_copy(update={"payload": {**event.payload, "delta": 999}}) if event_id == second_id else event
        monkeypatch.setattr(store, "get_event", altered)
    else:
        def altered_transaction(transaction_id):
            tx = transaction(transaction_id)
            if transaction_id != receipt.transaction_id:
                return tx
            return None if damage == "missing_transaction" else tx.model_copy(update={"result_digest": "sha256:" + "0" * 64})
        monkeypatch.setattr(store, "get_transaction", altered_transaction)
    before = store.export_snapshot()
    with pytest.raises(ValueError, match="resource_recovery_receipt_incomplete"):
        owner.recover(**args)
    assert store.export_snapshot() == before

