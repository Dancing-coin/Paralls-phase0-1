from __future__ import annotations

from pathlib import Path

import pytest

from app.gameplay.economy_runtime import (
    EconomyAuthorityService,
    PackageDeclaredNegotiatedExchangeIntentV1,
    PartyConsentAttestationV1,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import (
    ContainerSpec,
    InventoryAuthorityService,
    InventoryDefinitionRegistry,
    ItemDefinition,
)
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog
from test_inf1am_mill_flour_output_certification import _completed_case, _intent_for


PROVIDER = "organization:district-milling-cooperative"
RECEIVER = "org:mill:1"
FACILITY = "facility:mill-reinforcement:1"
ITEM = "item:industrial-facilities:flour@1"
RECIPE = "recipe:industrial-facilities:mill-flour@1"
OUTCOME = "outcome:industrial-facility-reinforced-mill-flour-output-purchase@1"
PROVIDER_CONTAINER = "container:district-milling-cooperative:mill-output"
RECEIVER_CONTAINER = "container:org:mill:1:stores"
MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "inf-2"
    / "package-industrial-facilities-v7-reinforced-mill-flour-output-purchase.manifest.json"
)


def _certified_source() -> tuple[GameplayEventStore, object]:
    store, authority, _started, finished = _completed_case()
    certified = authority.certify_mill_flour_output(_intent_for(finished))
    assert certified.committed, certified.failure
    return store, store.get_event(certified.committed_event_ids[0])


def _inventory_setup(
    store: GameplayEventStore,
) -> tuple[InventoryDefinitionRegistry, InventoryAuthorityService]:
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition(ITEM, "1", 1, 1))
    inventory = InventoryAuthorityService(store=store, registry=registry)
    for actor_ref, container_id in (
        (PROVIDER, PROVIDER_CONTAINER),
        (RECEIVER, RECEIVER_CONTAINER),
    ):
        created = inventory.create_container(
            command_id=f"inf2am:container:{actor_ref}",
            actor_ref=actor_ref,
            spec=ContainerSpec(container_id, 50, 50, 4),
            idempotency_key=f"inf2am:container:{actor_ref}",
            causation_id="cause:inf2am:bootstrap",
            correlation_id="corr:inf2am:bootstrap",
        )
        assert created.committed, created.failure
    return registry, inventory


def _economy_setup(
    *,
    store: GameplayEventStore,
    inventory_registry: InventoryDefinitionRegistry,
    inventory: InventoryAuthorityService,
) -> EconomyAuthorityService:
    manifest = GameplayPatchManifest.model_validate_json(MANIFEST.read_text(encoding="utf-8"))
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    registry.activate((manifest.patch_revision_id,))
    economy = EconomyAuthorityService(
        store=store,
        package_registry=registry,
        inventory_registry=inventory_registry,
        inventory_authority=inventory,
    )
    for account_id, owner_ref, balance in (
        ("account:inf2am:provider", PROVIDER, 0),
        ("account:inf2am:receiver", RECEIVER, 20),
    ):
        opened = economy.open_account(
            command_id=f"inf2am:account:{account_id}",
            account_id=account_id,
            owner_ref=owner_ref,
            currency_ref="currency:local",
            initial_balance=balance,
            idempotency_key=f"inf2am:account:{account_id}",
            causation_id="cause:inf2am:bootstrap",
            correlation_id="corr:inf2am:bootstrap",
        )
        assert opened.committed, opened.failure
    return economy


def _inventory_receipt_key(certification_event_id: str, certification_revision: int) -> str:
    return (
        "inventory:reinforced-mill-flour-output:"
        f"{certification_event_id}:{certification_revision}:v1"
    )


def _exchange_intent(
    *,
    proposal_digest: str = "proposal:inf2am:1",
    amount: int | None = None,
) -> PackageDeclaredNegotiatedExchangeIntentV1:
    return PackageDeclaredNegotiatedExchangeIntentV1(
        capability_ref="capability:package-declared-negotiated-exchange@1",
        outcome_ref=OUTCOME,
        proposal_digest=proposal_digest,
        provider_consent=PartyConsentAttestationV1(
            party_ref=PROVIDER,
            proposal_digest=proposal_digest,
        ),
        receiver_consent=PartyConsentAttestationV1(
            party_ref=RECEIVER,
            proposal_digest=proposal_digest,
        ),
        proposed_amount=amount,
        command_id=f"inf2am:{proposal_digest}",
        idempotency_key=(
            "package-negotiated-exchange:package:industrial-facilities:v7:"
            f"package_declared_negotiated_exchange@1:{proposal_digest}:v1"
        ),
        causation_id=f"cause:{proposal_digest}",
        correlation_id=f"corr:{proposal_digest}",
    )


def test_inf2am_freezes_exact_v7_manifest_for_reinforced_mill_flour_output_purchase() -> None:
    manifest = GameplayPatchManifest.model_validate_json(MANIFEST.read_text(encoding="utf-8"))

    assert manifest.manifest_schema_version == 2
    assert manifest.patch_revision_id == "package:industrial-facilities:v7"
    assert manifest.patch_version == "7.0.0"
    assert manifest.content_digest == manifest.expected_content_digest()
    assert len(manifest.economic_outcomes) == 1
    definition = manifest.economic_outcomes[0]
    assert definition.outcome_ref == OUTCOME
    assert definition.tradeable_ref == ITEM
    assert definition.source_evidence_mode == "inventory_custody@1"
    assert definition.source_evidence_kind == "inventory_custody@1"
    assert definition.price_policy.currency_ref == "currency:local"
    assert definition.price_policy.fixed_amount == 8
    contract = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:industrial-facility-reinforced-mill-flour-output-purchase@1",
        contract_kind="settlement",
    )
    assert contract.owner_ref == "actor_gameplay.economy_domain"
    assert contract.projection_scope == "authority_only"
    descriptor = next(
        item
        for item in GovernedAuthorityContractCatalog.descriptors()
        if item.descriptor_ref
        == "descriptor:industrial-facility-reinforced-mill-flour-output-purchase@1"
    )
    assert descriptor.capability_ref == "capability:package-declared-negotiated-exchange@1"
    assert descriptor.outcome_family_ref == OUTCOME


def test_inf2am_certified_project_inventory_receipt_drives_exact_authority_purchase() -> None:
    store, certification_event = _certified_source()
    inventory_registry, inventory = _inventory_setup(store)
    generic = inventory.record_output_receipt(
        command_id="inf2am:generic-output",
        actor_ref=PROVIDER,
        source_ref="source:generic-output",
        item_ref=ITEM,
        item_id="item:industrial-facilities:flour@generic",
        definition_id=ITEM,
        container_id=PROVIDER_CONTAINER,
        quantity=10,
        idempotency_key="inf2am:generic-output",
        causation_id="cause:inf2am:generic-output",
        correlation_id="corr:inf2am:generic-output",
    )
    assert generic.committed, generic.failure
    receipt = inventory.record_reinforced_mill_flour_output_receipt(
        certification_event_id=certification_event.event_id,
        expected_certification_revision=certification_event.stream_revision,
        expected_inventory_stream_revision=store.get_stream_head(
            f"gameplay:inventory:{PROVIDER}"
        ),
        command_id="inf2am:inventory-receipt",
        idempotency_key=_inventory_receipt_key(
            certification_event.event_id,
            certification_event.stream_revision,
        ),
        causation_id=certification_event.event_id,
        correlation_id="corr:inf2am:inventory-receipt",
    )
    assert receipt.committed, receipt.failure
    inventory_event = store.get_event(receipt.committed_event_ids[0])
    assert inventory_event.event_type == "gameplay.inventory.mill_flour_output_received@1"
    assert inventory_event.visibility_policy == "project"
    assert inventory_event.payload["provider_ref"] == PROVIDER
    assert inventory_event.payload["project_ref"] == "plot:mill-reinforcement:1"
    assert inventory_event.payload["facility_ref"] == FACILITY
    assert inventory_event.payload["recipe_ref"] == RECIPE
    assert inventory_event.payload["definition_id"] == ITEM
    assert inventory_event.payload["quantity"] == 10
    assert inventory_event.payload["container_id"] == PROVIDER_CONTAINER
    inventory_receipt = inventory.reinforced_mill_flour_output_receipt_for(
        result=receipt,
        scope="project",
    )
    assert inventory_receipt.committed_event_ids == tuple(receipt.committed_event_ids)

    economy = _economy_setup(
        store=store,
        inventory_registry=inventory_registry,
        inventory=inventory,
    )
    settled = economy.settle_package_declared_negotiated_exchange(_exchange_intent())

    assert settled.committed, settled.failure
    events = [store.get_event(event_id) for event_id in settled.committed_event_ids]
    assert {
        event.event_type for event in events
    } == {
        "gameplay.economy.account_debited",
        "gameplay.economy.account_credited",
        "gameplay.economy.package_declared_negotiated_exchange_settled",
        "gameplay.inventory.item_transferred_out",
        "gameplay.inventory.item_transferred_in",
    }
    settlement = next(
        event
        for event in events
        if event.event_type == "gameplay.economy.package_declared_negotiated_exchange_settled"
    )
    assert settlement.visibility_policy == "authority_only"
    assert settlement.payload["package_revision_id"] == "package:industrial-facilities:v7"
    assert settlement.payload["provider_ref"] == PROVIDER
    assert settlement.payload["receiver_ref"] == RECEIVER
    assert settlement.payload["amount_minor"] == 8
    assert settlement.payload["currency_ref"] == "currency:local"
    assert settlement.payload["source_event_ids"] == [inventory_event.event_id]
    full = economy.package_declared_negotiated_exchange_projection(scope="authority")
    tail = economy.package_declared_negotiated_exchange_projection(
        scope="authority",
        checkpoint_at=settled.global_sequence_range[-1],
    )
    assert full == tail


def test_inf2am_private_certification_is_zero_write_for_inventory_receipt() -> None:
    store, certification_event = _certified_source()
    _inventory_registry, inventory = _inventory_setup(store)
    store._events_by_id[certification_event.event_id] = certification_event.model_copy(
        update={"visibility_policy": "authority_only"},
        deep=True,
    )
    before = store.export_snapshot()

    rejected = inventory.record_reinforced_mill_flour_output_receipt(
        certification_event_id=certification_event.event_id,
        expected_certification_revision=certification_event.stream_revision,
        expected_inventory_stream_revision=store.get_stream_head(
            f"gameplay:inventory:{PROVIDER}"
        ),
        command_id="inf2am:inventory-private",
        idempotency_key=_inventory_receipt_key(
            certification_event.event_id,
            certification_event.stream_revision,
        ),
        causation_id=certification_event.event_id,
        correlation_id="corr:inf2am:inventory-private",
    )

    assert not rejected.committed
    assert rejected.failure is not None
    assert rejected.failure.error_code == "inventory_mill_flour_output_source_invalid"
    assert store.export_snapshot() == before


def test_inf2am_duplicate_and_price_conflicts_are_bounded() -> None:
    store, certification_event = _certified_source()
    inventory_registry, inventory = _inventory_setup(store)
    receipt = inventory.record_reinforced_mill_flour_output_receipt(
        certification_event_id=certification_event.event_id,
        expected_certification_revision=certification_event.stream_revision,
        expected_inventory_stream_revision=store.get_stream_head(
            f"gameplay:inventory:{PROVIDER}"
        ),
        command_id="inf2am:inventory-receipt",
        idempotency_key=_inventory_receipt_key(
            certification_event.event_id,
            certification_event.stream_revision,
        ),
        causation_id=certification_event.event_id,
        correlation_id="corr:inf2am:inventory-receipt",
    )
    assert receipt.committed, receipt.failure
    economy = _economy_setup(
        store=store,
        inventory_registry=inventory_registry,
        inventory=inventory,
    )
    first = economy.settle_package_declared_negotiated_exchange(_exchange_intent())
    assert first.committed, first.failure
    before = store.export_snapshot()

    duplicate = economy.settle_package_declared_negotiated_exchange(_exchange_intent())
    changed = economy.settle_package_declared_negotiated_exchange(
        _exchange_intent().model_copy(update={"correlation_id": "corr:inf2am:changed"})
    )
    bad_price = economy.settle_package_declared_negotiated_exchange(
        _exchange_intent(proposal_digest="proposal:inf2am:bad-price", amount=9)
    )

    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed
    assert changed.failure is not None
    assert changed.failure.error_code == "idempotency_key_reused"
    assert not bad_price.committed
    assert bad_price.failure is not None
    assert bad_price.failure.error_code == "package_exchange_price_invalid"
    assert before == store.export_snapshot()


def test_inf2am_account_conflict_is_zero_write() -> None:
    store, certification_event = _certified_source()
    inventory_registry, inventory = _inventory_setup(store)
    receipt = inventory.record_reinforced_mill_flour_output_receipt(
        certification_event_id=certification_event.event_id,
        expected_certification_revision=certification_event.stream_revision,
        expected_inventory_stream_revision=store.get_stream_head(
            f"gameplay:inventory:{PROVIDER}"
        ),
        command_id="inf2am:inventory-receipt",
        idempotency_key=_inventory_receipt_key(
            certification_event.event_id,
            certification_event.stream_revision,
        ),
        causation_id=certification_event.event_id,
        correlation_id="corr:inf2am:inventory-receipt",
    )
    assert receipt.committed, receipt.failure
    economy = _economy_setup(
        store=store,
        inventory_registry=inventory_registry,
        inventory=inventory,
    )
    second_receiver = economy.open_account(
        command_id="inf2am:receiver-duplicate",
        account_id="account:inf2am:receiver:second",
        owner_ref=RECEIVER,
        currency_ref="currency:local",
        initial_balance=20,
        idempotency_key="inf2am:receiver-duplicate",
        causation_id="cause:inf2am:receiver-duplicate",
        correlation_id="corr:inf2am:receiver-duplicate",
    )
    assert second_receiver.committed, second_receiver.failure
    before = store.export_snapshot()

    account_conflict = economy.settle_package_declared_negotiated_exchange(
        _exchange_intent(proposal_digest="proposal:inf2am:account-conflict")
    )

    assert not account_conflict.committed
    assert account_conflict.failure is not None
    assert account_conflict.failure.error_code == "package_exchange_party_account_unavailable"
    assert store.export_snapshot() == before


def test_inf2am_stale_provider_inventory_source_is_zero_write() -> None:
    store, certification_event = _certified_source()
    inventory_registry, inventory = _inventory_setup(store)
    receipt = inventory.record_reinforced_mill_flour_output_receipt(
        certification_event_id=certification_event.event_id,
        expected_certification_revision=certification_event.stream_revision,
        expected_inventory_stream_revision=store.get_stream_head(
            f"gameplay:inventory:{PROVIDER}"
        ),
        command_id="inf2am:inventory-receipt",
        idempotency_key=_inventory_receipt_key(
            certification_event.event_id,
            certification_event.stream_revision,
        ),
        causation_id=certification_event.event_id,
        correlation_id="corr:inf2am:inventory-receipt",
    )
    assert receipt.committed, receipt.failure
    inventory_event = store.get_event(receipt.committed_event_ids[0])
    extra_container = inventory.create_container(
        command_id="inf2am:provider-after-receipt",
        actor_ref=PROVIDER,
        spec=ContainerSpec("container:district-milling-cooperative:after-receipt", 50, 50, 4),
        idempotency_key="inf2am:provider-after-receipt",
        causation_id=inventory_event.event_id,
        correlation_id="corr:inf2am:provider-after-receipt",
    )
    assert extra_container.committed, extra_container.failure

    economy = _economy_setup(
        store=store,
        inventory_registry=inventory_registry,
        inventory=inventory,
    )
    before = store.export_snapshot()
    rejected = economy.settle_package_declared_negotiated_exchange(_exchange_intent())

    assert not rejected.committed
    assert rejected.failure is not None
    assert rejected.failure.error_code == "revision_conflict"
    assert store.export_snapshot() == before


def test_inf2am_replay_rejects_forged_economy_settlement_payload() -> None:
    store, certification_event = _certified_source()
    inventory_registry, inventory = _inventory_setup(store)
    receipt = inventory.record_reinforced_mill_flour_output_receipt(
        certification_event_id=certification_event.event_id,
        expected_certification_revision=certification_event.stream_revision,
        expected_inventory_stream_revision=store.get_stream_head(
            f"gameplay:inventory:{PROVIDER}"
        ),
        command_id="inf2am:inventory-receipt",
        idempotency_key=_inventory_receipt_key(
            certification_event.event_id,
            certification_event.stream_revision,
        ),
        causation_id=certification_event.event_id,
        correlation_id="corr:inf2am:inventory-receipt",
    )
    assert receipt.committed, receipt.failure
    economy = _economy_setup(
        store=store,
        inventory_registry=inventory_registry,
        inventory=inventory,
    )
    settled = economy.settle_package_declared_negotiated_exchange(_exchange_intent())
    assert settled.committed, settled.failure
    settlement_id = next(
        event_id
        for event_id in settled.committed_event_ids
        if store.get_event(event_id).event_type
        == "gameplay.economy.package_declared_negotiated_exchange_settled"
    )
    original = store.get_event(settlement_id)
    forged = original.model_copy(
        update={
            "payload": {
                **original.payload,
                "amount_minor": 9,
                "source_event_ids": ["event:forged"],
            }
        },
        deep=True,
    )
    store._events_by_id[settlement_id] = forged
    store._events = [
        forged if event.event_id == settlement_id else event
        for event in store._events
    ]

    with pytest.raises(ValueError, match="package_exchange_replay_invalid"):
        economy.package_declared_negotiated_exchange_projection(scope="authority")
