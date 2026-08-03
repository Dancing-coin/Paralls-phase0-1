from __future__ import annotations

import pytest

from app.gameplay.credential_runtime import CredentialAuthorityService, CredentialPresentationValidator, CredentialProjector, CredentialRuntimeError
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry, ItemDefinition
from app.gameplay.ownership_runtime import OwnershipAuthorityService, OwnershipProjector


ASSET = "land:observatory"
RIGHT = "right:observatory"


def _setup() -> tuple[GameplayEventStore, InventoryDefinitionRegistry, CredentialAuthorityService]:
    store = GameplayEventStore()
    OwnershipAuthorityService(store=store).grant_initial_title(command_id="cmd:title", asset_ref=ASSET, holder_ref="actor:alice", right_id=RIGHT, idempotency_key="title", causation_id="cause", correlation_id="corr")
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition("item:land-deed", "1", 0, 0))
    inventory = InventoryAuthorityService(store=store, registry=registry)
    inventory.create_container(command_id="cmd:alice-bag", actor_ref="actor:alice", spec=ContainerSpec("container:alice-bag", 1, 1, 2), idempotency_key="alice-bag", causation_id="cause", correlation_id="corr")
    for item_id in ("item:deed:1", "item:deed:2"):
        inventory.instantiate(command_id=f"cmd:{item_id}", actor_ref="actor:alice", item_id=item_id, definition_id="item:land-deed", quantity=1, container_id="container:alice-bag", idempotency_key=item_id, causation_id="cause", correlation_id="corr")
    return store, registry, CredentialAuthorityService(store=store, inventory_registry=registry)


def _issue(service: CredentialAuthorityService, *, command_id: str = "cmd:issue", credential_id: str = "credential:deed:1", item_ref: str = "item:deed:1", idempotency_key: str = "issue"):
    return service.issue_credential(
        command_id=command_id,
        credential_id=credential_id,
        credential_item_ref=item_ref,
        credential_holder_ref="actor:alice",
        right_id=RIGHT,
        credential_kind="deed",
        proves="evidence_only",
        issuer_ref="authority:land-registry",
        idempotency_key=idempotency_key,
        causation_id="cause",
        correlation_id="corr",
    )


def test_credential_is_replayable_evidence_not_title_truth() -> None:
    store, _, service = _setup()
    issued = _issue(service)
    assert issued.committed
    OwnershipAuthorityService(store=store).transfer_title(command_id="cmd:title-transfer", asset_ref=ASSET, right_id=RIGHT, from_holder_ref="actor:alice", to_holder_ref="actor:bob", idempotency_key="title-transfer", causation_id="cause", correlation_id="corr")
    credentials = CredentialProjector().rebuild(store.read_events())
    assert credentials.links["credential:deed:1"].status == "active"
    assert credentials.links["credential:deed:1"].credential_item_ref == "item:deed:1"
    assert OwnershipProjector().rebuild(store.read_events()).rights[RIGHT].holder_ref == "actor:bob"


def test_credential_records_issuance_holder_attestation_without_becoming_current_holder_truth() -> None:
    store, _, service = _setup()
    _issue(service)
    link = CredentialProjector().rebuild(store.read_events()).links["credential:deed:1"]
    assert link.issued_holder_ref == "actor:alice"
    assert link.issued_holder_inventory_revision > 0

    OwnershipAuthorityService(store=store).transfer_title(
        command_id="cmd:title-transfer",
        asset_ref=ASSET,
        right_id=RIGHT,
        from_holder_ref="actor:alice",
        to_holder_ref="actor:bob",
        idempotency_key="title-transfer",
        causation_id="cause",
        correlation_id="corr",
    )
    replayed = CredentialProjector().rebuild(store.read_events()).links["credential:deed:1"]
    assert replayed.issued_holder_ref == "actor:alice"
    assert OwnershipProjector().rebuild(store.read_events()).rights[RIGHT].holder_ref == "actor:bob"


def test_revoke_and_supersede_change_only_credential_link_state() -> None:
    store, _, service = _setup()
    _issue(service)
    superseded = service.supersede_credential(
        command_id="cmd:reissue",
        prior_credential_id="credential:deed:1",
        replacement_credential_id="credential:deed:2",
        replacement_item_ref="item:deed:2",
        replacement_holder_ref="actor:alice",
        issuer_ref="authority:land-registry",
        idempotency_key="reissue",
        causation_id="cause",
        correlation_id="corr",
    )
    assert superseded.committed
    links = CredentialProjector().rebuild(store.read_events()).links
    assert links["credential:deed:1"].status == "superseded"
    assert links["credential:deed:2"].status == "active"
    assert links["credential:deed:2"].issued_holder_ref == "actor:alice"
    assert links["credential:deed:2"].issued_holder_inventory_revision > 0
    assert OwnershipProjector().rebuild(store.read_events()).rights[RIGHT].holder_ref == "actor:alice"

    revoked = service.revoke_credential(command_id="cmd:revoke", credential_id="credential:deed:2", issuer_ref="authority:land-registry", reason="lost", idempotency_key="revoke", causation_id="cause", correlation_id="corr")
    assert revoked.committed
    assert CredentialProjector().rebuild(store.read_events()).links["credential:deed:2"].status == "revoked"


def test_unknown_right_rejects_without_event_and_retry_is_idempotent() -> None:
    store, _, service = _setup()
    before = store.read_events()
    with pytest.raises(CredentialRuntimeError, match="ownership_right_missing"):
        service.issue_credential(command_id="cmd:missing", credential_id="credential:missing", credential_item_ref="item:missing", credential_holder_ref="actor:alice", right_id="right:missing", credential_kind="deed", proves="evidence_only", issuer_ref="authority:land-registry", idempotency_key="missing", causation_id="cause", correlation_id="corr")
    assert store.read_events() == before
    first = _issue(service)
    replay = _issue(service)
    assert first.committed and replay.committed
    assert replay.idempotency_status == "duplicate_replayed"


def test_credential_presentation_requires_item_presence_and_right_holder() -> None:
    store, registry, service = _setup()
    _issue(service)
    validator = CredentialPresentationValidator(store=store, inventory_registry=registry)
    present = validator.verify_right_holder_presentation(credential_id="credential:deed:1", presenter_ref="actor:alice")
    assert present.authorized
    assert present.credential_present and present.presenter_is_right_holder

    OwnershipAuthorityService(store=store).transfer_title(command_id="cmd:transfer", asset_ref=ASSET, right_id=RIGHT, from_holder_ref="actor:alice", to_holder_ref="actor:bob", idempotency_key="transfer", causation_id="cause", correlation_id="corr")
    stale_holder = validator.verify_right_holder_presentation(credential_id="credential:deed:1", presenter_ref="actor:alice")
    assert stale_holder.credential_present
    assert not stale_holder.presenter_is_right_holder
    assert not stale_holder.authorized
    assert stale_holder.error_code == "ownership_right_holder_mismatch"

    absent = validator.verify_right_holder_presentation(credential_id="credential:deed:1", presenter_ref="actor:bob")
    assert absent.presenter_is_right_holder
    assert not absent.credential_present
    assert not absent.authorized
    assert absent.error_code == "credential_not_present"


def test_issuance_rejects_item_not_currently_held_without_link_event() -> None:
    store, _, service = _setup()
    before = store.read_events()
    with pytest.raises(CredentialRuntimeError, match="credential_item_not_present"):
        _issue(service, command_id="cmd:missing-item", credential_id="credential:missing-item", item_ref="item:missing", idempotency_key="missing-item")
    assert store.read_events() == before
