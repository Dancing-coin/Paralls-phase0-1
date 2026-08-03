from __future__ import annotations

from hashlib import sha256

from pydantic import BaseModel, ConfigDict

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import InventoryDefinitionRegistry, InventoryProjector, InventoryRuntimeError
from app.gameplay.models import AppendBatchResult
from app.services.embodied_carry_place_authority_service import EmbodiedCarryPlaceAuthorityService


class CustodyInventoryStowResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    error_code: str = ""
    transaction_id: str = ""
    append_result: AppendBatchResult | None = None
    custody_projection_refreshed: bool = False
    source_occupancy_released: bool = False


class CustodyInventoryRetrieveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    error_code: str = ""
    transaction_id: str = ""
    append_result: AppendBatchResult | None = None
    custody_projection_refreshed: bool = False
    destination_occupancy_reserved: bool = False


class EmbodiedCustodyInventoryAuthorityService:
    """Atomically bridges a settled custody holder to a verified actor container."""

    _PRINCIPAL = "embodied_custody_inventory_authority"
    _RETRIEVE_PRINCIPAL = "embodied_custody_inventory_retrieve_authority"

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        inventory_registry: InventoryDefinitionRegistry,
        custody_service: EmbodiedCarryPlaceAuthorityService,
    ) -> None:
        self._store = store
        self._inventory_registry = inventory_registry
        self._projector = InventoryProjector(inventory_registry)
        self._custody_service = custody_service

    def stow_from_custody(
        self,
        *,
        command_id: str,
        actor_ref: str,
        asset_ref: str,
        item_id: str,
        definition_id: str,
        quantity: int,
        source_holder_ref: str,
        destination_container_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> CustodyInventoryStowResult:
        request_digest = self._digest(
            {
                "actor_ref": actor_ref,
                "asset_ref": asset_ref,
                "item_id": item_id,
                "definition_id": definition_id,
                "quantity": quantity,
                "source_holder_ref": source_holder_ref,
                "destination_container_id": destination_container_id,
                "command_id": command_id,
                "causation_id": causation_id,
                "correlation_id": correlation_id,
            }
        )
        duplicate = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if duplicate is not None:
            existing = self._store.get_idempotency_record(self._PRINCIPAL, idempotency_key)
            if existing is None or existing.payload_digest != request_digest:
                return CustodyInventoryStowResult(
                    accepted=False,
                    error_code="idempotency_key_reused",
                    transaction_id=duplicate.transaction_id,
                    append_result=duplicate,
                )
            return self._replay_committed_result(
                append_result=duplicate.model_copy(
                    update={"idempotency_status": "duplicate_replayed"},
                    deep=True,
                ),
                asset_ref=asset_ref,
                source_holder_ref=source_holder_ref,
                destination_container_id=destination_container_id,
                actor_ref=actor_ref,
            )

        try:
            possession = self._custody_service.possession_projection(asset_ref) if asset_ref else None
        except KeyError:
            possession = None
        if possession is None or str(possession["custody_holder_ref"]) != source_holder_ref:
            return CustodyInventoryStowResult(accepted=False, error_code="source_custody_mismatch")
        source_occupancy = self._custody_service.tracked_drop_target_projection(
            source_holder_ref
        )
        if source_occupancy is not None and source_occupancy["occupied_by_ref"] != asset_ref:
            return CustodyInventoryStowResult(accepted=False, error_code="source_occupancy_mismatch")
        try:
            inventory = self._projector.rebuild(actor_ref, self._store.read_events())
            if destination_container_id not in inventory.containers:
                raise InventoryRuntimeError("inventory_container_unknown")
            if inventory.containers[destination_container_id].sealed:
                raise InventoryRuntimeError("inventory_access_denied")
            if item_id in inventory.items or quantity <= 0:
                raise InventoryRuntimeError("inventory_item_invalid")
            definition = self._inventory_registry.item(definition_id)
            occupied = self._items_in_container(inventory, destination_container_id)
            total_weight = self._total_weight(occupied) + definition.unit_weight * quantity
            total_volume = self._total_volume(occupied) + definition.unit_volume * quantity
            container = inventory.containers[destination_container_id]
            if (
                len(occupied) + 1 > container.capacity_slots
                or total_weight > container.capacity_weight
                or total_volume > container.capacity_volume
            ):
                raise InventoryRuntimeError("inventory_capacity_exceeded")
        except InventoryRuntimeError as exc:
            return CustodyInventoryStowResult(accepted=False, error_code=str(exc))

        custody_holder_ref = f"inventory:container:{actor_ref}:{destination_container_id}"
        custody_stream = f"inventory:possession:{asset_ref}"
        inventory_stream = f"gameplay:inventory:{actor_ref}"
        stow_stream = f"embodied:inventory-stow:{command_id}"
        occupancy_stream = f"scene:occupancy:{source_holder_ref}"
        transaction_id = f"tx:{command_id}:custody-inventory-stow"
        events = self._stow_events(
            asset_ref=asset_ref,
            actor_ref=actor_ref,
            item_id=item_id,
            definition_id=definition_id,
            quantity=quantity,
            source_holder_ref=source_holder_ref,
            destination_container_id=destination_container_id,
            custody_holder_ref=custody_holder_ref,
            owner_ref=str(possession["owner_ref"]),
            transaction_id=transaction_id,
            command_id=command_id,
            causation_id=causation_id,
            correlation_id=correlation_id,
            custody_stream=custody_stream,
            inventory_stream=inventory_stream,
            stow_stream=stow_stream,
            source_occupancy=source_occupancy,
        )
        expected_stream_revisions = {
            custody_stream: self._store.get_stream_head(custody_stream),
            inventory_stream: self._store.get_stream_head(inventory_stream),
            stow_stream: self._store.get_stream_head(stow_stream),
        }
        pinned_revisions = {"inventory": self._store.get_stream_head(inventory_stream)}
        if source_occupancy is not None:
            expected_stream_revisions[occupancy_stream] = self._store.get_stream_head(
                occupancy_stream
            )
            pinned_revisions["scene"] = int(source_occupancy["scene_revision"])
        append_result = self._store.append_batch(
            {
                "transaction_id": transaction_id,
                "command_id": command_id,
                "expected_stream_revisions": expected_stream_revisions,
                "pinned_revisions": pinned_revisions,
                "events": events,
                "idempotency_record": {
                    "principal_ref": self._PRINCIPAL,
                    "idempotency_key": idempotency_key,
                    "payload_digest": request_digest,
                },
                "outbox_entries": [],
                "result_digest": self._digest(events),
                "projection_refresh_hints": [],
            }
        )
        if not append_result.committed:
            return CustodyInventoryStowResult(accepted=False, error_code=append_result.failure.error_code if append_result.failure else "append_batch_failed", transaction_id=transaction_id, append_result=append_result)
        refreshed = self._custody_service.apply_committed_custody_transfer(
            asset_ref=asset_ref,
            expected_holder_ref=source_holder_ref,
            custody_holder_ref=custody_holder_ref,
            authority_transaction_id=transaction_id,
            released_drop_target_ref=source_holder_ref if source_occupancy is not None else "",
        )
        return CustodyInventoryStowResult(
            accepted=True,
            transaction_id=transaction_id,
            append_result=append_result,
            custody_projection_refreshed=refreshed,
            source_occupancy_released=refreshed and source_occupancy is not None,
        )

    def retrieve_to_custody(
        self,
        *,
        command_id: str,
        actor_ref: str,
        asset_ref: str,
        item_id: str,
        source_container_id: str,
        destination_receiver_ref: str,
        expected_definition_id: str = "",
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> CustodyInventoryRetrieveResult:
        request_digest = self._digest(
            {
                "command_id": command_id,
                "actor_ref": actor_ref,
                "asset_ref": asset_ref,
                "item_id": item_id,
                "source_container_id": source_container_id,
                "destination_receiver_ref": destination_receiver_ref,
                "expected_definition_id": expected_definition_id,
                "causation_id": causation_id,
                "correlation_id": correlation_id,
            }
        )
        duplicate = self._store.get_by_idempotency(
            self._RETRIEVE_PRINCIPAL,
            idempotency_key,
        )
        if duplicate is not None:
            existing = self._store.get_idempotency_record(
                self._RETRIEVE_PRINCIPAL,
                idempotency_key,
            )
            if existing is None or existing.payload_digest != request_digest:
                return CustodyInventoryRetrieveResult(
                    accepted=False,
                    error_code="idempotency_key_reused",
                    transaction_id=duplicate.transaction_id,
                    append_result=duplicate,
                )
            return self._replay_committed_retrieve_result(
                append_result=duplicate.model_copy(
                    update={"idempotency_status": "duplicate_replayed"},
                    deep=True,
                ),
                asset_ref=asset_ref,
                source_holder_ref=self._inventory_holder_ref(actor_ref, source_container_id),
                destination_receiver_ref=destination_receiver_ref,
            )

        source_holder_ref = self._inventory_holder_ref(actor_ref, source_container_id)
        try:
            possession = self._custody_service.possession_projection(asset_ref)
        except KeyError:
            possession = None
        if possession is None or possession["custody_holder_ref"] != source_holder_ref:
            return CustodyInventoryRetrieveResult(
                accepted=False,
                error_code="source_custody_mismatch",
            )
        receiver = self._custody_service.tracked_drop_target_projection(
            destination_receiver_ref
        )
        if receiver is None:
            return CustodyInventoryRetrieveResult(
                accepted=False,
                error_code="destination_receiver_unknown",
            )
        if receiver["occupied_by_ref"]:
            return CustodyInventoryRetrieveResult(
                accepted=False,
                error_code="destination_receiver_occupied",
            )
        try:
            inventory = self._projector.rebuild(actor_ref, self._store.read_events())
            source_container = inventory.containers.get(source_container_id)
            item = inventory.items.get(item_id)
            if source_container is None:
                raise InventoryRuntimeError("inventory_container_unknown")
            if source_container.sealed:
                raise InventoryRuntimeError("inventory_access_denied")
            if item is None or inventory.locations.get(item_id) != source_container_id:
                raise InventoryRuntimeError("inventory_move_source_invalid")
            if expected_definition_id and item.definition_id != expected_definition_id:
                raise InventoryRuntimeError("inventory_item_definition_mismatch")
        except InventoryRuntimeError as exc:
            return CustodyInventoryRetrieveResult(accepted=False, error_code=str(exc))

        transaction_id = f"tx:{command_id}:inventory-custody-retrieve"
        custody_stream = f"inventory:possession:{asset_ref}"
        inventory_stream = f"gameplay:inventory:{actor_ref}"
        occupancy_stream = f"scene:occupancy:{destination_receiver_ref}"
        retrieve_stream = f"embodied:inventory-retrieve:{command_id}"
        events = self._retrieve_events(
            asset_ref=asset_ref,
            actor_ref=actor_ref,
            item_id=item_id,
            source_container_id=source_container_id,
            source_holder_ref=source_holder_ref,
            destination_receiver_ref=destination_receiver_ref,
            owner_ref=str(possession["owner_ref"]),
            next_scene_revision=int(receiver["scene_revision"]) + 1,
            transaction_id=transaction_id,
            command_id=command_id,
            causation_id=causation_id,
            correlation_id=correlation_id,
            custody_stream=custody_stream,
            inventory_stream=inventory_stream,
            occupancy_stream=occupancy_stream,
            retrieve_stream=retrieve_stream,
        )
        append_result = self._store.append_batch(
            {
                "transaction_id": transaction_id,
                "command_id": command_id,
                "expected_stream_revisions": {
                    custody_stream: self._store.get_stream_head(custody_stream),
                    inventory_stream: self._store.get_stream_head(inventory_stream),
                    occupancy_stream: self._store.get_stream_head(occupancy_stream),
                    retrieve_stream: self._store.get_stream_head(retrieve_stream),
                },
                "pinned_revisions": {
                    "inventory": self._store.get_stream_head(inventory_stream),
                    "scene": int(receiver["scene_revision"]),
                },
                "events": events,
                "idempotency_record": {
                    "principal_ref": self._RETRIEVE_PRINCIPAL,
                    "idempotency_key": idempotency_key,
                    "payload_digest": request_digest,
                },
                "outbox_entries": [],
                "result_digest": self._digest(events),
                "projection_refresh_hints": [],
            }
        )
        if not append_result.committed:
            return CustodyInventoryRetrieveResult(
                accepted=False,
                error_code=self._append_error(append_result),
                transaction_id=transaction_id,
                append_result=append_result,
            )
        refreshed = self._custody_service.apply_committed_custody_transfer(
            asset_ref=asset_ref,
            expected_holder_ref=source_holder_ref,
            custody_holder_ref=destination_receiver_ref,
            authority_transaction_id=transaction_id,
            occupied_drop_target_ref=destination_receiver_ref,
        )
        return CustodyInventoryRetrieveResult(
            accepted=True,
            transaction_id=transaction_id,
            append_result=append_result,
            custody_projection_refreshed=refreshed,
            destination_occupancy_reserved=refreshed,
        )

    def _replay_committed_result(
        self,
        *,
        append_result: AppendBatchResult,
        asset_ref: str,
        source_holder_ref: str,
        destination_container_id: str,
        actor_ref: str,
    ) -> CustodyInventoryStowResult:
        custody_holder_ref = f"inventory:container:{actor_ref}:{destination_container_id}"
        try:
            possession = self._custody_service.possession_projection(asset_ref)
        except KeyError:
            possession = None
        refreshed = possession is not None and possession["custody_holder_ref"] == custody_holder_ref
        if possession is not None and possession["custody_holder_ref"] == source_holder_ref:
            refreshed = self._custody_service.apply_committed_custody_transfer(
                asset_ref=asset_ref,
                expected_holder_ref=source_holder_ref,
                custody_holder_ref=custody_holder_ref,
                authority_transaction_id=append_result.transaction_id,
            )
        return CustodyInventoryStowResult(
            accepted=append_result.committed,
            error_code="" if append_result.committed else self._append_error(append_result),
            transaction_id=append_result.transaction_id,
            append_result=append_result,
            custody_projection_refreshed=refreshed,
        )

    def _replay_committed_retrieve_result(
        self,
        *,
        append_result: AppendBatchResult,
        asset_ref: str,
        source_holder_ref: str,
        destination_receiver_ref: str,
    ) -> CustodyInventoryRetrieveResult:
        try:
            possession = self._custody_service.possession_projection(asset_ref)
        except KeyError:
            possession = None
        receiver = self._custody_service.tracked_drop_target_projection(
            destination_receiver_ref
        )
        refreshed = (
            possession is not None
            and possession["custody_holder_ref"] == destination_receiver_ref
            and receiver is not None
            and receiver["occupied_by_ref"] == asset_ref
        )
        if (
            possession is not None
            and possession["custody_holder_ref"] == source_holder_ref
            and receiver is not None
            and not receiver["occupied_by_ref"]
        ):
            refreshed = self._custody_service.apply_committed_custody_transfer(
                asset_ref=asset_ref,
                expected_holder_ref=source_holder_ref,
                custody_holder_ref=destination_receiver_ref,
                authority_transaction_id=append_result.transaction_id,
                occupied_drop_target_ref=destination_receiver_ref,
            )
        return CustodyInventoryRetrieveResult(
            accepted=append_result.committed,
            error_code="" if append_result.committed else self._append_error(append_result),
            transaction_id=append_result.transaction_id,
            append_result=append_result,
            custody_projection_refreshed=refreshed,
            destination_occupancy_reserved=refreshed,
        )

    def _stow_events(
        self,
        *,
        asset_ref: str,
        actor_ref: str,
        item_id: str,
        definition_id: str,
        quantity: int,
        source_holder_ref: str,
        destination_container_id: str,
        custody_holder_ref: str,
        owner_ref: str,
        transaction_id: str,
        command_id: str,
        causation_id: str,
        correlation_id: str,
        custody_stream: str,
        inventory_stream: str,
        stow_stream: str,
        source_occupancy: dict[str, object] | None,
    ) -> list[dict[str, object]]:
        events = [
            self._event(
                1,
                "inventory.custody_changed",
                custody_stream,
                transaction_id,
                command_id,
                causation_id,
                correlation_id,
                {
                    "asset_ref": asset_ref,
                    "from_holder_ref": source_holder_ref,
                    "to_holder_ref": custody_holder_ref,
                    "custody_holder_ref": custody_holder_ref,
                    "owner_ref": owner_ref,
                },
            ),
            self._event(
                2,
                "gameplay.inventory.item_transferred_in",
                inventory_stream,
                transaction_id,
                command_id,
                causation_id,
                correlation_id,
                {
                    "actor_ref": actor_ref,
                    "item_id": item_id,
                    "definition_id": definition_id,
                    "quantity": quantity,
                    "to_container_id": destination_container_id,
                    "from_custody_ref": source_holder_ref,
                },
            ),
        ]
        if source_occupancy is not None:
            events.append(
                self._event(
                    3,
                    "scene.occupancy.changed",
                    f"scene:occupancy:{source_holder_ref}",
                    transaction_id,
                    command_id,
                    causation_id,
                    correlation_id,
                    {
                        "target_ref": source_holder_ref,
                        "previous_occupied_by_ref": asset_ref,
                        "occupied_by_ref": "",
                        "scene_revision": int(source_occupancy["scene_revision"]) + 1,
                        "source_command_id": command_id,
                    },
                )
            )
        events.append(
            self._event(
                len(events) + 1,
                "embodied.inventory.stowed",
                stow_stream,
                transaction_id,
                command_id,
                causation_id,
                correlation_id,
                {
                    "asset_ref": asset_ref,
                    "actor_ref": actor_ref,
                    "item_id": item_id,
                    "destination_container_id": destination_container_id,
                    "custody_holder_ref": custody_holder_ref,
                },
            )
        )
        return events

    def _retrieve_events(
        self,
        *,
        asset_ref: str,
        actor_ref: str,
        item_id: str,
        source_container_id: str,
        source_holder_ref: str,
        destination_receiver_ref: str,
        owner_ref: str,
        next_scene_revision: int,
        transaction_id: str,
        command_id: str,
        causation_id: str,
        correlation_id: str,
        custody_stream: str,
        inventory_stream: str,
        occupancy_stream: str,
        retrieve_stream: str,
    ) -> list[dict[str, object]]:
        return [
            self._event(
                1,
                "inventory.custody_changed",
                custody_stream,
                transaction_id,
                command_id,
                causation_id,
                correlation_id,
                {
                    "asset_ref": asset_ref,
                    "from_holder_ref": source_holder_ref,
                    "to_holder_ref": destination_receiver_ref,
                    "custody_holder_ref": destination_receiver_ref,
                    "owner_ref": owner_ref,
                },
            ),
            self._event(
                2,
                "gameplay.inventory.item_transferred_out",
                inventory_stream,
                transaction_id,
                command_id,
                causation_id,
                correlation_id,
                {
                    "actor_ref": actor_ref,
                    "item_id": item_id,
                    "from_container_id": source_container_id,
                    "to_custody_ref": destination_receiver_ref,
                },
            ),
            self._event(
                3,
                "scene.occupancy.changed",
                occupancy_stream,
                transaction_id,
                command_id,
                causation_id,
                correlation_id,
                {
                    "target_ref": destination_receiver_ref,
                    "previous_occupied_by_ref": "",
                    "occupied_by_ref": asset_ref,
                    "scene_revision": next_scene_revision,
                    "source_command_id": command_id,
                },
            ),
            self._event(
                4,
                "embodied.inventory.retrieved",
                retrieve_stream,
                transaction_id,
                command_id,
                causation_id,
                correlation_id,
                {
                    "asset_ref": asset_ref,
                    "actor_ref": actor_ref,
                    "item_id": item_id,
                    "source_container_id": source_container_id,
                    "destination_receiver_ref": destination_receiver_ref,
                    "custody_holder_ref": destination_receiver_ref,
                },
            ),
        ]

    @staticmethod
    def _inventory_holder_ref(actor_ref: str, container_id: str) -> str:
        return f"inventory:container:{actor_ref}:{container_id}"

    def _items_in_container(self, inventory: object, container_id: str) -> list[object]:
        return [
            item
            for item_id, item in inventory.items.items()
            if inventory.locations.get(item_id) == container_id
        ]

    def _total_weight(self, items: list[object]) -> int:
        return sum(
            self._inventory_registry.item(item.definition_id).unit_weight * item.quantity
            for item in items
        )

    def _total_volume(self, items: list[object]) -> int:
        return sum(
            self._inventory_registry.item(item.definition_id).unit_volume * item.quantity
            for item in items
        )

    @staticmethod
    def _append_error(append_result: AppendBatchResult) -> str:
        return append_result.failure.error_code if append_result.failure else "append_batch_failed"

    @staticmethod
    def _event(index: int, event_type: str, stream_id: str, transaction_id: str, command_id: str, causation_id: str, correlation_id: str, payload: dict[str, object]) -> dict[str, object]:
        return {"event_id": f"evt:{command_id}:custody-inventory:{index}", "event_type": event_type, "schema_version": 1, "stream_id": stream_id, "stream_revision": 0, "global_sequence": 0, "transaction_id": transaction_id, "command_id": command_id, "causation_id": causation_id, "correlation_id": correlation_id, "visibility_policy": "authority_only", "payload": payload}

    @staticmethod
    def _digest(value: object) -> str:
        return "sha256:" + sha256(repr(value).encode("utf-8")).hexdigest()
