from __future__ import annotations

import pytest

from app.gameplay.ecology_runtime import EcologyHazardAuthority
from app.gameplay.event_schema_registry import EventSchemaRegistry, register_inf3ab_grain_custody_event_schemas
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog
from app.gameplay.inventory_runtime import (
    ContainerSpec,
    InventoryAuthorityService,
    InventoryDefinitionRegistry,
    ItemDefinition,
)
from test_inf3_grain_harvest import _admit_envelope, _harvest_envelope, _seed


PROVIDER = "organization:district-milling-cooperative"
CONTAINER = "container:district-milling-cooperative:grain-intake"
ITEM = "grain:wheat@1"
EVENT = "gameplay.inventory.grain_harvest_received@1"


def _source() -> tuple[GameplayEventStore, object]:
    store = _seed()
    ecology = EcologyHazardAuthority(store=store)
    assert ecology.admit_grain_crop(
        envelope=_admit_envelope(store),
        crop_ref="crop:inf3:grain:wheat",
        region_ref="region:inf3:grain",
        plot_ref="plot:inf3:grain:1",
    ).committed
    harvested = ecology.harvest_grain_crop(envelope=_harvest_envelope(store))
    assert harvested.committed, harvested.failure
    return store, store.get_event(harvested.committed_event_ids[0])


def _inventory(store: GameplayEventStore) -> InventoryAuthorityService:
    definitions = InventoryDefinitionRegistry()
    definitions.register_item(ItemDefinition(ITEM, "1", 1, 1))
    inventory = InventoryAuthorityService(store=store, registry=definitions)
    created = inventory.create_container(
        command_id="inf3ab:container",
        actor_ref=PROVIDER,
        spec=ContainerSpec(CONTAINER, 100, 100, 4),
        idempotency_key="inf3ab:container",
        causation_id="cause:inf3ab:container",
        correlation_id="corr:inf3ab:container",
    )
    assert created.committed, created.failure
    return inventory


def _key(source_event_id: str, source_revision: int, inventory_revision: int) -> str:
    return f"inventory:grain-harvest-custody:{source_event_id}:{source_revision}:{inventory_revision}:v1"


def _request(store: GameplayEventStore, source: object, **updates: object) -> dict[str, object]:
    values: dict[str, object] = {
        "harvest_event_id": source.event_id,
        "expected_harvest_revision": source.stream_revision,
        "expected_inventory_stream_revision": store.get_stream_head(f"gameplay:inventory:{PROVIDER}"),
        "command_id": "inf3ab:receipt",
        "idempotency_key": _key(
            source.event_id,
            source.stream_revision,
            store.get_stream_head(f"gameplay:inventory:{PROVIDER}"),
        ),
        "causation_id": source.event_id,
        "correlation_id": "corr:inf3ab",
    }
    values.update(updates)
    return values


def test_inf3ab_commits_owner_bound_grain_custody_receipt() -> None:
    store, source = _source()
    inventory = _inventory(store)

    result = inventory.record_grain_harvest_custody_receipt(**_request(store, source))

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == EVENT
    assert event.visibility_policy == "project"
    assert event.payload["actor_ref"] == PROVIDER
    assert event.payload["container_id"] == CONTAINER
    assert event.payload["definition_id"] == ITEM
    assert event.payload["quantity"] == 10
    projection = inventory._projector.rebuild(PROVIDER, store.read_events())
    item_id = event.payload["item_id"]
    assert projection.items[item_id].definition_id == ITEM
    assert projection.locations[item_id] == CONTAINER


def test_inf3ab_duplicate_changed_duplicate_and_replay_are_bounded() -> None:
    store, source = _source()
    inventory = _inventory(store)
    request = _request(store, source)
    first = inventory.record_grain_harvest_custody_receipt(**request)
    assert first.committed
    before = store.export_snapshot()

    duplicate = inventory.record_grain_harvest_custody_receipt(**request)
    changed = inventory.record_grain_harvest_custody_receipt(
        **{**request, "correlation_id": "corr:inf3ab:changed"}
    )
    full = inventory.grain_harvest_custody_view_for()
    tail = inventory.grain_harvest_custody_view_for(checkpoint_at=source.global_sequence)

    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed
    assert changed.failure is not None
    assert changed.failure.error_code == "idempotency_key_reused"
    assert store.export_snapshot() == before
    assert full == tail
    assert source.stream_id in full.source_revision_vector


def test_inf3ab_private_or_stale_harvest_is_zero_write() -> None:
    store, source = _source()
    inventory = _inventory(store)
    private = source.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    store._events_by_id[source.event_id] = private
    before = store.export_snapshot()
    rejected = inventory.record_grain_harvest_custody_receipt(**_request(store, source))
    assert not rejected.committed
    assert rejected.failure is not None
    assert rejected.failure.error_code == "inventory_grain_harvest_source_invalid"
    assert store.export_snapshot() == before

    store, source = _source()
    inventory = _inventory(store)
    store._stream_heads[source.stream_id] = source.stream_revision + 1
    before = store.export_snapshot()
    stale = inventory.record_grain_harvest_custody_receipt(**_request(store, source))
    assert not stale.committed
    assert stale.failure is not None
    assert stale.failure.error_code == "inventory_grain_harvest_source_invalid"
    assert store.export_snapshot() == before


def test_inf3ab_unknown_source_and_wrong_key_are_zero_write() -> None:
    store, source = _source()
    inventory = _inventory(store)
    before = store.export_snapshot()
    missing = inventory.record_grain_harvest_custody_receipt(
        **_request(store, source, harvest_event_id="event:missing")
    )
    assert not missing.committed
    assert missing.failure is not None
    assert missing.failure.error_code == "inventory_grain_harvest_source_missing"
    wrong_key = inventory.record_grain_harvest_custody_receipt(
        **_request(store, source, idempotency_key="caller-selected")
    )
    assert not wrong_key.committed
    assert wrong_key.failure is not None
    assert wrong_key.failure.error_code == "inventory_grain_harvest_idempotency_key_invalid"
    assert store.export_snapshot() == before


def test_inf3ab_missing_item_definition_is_zero_write() -> None:
    store, source = _source()
    inventory = InventoryAuthorityService(store=store, registry=InventoryDefinitionRegistry())
    created = inventory.create_container(
        command_id="inf3ab:container:missing-definition",
        actor_ref=PROVIDER,
        spec=ContainerSpec(CONTAINER, 100, 100, 4),
        idempotency_key="inf3ab:container:missing-definition",
        causation_id="cause:inf3ab:container",
        correlation_id="corr:inf3ab:container",
    )
    assert created.committed
    before = store.export_snapshot()
    rejected = inventory.record_grain_harvest_custody_receipt(**_request(store, source))
    assert not rejected.committed
    assert rejected.failure is not None
    assert rejected.failure.error_code == "inventory_item_definition_unknown"
    assert store.export_snapshot() == before


def test_inf3ab_replay_rejects_forged_source_reference() -> None:
    store, source = _source()
    inventory = _inventory(store)
    result = inventory.record_grain_harvest_custody_receipt(**_request(store, source))
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    forged = event.model_copy(
        update={"payload": {**event.payload, "source_harvest_event_id": "event:forged"}},
        deep=True,
    )
    store._events_by_id[event.event_id] = forged
    store._events = [forged if item.event_id == event.event_id else item for item in store._events]
    with pytest.raises(ValueError, match="inventory_grain_harvest_replay_invalid"):
        inventory.grain_harvest_custody_view_for()


def test_inf3ab_projector_rejects_private_custody_event() -> None:
    store, source = _source()
    inventory = _inventory(store)
    result = inventory.record_grain_harvest_custody_receipt(**_request(store, source))
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    private = event.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    store._events_by_id[event.event_id] = private
    store._events = [private if item.event_id == event.event_id else item for item in store._events]
    with pytest.raises(ValueError, match="inventory_grain_harvest_replay_invalid"):
        inventory._projector.rebuild(PROVIDER, store.read_events())


def test_inf3ab_catalog_row_is_exact_and_non_generic() -> None:
    contract = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:inventory-grain-harvest-custody@1",
        contract_kind="contract_admission",
    )
    assert contract.owner_ref == "actor_gameplay.inventory_domain"
    assert contract.stream_patterns == ("gameplay:inventory:{actor_ref}",)
    assert contract.event_types == (EVENT,)
    assert contract.projection_scope == "project"


def test_inf3ab_event_schema_is_registered_exactly() -> None:
    registry = EventSchemaRegistry()
    register_inf3ab_grain_custody_event_schemas(registry)
    assert registry.get(EVENT, 1).schema_digest.startswith("sha256:")
