from __future__ import annotations

from decimal import Decimal
from types import MappingProxyType

import pytest

from app.gameplay.ability_runtime import AbilityDefinitionRegistry, AbilityPathDefinition, AbilitySkillDefinition, AbilityStateProjector
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.equipment_runtime import (
    EquipmentAuthorityService,
    EquipmentDefinitionRegistry,
    EquipmentProfile,
    EquipmentProjector,
    EquipmentRuntimeError,
    EquipmentSlotDefinition,
)
from app.gameplay.inventory_runtime import (
    ContainerSpec,
    InventoryAuthorityService,
    InventoryDefinitionRegistry,
    InventoryProjector,
    ItemDefinition,
)
from app.gameplay.effective_stats import EffectiveStatResolver, StatBaseline
from app.gameplay.modifier_runtime import ModifierDefinitionRegistry, ModifierStateProjector, ModifierTemplate
from app.gameplay.resource_body_runtime import BodyRuntimeProjection, FunctionalCapacity


ACTOR = "actor:equipment"


def _body(*, right_grip_available: bool = True) -> BodyRuntimeProjection:
    functions = {}
    if not right_grip_available:
        functions["grip.right"] = FunctionalCapacity("grip.right", 0, "unavailable", ())
    return BodyRuntimeProjection(
        ACTOR,
        MappingProxyType({}),
        MappingProxyType(functions),
        MappingProxyType({f"gameplay:body:{ACTOR}": 0}),
        "body:test",
    )


def _ability_registry() -> AbilityDefinitionRegistry:
    registry = AbilityDefinitionRegistry()
    registry.register_skill(AbilitySkillDefinition("skill:sword", "1"))
    registry.register_path(AbilityPathDefinition("path:sword-swing", "skill:sword", "action:sword-swing"))
    return registry


def _modifier_registry() -> ModifierDefinitionRegistry:
    registry = ModifierDefinitionRegistry()
    registry.register_template(
        ModifierTemplate(
            "modifier-template:sword-power",
            "combat.power",
            "additive",
            Decimal("2"),
            "sword-power",
        )
    )
    return registry


def _service() -> tuple[GameplayEventStore, InventoryDefinitionRegistry, EquipmentAuthorityService]:
    store = GameplayEventStore()
    inventory = InventoryDefinitionRegistry()
    inventory.register_item(ItemDefinition("item:sword", "1", 3, 2))
    inventory.register_item(ItemDefinition("item:greatsword", "1", 5, 3))
    inventory.register_item(ItemDefinition("item:helm", "1", 2, 2))
    equipment = EquipmentDefinitionRegistry()
    equipment.register_profile(
        "item:sword",
        EquipmentProfile(
            "profile:sword",
            ("right_hand", "left_hand"),
            (),
            ("path:sword-swing",),
            ("modifier-template:sword-power",),
        ),
    )
    equipment.register_profile(
        "item:greatsword",
        EquipmentProfile(
            "profile:greatsword",
            ("right_hand", "left_hand"),
            (),
            (),
            (),
            ("left_hand",),
        ),
    )
    equipment.register_profile(
        "item:helm",
        EquipmentProfile("profile:helm", ("head",), ()),
    )
    return store, inventory, EquipmentAuthorityService(
        store=store,
        inventory_registry=inventory,
        equipment_registry=equipment,
        ability_registry=_ability_registry(),
        modifier_registry=_modifier_registry(),
        slots=(
            EquipmentSlotDefinition("right_hand", ("grip.right",)),
            EquipmentSlotDefinition("left_hand", ("grip.left",)),
            EquipmentSlotDefinition("head"),
        ),
    )


def _inventory(store: GameplayEventStore, registry: InventoryDefinitionRegistry) -> InventoryAuthorityService:
    return InventoryAuthorityService(store=store, registry=registry)


def _create_sword(store: GameplayEventStore, registry: InventoryDefinitionRegistry) -> None:
    service = _inventory(store, registry)
    assert service.create_container(
        command_id="cmd:bag",
        actor_ref=ACTOR,
        spec=ContainerSpec("container:bag", 20, 20, 4),
        idempotency_key="bag",
        causation_id="cause",
        correlation_id="corr",
    ).committed
    assert service.create_container(
        command_id="cmd:hand",
        actor_ref=ACTOR,
        spec=ContainerSpec("container:hand", 20, 20, 4),
        idempotency_key="hand",
        causation_id="cause",
        correlation_id="corr",
    ).committed
    assert service.instantiate(
        command_id="cmd:sword",
        actor_ref=ACTOR,
        item_id="item:sword:1",
        definition_id="item:sword",
        quantity=1,
        container_id="container:bag",
        idempotency_key="sword",
        causation_id="cause",
        correlation_id="corr",
    ).committed


def _create_greatsword(store: GameplayEventStore, registry: InventoryDefinitionRegistry) -> None:
    service = _inventory(store, registry)
    assert service.instantiate(
        command_id="cmd:greatsword",
        actor_ref=ACTOR,
        item_id="item:greatsword:1",
        definition_id="item:greatsword",
        quantity=1,
        container_id="container:bag",
        idempotency_key="greatsword",
        causation_id="cause",
        correlation_id="corr",
    ).committed


def test_equip_changes_inventory_and_activation_streams_in_one_atomic_batch() -> None:
    store, inventory_registry, service = _service()
    _create_sword(store, inventory_registry)
    event_count = len(store.read_events())

    result = service.equip(
        command_id="cmd:equip",
        actor_ref=ACTOR,
        item_id="item:sword:1",
        source_container_id="container:bag",
        slot_key="right_hand",
        body=_body(),
        idempotency_key="equip",
        causation_id="cause",
        correlation_id="corr",
    )

    assert result.committed
    assert len(store.read_events()) == event_count + 4
    transaction = store.read_transactions()[-1]
    assert {event.stream_id for event in transaction.events} == {
        f"gameplay:inventory:{ACTOR}",
        f"gameplay:equipment:{ACTOR}",
        f"gameplay:abilities:{ACTOR}",
        f"gameplay:modifiers:{ACTOR}",
    }
    inventory = InventoryProjector(inventory_registry).rebuild(ACTOR, store.read_events())
    loadout = EquipmentProjector().rebuild(ACTOR, store.read_events())
    assert inventory.locations == {"item:sword:1": "equipment:right_hand"}
    assert loadout.active_by_slot == {"right_hand": "activation:cmd:equip"}
    ability_state = AbilityStateProjector(_ability_registry()).rebuild(ACTOR, store.read_events())
    assert ability_state.learned == {}
    assert ability_state.grants["ability-grant:activation:cmd:equip:path:sword-swing"].source_ref == "activation:cmd:equip"
    modifier_state = ModifierStateProjector(_modifier_registry()).rebuild(ACTOR, store.read_events())
    resolved = EffectiveStatResolver().resolve(
        StatBaseline(stat_id="combat.power", value=10, source_ref="baseline:test"),
        list(modifier_state.active_modifiers.values()),
    )
    assert resolved.effective_value == 12


def test_incompatible_slot_rejects_before_any_stream_changes() -> None:
    store, inventory_registry, service = _service()
    _create_sword(store, inventory_registry)
    before = store.read_events()

    with pytest.raises(EquipmentRuntimeError, match="equipment_slot_incompatible"):
        service.equip(
            command_id="cmd:bad-slot",
            actor_ref=ACTOR,
            item_id="item:sword:1",
            source_container_id="container:bag",
            slot_key="head",
            body=_body(),
            idempotency_key="bad-slot",
            causation_id="cause",
            correlation_id="corr",
        )

    assert store.read_events() == before


def test_unavailable_body_function_rejects_before_any_stream_changes() -> None:
    store, inventory_registry, service = _service()
    _create_sword(store, inventory_registry)
    before = store.read_events()

    with pytest.raises(EquipmentRuntimeError, match="equipment_body_requirement_failed"):
        service.equip(
            command_id="cmd:injured",
            actor_ref=ACTOR,
            item_id="item:sword:1",
            source_container_id="container:bag",
            slot_key="right_hand",
            body=_body(right_grip_available=False),
            idempotency_key="injured",
            causation_id="cause",
            correlation_id="corr",
        )

    assert store.read_events() == before


def test_unequip_restores_inventory_placement_and_only_ends_that_activation() -> None:
    store, inventory_registry, service = _service()
    _create_sword(store, inventory_registry)
    service.equip(
        command_id="cmd:equip",
        actor_ref=ACTOR,
        item_id="item:sword:1",
        source_container_id="container:bag",
        slot_key="right_hand",
        body=_body(),
        idempotency_key="equip",
        causation_id="cause",
        correlation_id="corr",
    )

    result = service.unequip(
        command_id="cmd:unequip",
        actor_ref=ACTOR,
        activation_id="activation:cmd:equip",
        destination_container_id="container:hand",
        body=_body(),
        idempotency_key="unequip",
        causation_id="cause",
        correlation_id="corr",
    )

    assert result.committed
    inventory = InventoryProjector(inventory_registry).rebuild(ACTOR, store.read_events())
    loadout = EquipmentProjector().rebuild(ACTOR, store.read_events())
    assert inventory.locations == {"item:sword:1": "container:hand"}
    assert loadout.activations == {}
    assert loadout.ended_activation_ids == ("activation:cmd:equip",)
    ability_state = AbilityStateProjector(_ability_registry()).rebuild(ACTOR, store.read_events())
    assert ability_state.learned == {}
    assert ability_state.grants["ability-grant:activation:cmd:equip:path:sword-swing"].status == "revoked"
    modifier_state = ModifierStateProjector(_modifier_registry()).rebuild(ACTOR, store.read_events())
    assert modifier_state.active_modifiers == {}


def test_equip_replays_the_same_idempotency_result_without_second_batch() -> None:
    store, inventory_registry, service = _service()
    _create_sword(store, inventory_registry)
    first = service.equip(
        command_id="cmd:equip",
        actor_ref=ACTOR,
        item_id="item:sword:1",
        source_container_id="container:bag",
        slot_key="right_hand",
        body=_body(),
        idempotency_key="equip",
        causation_id="cause",
        correlation_id="corr",
    )
    event_count = len(store.read_events())

    replay = service.equip(
        command_id="cmd:equip",
        actor_ref=ACTOR,
        item_id="item:sword:1",
        source_container_id="container:bag",
        slot_key="right_hand",
        body=_body(),
        idempotency_key="equip",
        causation_id="cause",
        correlation_id="corr",
    )

    assert first.committed and replay.committed
    assert replay.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == event_count


def test_stale_body_revision_rejects_before_any_stream_changes() -> None:
    store, inventory_registry, service = _service()
    _create_sword(store, inventory_registry)
    assert store.append_batch(
        {
            "transaction_id": "tx:body-change",
            "command_id": "cmd:body-change",
            "expected_stream_revisions": {f"gameplay:body:{ACTOR}": 0},
            "pinned_revisions": {},
            "events": [
                {
                    "event_id": "evt:body-change",
                    "event_type": "gameplay.body.injury_applied",
                    "schema_version": 1,
                    "stream_id": f"gameplay:body:{ACTOR}",
                    "stream_revision": 0,
                    "global_sequence": 0,
                    "transaction_id": "tx:body-change",
                    "command_id": "cmd:body-change",
                    "causation_id": "cause",
                    "correlation_id": "corr",
                    "visibility_policy": "authority_only",
                    "payload": {"actor_ref": ACTOR, "injury_id": "injury:stale", "function_id": "grip.right", "capacity_ratio": 100},
                }
            ],
            "idempotency_record": {"principal_ref": "test", "idempotency_key": "body-change", "payload_digest": "body-change"},
            "outbox_entries": [],
            "result_digest": "body-change",
            "projection_refresh_hints": [],
        }
    ).committed
    before = store.read_events()

    with pytest.raises(EquipmentRuntimeError, match="revision_conflict"):
        service.equip(
            command_id="cmd:stale",
            actor_ref=ACTOR,
            item_id="item:sword:1",
            source_container_id="container:bag",
            slot_key="right_hand",
            body=_body(),
            idempotency_key="stale",
            causation_id="cause",
            correlation_id="corr",
        )

    assert store.read_events() == before


def test_multi_slot_equipment_occupies_each_slot_through_one_activation() -> None:
    store, inventory_registry, service = _service()
    _create_sword(store, inventory_registry)
    _create_greatsword(store, inventory_registry)

    result = service.equip(
        command_id="cmd:equip-greatsword",
        actor_ref=ACTOR,
        item_id="item:greatsword:1",
        source_container_id="container:bag",
        slot_key="right_hand",
        body=_body(),
        idempotency_key="equip-greatsword",
        causation_id="cause",
        correlation_id="corr",
    )

    assert result.committed
    loadout = EquipmentProjector().rebuild(ACTOR, store.read_events())
    assert loadout.active_by_slot == {
        "left_hand": "activation:cmd:equip-greatsword",
        "right_hand": "activation:cmd:equip-greatsword",
    }


def test_multi_slot_conflict_in_a_secondary_slot_writes_nothing() -> None:
    store, inventory_registry, service = _service()
    _create_sword(store, inventory_registry)
    _create_greatsword(store, inventory_registry)
    assert service.equip(
        command_id="cmd:equip-left-sword",
        actor_ref=ACTOR,
        item_id="item:sword:1",
        source_container_id="container:bag",
        slot_key="left_hand",
        body=_body(),
        idempotency_key="equip-left-sword",
        causation_id="cause",
        correlation_id="corr",
    ).committed
    before = store.read_events()

    with pytest.raises(EquipmentRuntimeError, match="equipment_slot_occupied"):
        service.equip(
            command_id="cmd:conflicted-greatsword",
            actor_ref=ACTOR,
            item_id="item:greatsword:1",
            source_container_id="container:bag",
            slot_key="right_hand",
            body=_body(),
            idempotency_key="conflicted-greatsword",
            causation_id="cause",
            correlation_id="corr",
        )

    assert store.read_events() == before


def test_swap_replaces_loadout_and_effect_sources_in_one_atomic_batch() -> None:
    store, inventory_registry, service = _service()
    _create_sword(store, inventory_registry)
    _create_greatsword(store, inventory_registry)
    assert service.equip(
        command_id="cmd:equip-sword",
        actor_ref=ACTOR,
        item_id="item:sword:1",
        source_container_id="container:bag",
        slot_key="right_hand",
        body=_body(),
        idempotency_key="equip-sword",
        causation_id="cause",
        correlation_id="corr",
    ).committed

    result = service.swap(
        command_id="cmd:swap",
        actor_ref=ACTOR,
        outgoing_activation_id="activation:cmd:equip-sword",
        incoming_item_id="item:greatsword:1",
        incoming_source_container_id="container:bag",
        incoming_slot_key="right_hand",
        outgoing_destination_container_id="container:bag",
        body=_body(),
        idempotency_key="swap",
        causation_id="cause",
        correlation_id="corr",
    )

    assert result.committed
    inventory = InventoryProjector(inventory_registry).rebuild(ACTOR, store.read_events())
    loadout = EquipmentProjector().rebuild(ACTOR, store.read_events())
    assert inventory.locations == {
        "item:greatsword:1": "equipment:right_hand",
        "item:sword:1": "container:bag",
    }
    assert loadout.active_by_slot == {
        "left_hand": "activation:cmd:swap",
        "right_hand": "activation:cmd:swap",
    }
    ability_state = AbilityStateProjector(_ability_registry()).rebuild(ACTOR, store.read_events())
    assert ability_state.grants["ability-grant:activation:cmd:equip-sword:path:sword-swing"].status == "revoked"
    assert ModifierStateProjector(_modifier_registry()).rebuild(ACTOR, store.read_events()).active_modifiers == {}


def test_swap_rejects_before_mutating_the_current_loadout() -> None:
    store, inventory_registry, service = _service()
    _create_sword(store, inventory_registry)
    _create_greatsword(store, inventory_registry)
    assert service.equip(
        command_id="cmd:equip-sword",
        actor_ref=ACTOR,
        item_id="item:sword:1",
        source_container_id="container:bag",
        slot_key="right_hand",
        body=_body(),
        idempotency_key="equip-sword",
        causation_id="cause",
        correlation_id="corr",
    ).committed
    before = store.read_events()

    with pytest.raises(EquipmentRuntimeError, match="equipment_destination_rejected"):
        service.swap(
            command_id="cmd:bad-swap",
            actor_ref=ACTOR,
            outgoing_activation_id="activation:cmd:equip-sword",
            incoming_item_id="item:greatsword:1",
            incoming_source_container_id="container:bag",
            incoming_slot_key="right_hand",
            outgoing_destination_container_id="container:missing",
            body=_body(),
            idempotency_key="bad-swap",
            causation_id="cause",
            correlation_id="corr",
        )

    assert store.read_events() == before
