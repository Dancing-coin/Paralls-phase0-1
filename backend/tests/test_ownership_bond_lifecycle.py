from __future__ import annotations

from decimal import Decimal

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.ownership_runtime import OwnershipAuthorityService, OwnershipProjector, OwnershipRuntimeError
from app.models.fact_type import FACT_TYPE_REGISTRY


STREAM = "gameplay:ownership"
TARGET = "asset:observatory"


def append_source_event(store):
    store.append_batch({
        "transaction_id": "tx:source",
        "command_id": "cmd:source",
        "expected_stream_revisions": {"gameplay:test:sources": 0},
        "events": [{
            "event_id": "evt:source",
            "event_type": "gameplay.test.source_recorded",
            "schema_version": 1,
            "stream_id": "gameplay:test:sources",
            "stream_revision": 0,
            "global_sequence": 0,
            "transaction_id": "tx:source",
            "command_id": "cmd:source",
            "causation_id": "evt:seed",
            "correlation_id": "corr:source",
            "visibility_policy": "authority_only",
            "payload": {},
        }],
        "idempotency_record": {
            "principal_ref": "actor:test.source",
            "idempotency_key": "source",
            "payload_digest": "sha256:test-source",
        },
        "outbox_entries": [],
        "result_digest": "sha256:test-source",
        "projection_refresh_hints": [],
    })


def command(name, expected_revision):
    return {
        "command_id": f"cmd:{name}",
        "idempotency_key": name,
        "causation_id": "evt:source",
        "correlation_id": "corr:bonds",
        "expected_ownership_revision": expected_revision,
        "world_tick": 0,
    }


def grant(ref, revision, **changes):
    return command(ref, revision) | {
        "bond_ref": f"bond:{ref}",
        "idempotency_key": f"bond:{ref}",
        "subject_ref": "actor:alice",
        "target_ref": TARGET,
        "bond_type": "custody",
        "scope": "region:north",
        "term_expires_at": None,
        "source_event_ref": "evt:source",
        "attributes": {"capacity": "10.0"},
    } | changes


def test_scoped_bonds_coexist_and_do_not_grant_legacy_title():
    store = GameplayEventStore()
    append_source_event(store)
    service = OwnershipAuthorityService(store=store)
    args = grant("north", 0, term_expires_at=10)
    wrong_key_store = GameplayEventStore()
    with pytest.raises(OwnershipRuntimeError, match="^ownership_bond_idempotency_invalid$"):
        OwnershipAuthorityService(store=wrong_key_store).grant_bond(**(args | {"idempotency_key": "other"}))
    assert wrong_key_store.read_events() == []
    first = service.grant_bond(**args)
    assert first.committed
    assert service.grant_bond(**grant("south", 1, scope="region:south")).committed
    assert service.grant_bond(**grant("title", 2, bond_type="ownership", attributes={"share": "1.0"})).committed
    bond_grants = [
        event
        for event in store.read_events()
        if event.event_type == "gameplay.ownership.bond_granted"
    ]
    assert "term_expires_at" in bond_grants[0].payload
    assert "term_expires_at" not in bond_grants[1].payload
    projection = OwnershipProjector().rebuild(store.read_events())
    north = projection.active_bonds(TARGET, "custody", "region:north", world_tick=9)
    assert tuple(bond.bond_ref for bond in north) == ("bond:north",)
    assert north[0].attributes == {"capacity": "10.0"}
    with pytest.raises(TypeError):
        north[0].attributes["capacity"] = "20.0"
    assert projection.active_bonds(TARGET, "custody", "region:north", world_tick=10) == ()
    assert projection.active_bonds(TARGET, "custody", "region:elsewhere", world_tick=0) == ()
    assert projection.active_right_by_asset == {}
    assert projection.rights == {}
    assert projection.source_revision_vector == {STREAM: 3}
    changed_events = list(store.read_events())
    grant_index = next(
        index
        for index, event in enumerate(changed_events)
        if event.event_type == "gameplay.ownership.bond_granted"
        and event.payload["bond_ref"] == "bond:north"
    )
    changed_payload = dict(changed_events[grant_index].payload)
    changed_payload["attributes"] = {"capacity": "11.0"}
    changed_events[grant_index] = changed_events[grant_index].model_copy(
        update={"payload": changed_payload}
    )
    changed_projection = OwnershipProjector().rebuild(changed_events)
    assert changed_projection.source_revision_vector == projection.source_revision_vector
    assert changed_projection.projection_revision != projection.projection_revision

    later_replay = service.grant_bond(**(args | {"world_tick": 100}))
    assert later_replay == first.model_copy(update={"idempotency_status": "duplicate_replayed"})
    renewed = service.grant_bond(**grant(
        "north-renewed", 3, term_expires_at=20, world_tick=10,
    ))
    assert renewed.committed and len(renewed.committed_event_ids) == 2
    assert [event.event_type for event in store.read_events()[-2:]] == [
        "gameplay.ownership.bond_expired",
        "gameplay.ownership.bond_granted",
    ]
    assert OwnershipProjector().rebuild(store.read_events()).bonds["bond:north"].status == "expired"
    assert OwnershipProjector().rebuild(store.read_events()).active_bonds(
        TARGET, "custody", "region:north", world_tick=10,
    )[0].bond_ref == "bond:north-renewed"
    assert service.grant_bond(**args) == first.model_copy(update={"idempotency_status": "duplicate_replayed"})

    before = store.export_snapshot()
    with pytest.raises(OwnershipRuntimeError, match="^idempotency_key_reused$"):
        service.grant_bond(**(args | {"scope": "region:elsewhere"}))
    with pytest.raises(OwnershipRuntimeError, match="^ownership_bond_conflict$"):
        service.grant_bond(**grant("conflict", 5))
    with pytest.raises(OwnershipRuntimeError, match="^ownership_bond_attributes_invalid$"):
        service.grant_bond(**grant(
            "attributes", 5, attributes={f"value_{index}": index for index in range(9)},
        ))
    with pytest.raises(OwnershipRuntimeError, match="^ownership_bond_attributes_invalid$"):
        service.grant_bond(**grant("attributes-shape", 5, attributes=[]))
    with pytest.raises(OwnershipRuntimeError, match="^ownership_bond_term_invalid$"):
        service.grant_bond(**grant("term", 5, term_expires_at=True))
    with pytest.raises(OwnershipRuntimeError, match="^revision_conflict$"):
        service.grant_bond(**grant("stale", 4, target_ref="item:other"))
    assert store.export_snapshot() == before


def test_bond_attributes_reject_keys_outside_the_type_contract_without_write():
    store = GameplayEventStore()
    append_source_event(store)
    service = OwnershipAuthorityService(store=store)
    before = store.export_snapshot()

    with pytest.raises(OwnershipRuntimeError, match="^ownership_bond_attributes_invalid$"):
        service.grant_bond(**grant(
            "extension-key", 0, attributes={"outstanding_amount": 5},
        ))

    assert store.export_snapshot() == before


def test_bond_projection_preserves_legacy_extension_attributes():
    store = GameplayEventStore()
    append_source_event(store)
    service = OwnershipAuthorityService(store=store)
    assert service.grant_bond(**grant("legacy-extension", 0)).committed

    events = list(store.read_events())
    grant_index = next(
        index for index, event in enumerate(events)
        if event.event_type == "gameplay.ownership.bond_granted"
    )
    payload = dict(events[grant_index].payload)
    payload["attributes"] = {"outstanding_amount": 5}
    events[grant_index] = events[grant_index].model_copy(update={"payload": payload})

    projection = OwnershipProjector().rebuild(events)

    assert projection.bonds["bond:legacy-extension"].attributes == {
        "outstanding_amount": 5,
    }


def test_bond_decimal_attributes_round_trip_and_replay_deterministically():
    store = GameplayEventStore()
    append_source_event(store)
    service = OwnershipAuthorityService(store=store)
    args = grant(
        "decimal-attribute", 0,
        bond_type="obligation",
        attributes={"amount": Decimal("5.2500")},
    )

    committed = service.grant_bond(**args)
    replayed = service.grant_bond(**args)
    restored = GameplayEventStore.from_snapshot(store.export_snapshot())
    bond = OwnershipProjector().rebuild(restored.read_events()).bonds[
        "bond:decimal-attribute"
    ]

    assert committed.committed
    assert replayed.idempotency_status == "duplicate_replayed"
    assert bond.attributes == {"amount": "5.2500"}


def test_bond_lifecycle_rebuilds_all_history_after_snapshot_restore():
    store = GameplayEventStore()
    append_source_event(store)
    service = OwnershipAuthorityService(store=store)
    assert service.grant_initial_title(
        **{
            key: value
            for key, value in command("legacy", 0).items()
            if key not in {"expected_ownership_revision", "world_tick"}
        },
        asset_ref=TARGET,
        holder_ref="actor:legacy",
        right_id="right:legacy",
    ).committed
    assert service.grant_bond(**grant("north", 1, term_expires_at=10)).committed
    before = store.export_snapshot()
    with pytest.raises(OwnershipRuntimeError, match="^ownership_bond_not_due$"):
        service.expire_bond(**(command("early", 2) | {"world_tick": 9}), bond_ref="bond:north")
    with pytest.raises(OwnershipRuntimeError, match="^ownership_bond_ref_duplicate$"):
        service.transfer_bond(
            **command("reuse", 2), bond_ref="bond:north", new_bond_ref="bond:north",
            new_subject="actor:bob", source_event_ref="evt:source",
        )
    assert store.export_snapshot() == before

    assert service.transfer_bond(
        **command("transfer", 2), bond_ref="bond:north", new_bond_ref="bond:bob",
        new_subject="actor:bob", source_event_ref="evt:source",
    ).committed
    replace_args = command("supersede", 4) | {
        "old_bond_ref": "bond:bob",
        "new_bond_ref": "bond:replacement",
        "subject_ref": "actor:bob",
        "target_ref": TARGET,
        "bond_type": "custody",
        "scope": "region:north",
        "source_event_ref": "evt:source",
        "term_expires_at": 11,
        "attributes": {"capacity": "20.0"},
    }
    superseded = service.supersede_bond(**replace_args)
    assert superseded.committed and len(superseded.committed_event_ids) == 2
    assert service.expire_bond(
        **(command("expire", 6) | {"world_tick": 11}), bond_ref="bond:replacement",
    ).committed
    assert service.grant_bond(**grant("revoke-me", 7, target_ref="item:evidence")).committed
    before_invalid_revoke = store.export_snapshot()
    with pytest.raises(OwnershipRuntimeError, match="^ownership_bond_revoke_reason_invalid$"):
        service.revoke_bond(
            **command("invalid-revoke", 8),
            bond_ref="bond:revoke-me",
            reason_code="unknown_reason",
        )
    assert store.export_snapshot() == before_invalid_revoke
    assert service.revoke_bond(
        **command("revoke", 8), bond_ref="bond:revoke-me", reason_code="party_requested",
    ).committed

    restored = GameplayEventStore.from_snapshot(store.export_snapshot())
    events = restored.read_events()
    projector = OwnershipProjector()
    full = projector.rebuild(events)
    for checkpoint in range(len(events) + 1):
        assert projector.rebuild(events, checkpoint_at=checkpoint) == full
    assert full.active_right_by_asset == {TARGET: "right:legacy"}
    assert full.bonds["bond:north"].status == "transferred"
    assert full.bonds["bond:bob"].status == "superseded"
    assert full.bonds["bond:bob"].attributes == {"capacity": "10.0"}
    assert full.bonds["bond:replacement"].status == "expired"
    assert full.bonds["bond:replacement"].attributes == {"capacity": "20.0"}
    assert full.bonds["bond:revoke-me"].status == "revoked"
    malformed_events = list(events)
    revoke_index = next(
        index
        for index, event in enumerate(malformed_events)
        if event.event_type == "gameplay.ownership.bond_revoked"
    )
    malformed_payload = dict(malformed_events[revoke_index].payload)
    malformed_payload["reason_code"] = "unknown_reason"
    malformed_events[revoke_index] = malformed_events[revoke_index].model_copy(
        update={"payload": malformed_payload}
    )
    with pytest.raises(OwnershipRuntimeError, match="^ownership_bond_revoke_reason_invalid$"):
        projector.rebuild(malformed_events)
    assert full.active_bonds(TARGET, "custody", "region:north", world_tick=11) == ()
    replay = OwnershipAuthorityService(store=restored).supersede_bond(**replace_args)
    assert replay == superseded.model_copy(update={"idempotency_status": "duplicate_replayed"})
    assert restored.export_snapshot() == store.export_snapshot()
    for event in events:
        if not event.event_type.startswith("gameplay.ownership."):
            continue
        event_type = FACT_TYPE_REGISTRY.from_event_type(event.event_type)
        assert event_type is not None and FACT_TYPE_REGISTRY.domain_for(event_type) == "ownership"
        assert event.visibility_policy == "authority_only"


def test_bond_grant_requires_a_stored_source_event_without_writes():
    store = GameplayEventStore()
    service = OwnershipAuthorityService(store=store)
    before = store.export_snapshot()

    with pytest.raises(OwnershipRuntimeError, match="^ownership_bond_source_missing$"):
        service.grant_bond(**grant("missing-source", 0))

    assert store.export_snapshot() == before


def test_bond_transfer_and_supersede_require_stored_source_events():
    store = GameplayEventStore()
    append_source_event(store)
    service = OwnershipAuthorityService(store=store)
    assert service.grant_bond(**grant("source-check", 0)).committed
    before = store.export_snapshot()

    with pytest.raises(OwnershipRuntimeError, match="^ownership_bond_source_missing$"):
        service.transfer_bond(
            **command("missing-transfer-source", 1),
            bond_ref="bond:source-check",
            new_bond_ref="bond:unwritten-transfer",
            new_subject="actor:bob",
            source_event_ref="evt:missing",
        )
    with pytest.raises(OwnershipRuntimeError, match="^ownership_bond_source_missing$"):
        service.supersede_bond(
            **command("missing-supersede-source", 1),
            old_bond_ref="bond:source-check",
            new_bond_ref="bond:unwritten-supersede",
            subject_ref="actor:alice",
            target_ref=TARGET,
            bond_type="custody",
            scope="region:north",
            term_expires_at=None,
            source_event_ref="evt:missing",
        )

    assert store.export_snapshot() == before
