from __future__ import annotations

from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry, InventoryProjector, ItemDefinition
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.embodied_carry_place_authority_service import EmbodiedCarryPlaceAuthorityService
from app.services.embodied_custody_inventory_authority_service import EmbodiedCustodyInventoryAuthorityService
from app.services.embodied_evidence_ledger import EmbodiedEvidenceLedger


ACTOR_REF = "character:char_c"
CONTAINER_ID = "container:char_c:backpack"


def _services(*, capacity_slots: int = 2) -> tuple[GameplayEventStore, EmbodiedCarryPlaceAuthorityService, EmbodiedCustodyInventoryAuthorityService, InventoryProjector]:
    store = GameplayEventStore()
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition("archive_token", "v1", 1, 1))
    inventory = InventoryAuthorityService(store=store, registry=registry)
    inventory.create_container(command_id="bootstrap-container", actor_ref=ACTOR_REF, spec=ContainerSpec(CONTAINER_ID, 3, 3, capacity_slots), idempotency_key="bootstrap", causation_id="bootstrap", correlation_id="bootstrap")
    custody = EmbodiedCarryPlaceAuthorityService(store=store, dispatcher=GameplayOutboxDispatcher(store=store, bus=InMemoryAuthorityEventBus()), evidence_ledger=EmbodiedEvidenceLedger())
    custody.seed_asset_possession(asset_ref="item:archive_token_01", custody_holder_ref="character:char_c:hand", owner_ref="world:archive")
    custody.seed_drop_target(
        target_ref="character:char_c:hand",
        occupied_by_ref="item:archive_token_01",
        scene_revision=11,
    )
    return store, custody, EmbodiedCustodyInventoryAuthorityService(store=store, inventory_registry=registry, custody_service=custody), InventoryProjector(registry)


def test_stow_from_custody_commits_inventory_location_and_custody_in_one_batch() -> None:
    store, custody, service, projector = _services()

    result = service.stow_from_custody(command_id="stow-token", actor_ref=ACTOR_REF, asset_ref="item:archive_token_01", item_id="item:archive_token_01", definition_id="archive_token", quantity=1, source_holder_ref="character:char_c:hand", destination_container_id=CONTAINER_ID, idempotency_key="stow-1", causation_id="pickup:1", correlation_id="pickup:1")
    transaction = store.read_transactions()[-1]
    inventory = projector.rebuild(ACTOR_REF, store.read_events())

    assert result.accepted is True
    assert [event.event_type for event in transaction.events] == [
        "inventory.custody_changed",
        "gameplay.inventory.item_transferred_in",
        "scene.occupancy.changed",
        "embodied.inventory.stowed",
    ]
    assert len({event.transaction_id for event in transaction.events}) == 1
    assert inventory.locations["item:archive_token_01"] == CONTAINER_ID
    assert custody.possession_projection("item:archive_token_01")["custody_holder_ref"] == f"inventory:container:{ACTOR_REF}:{CONTAINER_ID}"
    assert custody.drop_target_projection("character:char_c:hand")["occupied_by_ref"] == ""
    assert result.source_occupancy_released is True


def test_stow_from_custody_rejects_capacity_without_mutating_custody_or_inventory() -> None:
    store, custody, service, projector = _services(capacity_slots=0)

    result = service.stow_from_custody(command_id="stow-token", actor_ref=ACTOR_REF, asset_ref="item:archive_token_01", item_id="item:archive_token_01", definition_id="archive_token", quantity=1, source_holder_ref="character:char_c:hand", destination_container_id=CONTAINER_ID, idempotency_key="stow-1", causation_id="pickup:1", correlation_id="pickup:1")
    inventory = projector.rebuild(ACTOR_REF, store.read_events())

    assert result.accepted is False
    assert result.error_code == "inventory_capacity_exceeded"
    assert custody.possession_projection("item:archive_token_01")["custody_holder_ref"] == "character:char_c:hand"
    assert custody.drop_target_projection("character:char_c:hand")["occupied_by_ref"] == "item:archive_token_01"
    assert inventory.items == {}


def test_stow_from_custody_replays_the_committed_transaction_before_custody_validation() -> None:
    store, custody, service, projector = _services()
    command = {
        "command_id": "stow-token",
        "actor_ref": ACTOR_REF,
        "asset_ref": "item:archive_token_01",
        "item_id": "item:archive_token_01",
        "definition_id": "archive_token",
        "quantity": 1,
        "source_holder_ref": "character:char_c:hand",
        "destination_container_id": CONTAINER_ID,
        "idempotency_key": "stow-1",
        "causation_id": "pickup:1",
        "correlation_id": "pickup:1",
    }

    first = service.stow_from_custody(**command)
    replayed = service.stow_from_custody(**command)
    inventory = projector.rebuild(ACTOR_REF, store.read_events())

    assert first.accepted is True
    assert replayed.accepted is True
    assert replayed.append_result is not None
    assert replayed.append_result.idempotency_status == "duplicate_replayed"
    assert replayed.transaction_id == first.transaction_id
    assert len(store.read_transactions()) == 2
    assert len(store.read_transactions()[-1].events) == 4
    assert inventory.locations["item:archive_token_01"] == CONTAINER_ID
    assert custody.possession_projection("item:archive_token_01")["custody_holder_ref"] == f"inventory:container:{ACTOR_REF}:{CONTAINER_ID}"
    assert custody.drop_target_projection("character:char_c:hand")["occupied_by_ref"] == ""


def test_retrieve_to_custody_commits_inventory_out_custody_and_receiver_occupancy_in_one_batch() -> None:
    store, custody, service, projector = _services()
    stowed = service.stow_from_custody(
        command_id="stow-token",
        actor_ref=ACTOR_REF,
        asset_ref="item:archive_token_01",
        item_id="item:archive_token_01",
        definition_id="archive_token",
        quantity=1,
        source_holder_ref="character:char_c:hand",
        destination_container_id=CONTAINER_ID,
        idempotency_key="stow-1",
        causation_id="pickup:1",
        correlation_id="pickup:1",
    )

    result = service.retrieve_to_custody(
        command_id="retrieve-token",
        actor_ref=ACTOR_REF,
        asset_ref="item:archive_token_01",
        item_id="item:archive_token_01",
        source_container_id=CONTAINER_ID,
        destination_receiver_ref="character:char_c:hand",
        expected_definition_id="archive_token",
        idempotency_key="retrieve-1",
        causation_id="stow:1",
        correlation_id="stow:1",
    )
    transaction = store.read_transactions()[-1]
    inventory = projector.rebuild(ACTOR_REF, store.read_events())

    assert stowed.accepted is True
    assert result.accepted is True
    assert [event.event_type for event in transaction.events] == [
        "inventory.custody_changed",
        "gameplay.inventory.item_transferred_out",
        "scene.occupancy.changed",
        "embodied.inventory.retrieved",
    ]
    assert inventory.locations == {}
    assert inventory.items["item:archive_token_01"].definition_id == "archive_token"
    assert custody.possession_projection("item:archive_token_01")["custody_holder_ref"] == "character:char_c:hand"
    assert custody.possession_projection("item:archive_token_01")["owner_ref"] == "world:archive"
    assert custody.drop_target_projection("character:char_c:hand")["occupied_by_ref"] == "item:archive_token_01"
    assert result.destination_occupancy_reserved is True


def test_retrieve_to_custody_rejects_occupied_receiver_without_mutating_inventory_or_custody() -> None:
    store, custody, service, projector = _services()
    service.stow_from_custody(
        command_id="stow-token",
        actor_ref=ACTOR_REF,
        asset_ref="item:archive_token_01",
        item_id="item:archive_token_01",
        definition_id="archive_token",
        quantity=1,
        source_holder_ref="character:char_c:hand",
        destination_container_id=CONTAINER_ID,
        idempotency_key="stow-1",
        causation_id="pickup:1",
        correlation_id="pickup:1",
    )
    custody.seed_drop_target(
        target_ref="character:char_c:hand",
        occupied_by_ref="item:other",
        scene_revision=13,
    )
    transaction_count = len(store.read_transactions())

    result = service.retrieve_to_custody(
        command_id="retrieve-token",
        actor_ref=ACTOR_REF,
        asset_ref="item:archive_token_01",
        item_id="item:archive_token_01",
        source_container_id=CONTAINER_ID,
        destination_receiver_ref="character:char_c:hand",
        idempotency_key="retrieve-1",
        causation_id="stow:1",
        correlation_id="stow:1",
    )
    inventory = projector.rebuild(ACTOR_REF, store.read_events())

    assert result.accepted is False
    assert result.error_code == "destination_receiver_occupied"
    assert len(store.read_transactions()) == transaction_count
    assert inventory.locations["item:archive_token_01"] == CONTAINER_ID
    assert custody.possession_projection("item:archive_token_01")["custody_holder_ref"] == f"inventory:container:{ACTOR_REF}:{CONTAINER_ID}"


def test_retrieve_to_custody_replays_before_mutable_source_checks() -> None:
    store, custody, service, _projector = _services()
    service.stow_from_custody(
        command_id="stow-token",
        actor_ref=ACTOR_REF,
        asset_ref="item:archive_token_01",
        item_id="item:archive_token_01",
        definition_id="archive_token",
        quantity=1,
        source_holder_ref="character:char_c:hand",
        destination_container_id=CONTAINER_ID,
        idempotency_key="stow-1",
        causation_id="pickup:1",
        correlation_id="pickup:1",
    )
    command = {
        "command_id": "retrieve-token",
        "actor_ref": ACTOR_REF,
        "asset_ref": "item:archive_token_01",
        "item_id": "item:archive_token_01",
        "source_container_id": CONTAINER_ID,
        "destination_receiver_ref": "character:char_c:hand",
        "expected_definition_id": "archive_token",
        "idempotency_key": "retrieve-1",
        "causation_id": "stow:1",
        "correlation_id": "stow:1",
    }

    first = service.retrieve_to_custody(**command)
    replayed = service.retrieve_to_custody(**command)

    assert first.accepted is True
    assert replayed.accepted is True
    assert replayed.append_result is not None
    assert replayed.append_result.idempotency_status == "duplicate_replayed"
    assert replayed.transaction_id == first.transaction_id
    assert len(store.read_transactions()) == 3
    assert custody.possession_projection("item:archive_token_01")["custody_holder_ref"] == "character:char_c:hand"
