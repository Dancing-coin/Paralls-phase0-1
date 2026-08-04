"""Read-only Godot mirror views for the governed adventure-basic scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping

from app.gameplay.adventure_basic_closure import capture_adventure_basic_closure
from app.gameplay.adventure_basic_reference import (
    AdventureBasicScenario1,
    AdventureBasicScenario2,
    AdventureBasicScenario3,
    AdventureBasicScenario4,
    AdventureBasicScenario5,
)
from app.gameplay.state_group_views import CharacterGameRuntimeStateView, StateGroupRuntimeViewEnvelope


class AdventureBasicMirrorSourceError(ValueError):
    """Raised when a scenario cannot provide a safe committed mirror view."""


Scenario = (
    AdventureBasicScenario1
    | AdventureBasicScenario2
    | AdventureBasicScenario3
    | AdventureBasicScenario4
    | AdventureBasicScenario5
)

_SCENARIO_TYPES = {
    "scenario-1": AdventureBasicScenario1,
    "scenario-2": AdventureBasicScenario2,
    "scenario-3": AdventureBasicScenario3,
    "scenario-4": AdventureBasicScenario4,
    "scenario-5": AdventureBasicScenario5,
}

_PRESENTATION_STATES = {
    "scenario-1": "sword_equipped",
}


@dataclass(frozen=True)
class AdventureBasicMirrorSource:
    """Build one disposable Godot view from an already committed scenario store."""

    scenario_id: str
    scenario: Scenario

    def __post_init__(self) -> None:
        expected_type = _SCENARIO_TYPES.get(self.scenario_id)
        if expected_type is None or not isinstance(self.scenario, expected_type):
            raise AdventureBasicMirrorSourceError("adventure_basic_mirror_scenario_mismatch")

    def godot_view(self) -> CharacterGameRuntimeStateView:
        try:
            evidence = capture_adventure_basic_closure(
                scenario_id=self.scenario_id,
                scenario=self.scenario,
            )
        except ValueError as exc:
            raise AdventureBasicMirrorSourceError("adventure_basic_mirror_projection_unavailable") from exc

        source_revision_vector = MappingProxyType(dict(sorted(evidence.source_revision_vector.items())))
        group_id = f"adventure.basic.{self.scenario_id}"
        payload = MappingProxyType(
            {
                "scenario_id": self.scenario_id,
                "presentation_state": _presentation_state(
                    scenario_id=self.scenario_id,
                    scenario=self.scenario,
                    facade=evidence.online_facade,
                ),
                "facade_checksum": evidence.online_facade_hash,
                "latest_transaction_id": str(evidence.result_metadata["latest_transaction_id"]),
                "source_revision_vector": dict(source_revision_vector),
            }
        )
        envelope = StateGroupRuntimeViewEnvelope(
            group_id=group_id,
            definition_version="1",
            projection_schema_version=1,
            projection_revision=evidence.online_facade_hash,
            source_revision_vector=source_revision_vector,
            payload=payload,
        )
        groups: Mapping[str, StateGroupRuntimeViewEnvelope] = MappingProxyType({group_id: envelope})
        return CharacterGameRuntimeStateView(
            actor_ref=self.scenario.player_ref,
            consumer="godot",
            source_facade_revision=evidence.online_facade_hash,
            source_revision_vector=source_revision_vector,
            groups=groups,
            view_checksum=_view_checksum(
                actor_ref=self.scenario.player_ref,
                facade_revision=evidence.online_facade_hash,
                group_id=group_id,
                payload=payload,
            ),
        )


def _presentation_state(
    *,
    scenario_id: str,
    scenario: Scenario,
    facade: Mapping[str, object],
) -> str:
    if scenario_id == "scenario-1":
        assert isinstance(scenario, AdventureBasicScenario1)
        if _slot_is_active(facade, "right_hand"):
            return "sword_equipped"
        if _inventory_contains(facade, scenario.sword_item_id):
            return "sword_purchased"
        return "sword_offer_available"
    if scenario_id == "scenario-2":
        assert isinstance(scenario, AdventureBasicScenario2)
        if not _slot_is_active(facade, "right_hand"):
            return "sword_action_unavailable"
        if _resource_current(facade, scenario.stamina_resource_id) < 24:
            return "resource_action_resolved"
        return "sword_action_ready"
    if scenario_id == "scenario-3":
        assert isinstance(scenario, AdventureBasicScenario3)
        if _inventory_location(facade, scenario.cargo_item_id) == scenario.storage_ring_container_id:
            return "storage_ring_loaded"
        if _facade_flag(facade, "storage_ring_access", "active"):
            return "storage_ring_equipped"
        return "storage_ring_available"
    if scenario_id == "scenario-4":
        assert isinstance(scenario, AdventureBasicScenario4)
        if _right_holder(facade, scenario.land_right_id) == scenario.recipient_ref:
            return "land_right_transferred"
        if _right_holder(facade, scenario.land_right_id) == scenario.player_ref:
            return "land_right_purchased"
        return "land_right_available"
    if scenario_id == "scenario-5":
        assert isinstance(scenario, AdventureBasicScenario5)
        if _contract_status(facade, scenario.service_contract_id) == "fulfilled":
            return "gift_debt_contract_settled"
        return "gift_debt_contract_available"
    raise AdventureBasicMirrorSourceError("adventure_basic_mirror_scenario_mismatch")


def _inventory_contains(facade: Mapping[str, object], item_id: str) -> bool:
    inventory = facade.get("inventory", {})
    return isinstance(inventory, Mapping) and isinstance(inventory.get("items", {}), Mapping) and item_id in inventory["items"]


def _inventory_location(facade: Mapping[str, object], item_id: str) -> str:
    inventory = facade.get("inventory", {})
    if not isinstance(inventory, Mapping):
        return ""
    locations = inventory.get("locations", {})
    return str(locations.get(item_id, "")) if isinstance(locations, Mapping) else ""


def _slot_is_active(facade: Mapping[str, object], slot_key: str) -> bool:
    equipment = facade.get("equipment", {})
    if not isinstance(equipment, Mapping):
        return False
    active_by_slot = equipment.get("active_by_slot", {})
    return isinstance(active_by_slot, Mapping) and bool(str(active_by_slot.get(slot_key, "")))


def _resource_current(facade: Mapping[str, object], resource_id: str) -> int:
    resources = facade.get("resources", {})
    if not isinstance(resources, Mapping):
        return 0
    entries = resources.get("entries", {})
    if not isinstance(entries, Mapping):
        return 0
    entry = entries.get(resource_id, {})
    return int(entry.get("current", 0)) if isinstance(entry, Mapping) else 0


def _facade_flag(facade: Mapping[str, object], group_id: str, flag: str) -> bool:
    group = facade.get(group_id, {})
    return bool(group.get(flag, False)) if isinstance(group, Mapping) else False


def _right_holder(facade: Mapping[str, object], right_id: str) -> str:
    ownership = facade.get("ownership", {})
    if not isinstance(ownership, Mapping):
        return ""
    rights = ownership.get("rights", {})
    right = rights.get(right_id, {}) if isinstance(rights, Mapping) else {}
    return str(right.get("holder_ref", "")) if isinstance(right, Mapping) else ""


def _contract_status(facade: Mapping[str, object], contract_id: str) -> str:
    contracts = facade.get("contracts", {})
    if not isinstance(contracts, Mapping):
        return ""
    entries = contracts.get("contracts", {})
    contract = entries.get(contract_id, {}) if isinstance(entries, Mapping) else {}
    return str(contract.get("status", "")) if isinstance(contract, Mapping) else ""


def _view_checksum(
    *,
    actor_ref: str,
    facade_revision: str,
    group_id: str,
    payload: Mapping[str, object],
) -> str:
    encoded = json.dumps(
        {
            "actor_ref": actor_ref,
            "consumer": "godot",
            "facade_revision": facade_revision,
            "groups": {group_id: dict(payload)},
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


__all__ = ["AdventureBasicMirrorSource", "AdventureBasicMirrorSourceError"]
