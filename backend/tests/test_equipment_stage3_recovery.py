from __future__ import annotations

from decimal import Decimal

from app.gameplay.ability_runtime import (
    AbilityAuthorityService,
    AbilityDefinitionRegistry,
    AbilityPathDefinition,
    AbilitySkillDefinition,
    AbilityStateProjector,
)
from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.equipment_runtime import (
    EquipmentAuthorityService,
    EquipmentDefinitionRegistry,
    EquipmentProfile,
    EquipmentProjector,
    EquipmentSlotDefinition,
)
from app.gameplay.inventory_runtime import (
    ContainerSpec,
    InventoryAuthorityService,
    InventoryDefinitionRegistry,
    InventoryProjector,
    ItemDefinition,
)
from app.gameplay.modifier_runtime import ModifierDefinitionRegistry, ModifierStateProjector, ModifierTemplate
from app.gameplay.resource_body_runtime import BodyRuntimeProjection
from app.gameplay.prediction_authority import PredictionAuthority


ACTOR = "actor:equipment-recovery"


def _body() -> BodyRuntimeProjection:
    return BodyRuntimeProjection(ACTOR, {}, {}, {f"gameplay:body:{ACTOR}": 0}, "body:test")


def _registries() -> tuple[InventoryDefinitionRegistry, EquipmentDefinitionRegistry, AbilityDefinitionRegistry, ModifierDefinitionRegistry]:
    inventory = InventoryDefinitionRegistry()
    inventory.register_item(ItemDefinition("item:sword", "1", 3, 2))
    equipment = EquipmentDefinitionRegistry()
    equipment.register_profile(
        "item:sword",
        EquipmentProfile("profile:sword", ("right_hand",), (), ("path:sword-swing",), ("modifier-template:sword-power",)),
    )
    abilities = AbilityDefinitionRegistry()
    abilities.register_skill(AbilitySkillDefinition("skill:sword", "1"))
    abilities.register_path(AbilityPathDefinition("path:sword-swing", "skill:sword", "action:sword-swing"))
    modifiers = ModifierDefinitionRegistry()
    modifiers.register_template(ModifierTemplate("modifier-template:sword-power", "combat.power", "additive", Decimal("2"), "sword-power"))
    return inventory, equipment, abilities, modifiers


def _seed(store, inventory_registry) -> None:
    inventory = InventoryAuthorityService(store=store, registry=inventory_registry)
    for command_id, container_id in (("bag", "container:bag"), ("hand", "container:hand")):
        assert inventory.create_container(
            command_id=f"cmd:{command_id}", actor_ref=ACTOR,
            spec=ContainerSpec(container_id, 20, 20, 4), idempotency_key=command_id,
            causation_id="cause", correlation_id="corr",
        ).committed
    assert inventory.instantiate(
        command_id="cmd:sword", actor_ref=ACTOR, item_id="item:sword:1", definition_id="item:sword",
        quantity=1, container_id="container:bag", idempotency_key="sword", causation_id="cause", correlation_id="corr",
    ).committed


def _service(store):
    inventory, equipment, abilities, modifiers = _registries()
    return (
        inventory,
        abilities,
        EquipmentAuthorityService(
            store=store, inventory_registry=inventory, equipment_registry=equipment,
            ability_registry=abilities, modifier_registry=modifiers,
            slots=(EquipmentSlotDefinition("right_hand", ("grip.right",)),),
        ),
    )


def test_equipment_durable_reopen_replays_receipt_and_unequip_preserves_learning(tmp_path) -> None:
    path = tmp_path / "equipment.sqlite"
    store = DurableGameplayEventStore(path)
    inventory_registry, abilities, equipment = _service(store)
    _seed(store, inventory_registry)
    assert AbilityAuthorityService(store=store, registry=abilities).learn(
        command_id="cmd:learn", actor_ref=ACTOR, skill_id="skill:sword", rank="basic", source_ref="lesson:1",
        idempotency_key="learn", causation_id="cause", correlation_id="corr",
    ).committed
    assert PredictionAuthority(store=store).open(
        prediction_id="prediction:equip", command_id="cmd:equip", actor_ref=ACTOR,
        operation="equipment_overlay", idempotency_key="prediction:open",
    ).committed
    first = equipment.equip(
        command_id="cmd:equip", actor_ref=ACTOR, item_id="item:sword:1", source_container_id="container:bag",
        slot_key="right_hand", body=_body(), idempotency_key="equip", causation_id="cause", correlation_id="corr",
    )
    assert first.committed
    store.close()

    reopened = DurableGameplayEventStore(path)
    inventory_registry, abilities, equipment = _service(reopened)
    replay = equipment.equip(
        command_id="cmd:equip", actor_ref=ACTOR, item_id="item:sword:1", source_container_id="container:bag",
        slot_key="right_hand", body=_body(), idempotency_key="equip", causation_id="cause", correlation_id="corr",
    )
    assert replay.idempotency_status == "duplicate_replayed"
    prediction = PredictionAuthority(store=reopened)
    confirmed = prediction.confirm(
        prediction_id="prediction:equip", idempotency_key="prediction:confirm",
        owner_principal="actor_gameplay.equipment_domain", owner_idempotency_key=f"{ACTOR}:equip",
    )
    assert confirmed.committed
    assert prediction.state("prediction:equip").owner_transaction_id == first.transaction_id
    assert prediction.replay("prediction:equip") == prediction.replay("prediction:equip", checkpoint_at=1)
    assert prediction.confirm(
        prediction_id="prediction:equip", idempotency_key="prediction:confirm",
        owner_principal="actor_gameplay.equipment_domain", owner_idempotency_key=f"{ACTOR}:equip",
    ).idempotency_status == "duplicate_replayed"
    assert EquipmentProjector().rebuild(ACTOR, reopened.read_events()).active_by_slot == {"right_hand": "activation:cmd:equip"}

    ended = equipment.unequip(
        command_id="cmd:unequip", actor_ref=ACTOR, activation_id="activation:cmd:equip",
        destination_container_id="container:hand", body=_body(), idempotency_key="unequip",
        causation_id="cause", correlation_id="corr",
    )
    assert ended.committed
    projection = AbilityStateProjector(abilities).rebuild(ACTOR, reopened.read_events())
    assert projection.learned["skill:sword"].rank == "basic"
    assert projection.grants["ability-grant:activation:cmd:equip:path:sword-swing"].status == "revoked"
    assert ModifierStateProjector(_registries()[3]).rebuild(ACTOR, reopened.read_events()).active_modifiers == {}
    assert InventoryProjector(inventory_registry).rebuild(ACTOR, reopened.read_events()).locations == {"item:sword:1": "container:hand"}
    reopened.close()
