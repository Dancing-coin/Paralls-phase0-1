from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.main as main
from app.gameplay.inventory_runtime import InventoryProjector
from app.models.player_input import PickupIntent, RetrieveIntent
from app.services.default_scene_pickup_policy import DefaultScenePickupPolicyService


def _pickup_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "player_id": "p1",
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "actor_id": "char_c",
        "intent_type": "pickup_intent",
        "producer_ts": 200,
        "target_object_id": "obj_archive_token",
    }
    payload.update(overrides)
    return payload


def _stow_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "player_id": "p1",
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "actor_id": "char_c",
        "intent_type": "stow_intent",
        "producer_ts": 201,
        "target_object_id": "obj_archive_token",
    }
    payload.update(overrides)
    return payload


def _retrieve_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "player_id": "p1",
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "actor_id": "char_c",
        "intent_type": "retrieve_intent",
        "producer_ts": 202,
        "target_object_id": "obj_archive_storage_chest",
    }
    payload.update(overrides)
    return payload


def test_default_scene_pickup_policy_resolves_only_reviewed_actor_context_and_range() -> None:
    service = DefaultScenePickupPolicyService.demo_defaults()

    accepted = service.resolve(
        target_object_id="obj_archive_token",
        interaction_type="grab",
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_position=(3.8, 0.7, -1.2),
    )
    wrong_actor = service.resolve(
        target_object_id="obj_archive_token",
        interaction_type="grab",
        actor_id="char_a",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_position=(3.8, 0.7, -1.2),
    )
    far = service.resolve(
        target_object_id="obj_archive_token",
        interaction_type="grab",
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_position=(30.0, 0.7, -1.2),
    )

    assert accepted.accepted is True
    assert accepted.policy is not None
    assert accepted.policy.asset_ref == "item:archive_token_01"
    assert accepted.actor_ref == "character:char_c"
    assert accepted.drop_target_ref == "character:char_c:hand"
    assert DefaultScenePickupPolicyService.inventory_destination_for(
        accepted.policy,
        "char_c",
    ) == "container:char_c:backpack"
    assert wrong_actor.error_code == "pickup_actor_not_allowed"
    assert far.error_code == "pickup_out_of_range"


def test_pickup_intent_forbids_client_world_reference_injection() -> None:
    with pytest.raises(ValidationError):
        PickupIntent(**_pickup_payload(asset_ref="item:other", source_holder_ref="world:fake"))


def test_retrieve_intent_forbids_client_inventory_or_receiver_reference_injection() -> None:
    with pytest.raises(ValidationError):
        RetrieveIntent(
            **_retrieve_payload(
                asset_ref="item:other",
                source_container_id="container:other",
                destination_receiver_ref="world:fake",
            )
        )


def test_websocket_default_scene_pickup_resolves_custody_from_backend_policy_only() -> None:
    main.reset_runtime_state()
    main.runtime._actor_positions["char_c"] = (3.8, 0.7, -1.2)
    client = TestClient(main.app)

    with client.websocket_connect("/ws") as websocket:
        websocket.send_json({"message_type": "player_input", "payload": _pickup_payload()})
        received = [websocket.receive_json() for _ in range(3)]

    ack, pickup_result, carry_place_event = received
    payload = carry_place_event["payload"]
    possession = main.embodied_carry_place_authority_service.possession_projection("item:archive_token_01")

    assert ack == {
        "message_type": "ack",
        "payload": {
            "accepted": True,
            "source_type": "player_input",
            "route": "default_scene_pickup_authority",
        },
    }
    assert pickup_result == {
        "message_type": "embodied_pickup_result",
        "payload": {
            "accepted": True,
            "target_object_id": "obj_archive_token",
            "interaction_type": "grab",
            "policy_revision": 1,
            "possession_semantics": "custody_only",
        },
    }
    assert carry_place_event["message_type"] == "embodied_carry_place_event"
    assert payload["event_type"] == "embodied.place.settled"
    assert payload["asset_ref"] == "item:archive_token_01"
    assert payload["source_holder_ref"] == "world:anchor:archive_token_pedestal_01"
    assert payload["drop_target_ref"] == "character:char_c:hand"
    assert payload["placement_directive"] == {
        "mode": "place_for_presentation",
        "asset_ref": "item:archive_token_01",
        "place_at_ref": "character:char_c:hand",
        "authority_only": True,
    }
    assert possession["custody_holder_ref"] == "character:char_c:hand"
    assert possession["owner_ref"] == "world:archive"


def test_default_scene_pickup_rejection_is_structured_and_does_not_mutate_custody() -> None:
    main.reset_runtime_state()
    client = TestClient(main.app)

    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": _pickup_payload(target_object_id="obj_unreviewed_prop"),
            }
        )
        ack = websocket.receive_json()
        rejection = websocket.receive_json()

    possession = main.embodied_carry_place_authority_service.possession_projection("item:archive_token_01")
    assert ack["payload"]["accepted"] is False
    assert ack["payload"]["route"] == "default_scene_pickup_authority"
    assert rejection == {
        "message_type": "embodied_pickup_result",
        "payload": {
            "accepted": False,
            "target_object_id": "obj_unreviewed_prop",
            "interaction_type": "grab",
            "constraint_type": "pickup_authority_constraint",
            "constraint_code": "pickup_target_unknown",
        },
    }
    assert possession["custody_holder_ref"] == "world:anchor:archive_token_pedestal_01"


def test_websocket_default_scene_stow_moves_picked_up_item_into_inventory_and_commits_three_events() -> None:
    main.reset_runtime_state()
    client = TestClient(main.app)

    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": {
                    "player_id": "p1",
                    "room_id": "room_demo",
                    "scene_id": "scene_demo",
                    "zone_id": "zone_focus",
                    "actor_id": "char_c",
                    "intent_type": "move_intent",
                    "producer_ts": 199,
                    "move_mode": "locomotion",
                    "target_point": [3.8, 0.7, -1.2],
                },
            }
        )
        move_ack = websocket.receive_json()
        runtime_snapshot = websocket.receive_json()

        websocket.send_json({"message_type": "player_input", "payload": _pickup_payload()})
        pickup_ack = websocket.receive_json()
        pickup_result = websocket.receive_json()
        carry_place_event = websocket.receive_json()

        websocket.send_json({"message_type": "player_input", "payload": _stow_payload()})
        stow_ack = websocket.receive_json()
        stow_result = websocket.receive_json()

    inventory = InventoryProjector(main.inventory_definition_registry).rebuild(
        "character:char_c",
        main.gameplay_event_store.read_events(),
    )
    possession = main.embodied_carry_place_authority_service.possession_projection("item:archive_token_01")
    transaction = main.gameplay_event_store.read_transactions()[-1]

    assert move_ack["payload"] == {
        "accepted": True,
        "source_type": "player_input",
        "route": "local_motion",
    }
    assert runtime_snapshot["message_type"] == "character_runtime_state_snapshot"
    assert runtime_snapshot["payload"]["actor_id"] == "char_c"
    assert pickup_ack["payload"]["accepted"] is True
    assert pickup_result["payload"]["accepted"] is True
    assert carry_place_event["message_type"] == "embodied_carry_place_event"
    assert stow_ack == {
        "message_type": "ack",
        "payload": {
            "accepted": True,
            "source_type": "player_input",
            "route": "default_scene_inventory_authority",
        },
    }
    assert stow_result["message_type"] == "embodied_inventory_stow_result"
    assert stow_result["payload"]["accepted"] is True
    assert stow_result["payload"]["target_object_id"] == "obj_archive_token"
    assert stow_result["payload"]["constraint_code"] == ""
    assert stow_result["payload"]["possession_semantics"] == "inventory_location"
    assert stow_result["payload"]["transaction_id"].startswith("tx:stow:char_c:obj_archive_token:201:")
    assert stow_result["payload"]["presentation_directive"] == {
        "mode": "inventory_stowed_for_presentation",
        "authority_only": True,
    }
    assert inventory.locations["item:archive_token_01"] == "container:char_c:backpack"
    assert possession["custody_holder_ref"] == "inventory:container:character:char_c:container:char_c:backpack"
    assert [event.event_type for event in transaction.events] == [
        "inventory.custody_changed",
        "gameplay.inventory.item_transferred_in",
        "scene.occupancy.changed",
        "embodied.inventory.stowed",
    ]
    assert all(event.transaction_id == stow_result["payload"]["transaction_id"] for event in transaction.events)
    assert transaction.events[1].payload["to_container_id"] == "container:char_c:backpack"
    assert main.embodied_carry_place_authority_service.drop_target_projection(
        "character:char_c:hand"
    )["occupied_by_ref"] == ""


def test_websocket_default_scene_retrieve_resolves_container_item_and_receiver_from_backend_policy() -> None:
    main.reset_runtime_state()
    client = TestClient(main.app)

    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": {
                    "player_id": "p1",
                    "room_id": "room_demo",
                    "scene_id": "scene_demo",
                    "zone_id": "zone_focus",
                    "actor_id": "char_c",
                    "intent_type": "move_intent",
                    "producer_ts": 199,
                    "move_mode": "locomotion",
                    "target_point": [3.8, 0.7, -1.2],
                },
            }
        )
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_json({"message_type": "player_input", "payload": _pickup_payload()})
        [websocket.receive_json() for _ in range(3)]
        websocket.send_json({"message_type": "player_input", "payload": _stow_payload()})
        websocket.receive_json()
        websocket.receive_json()

        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": {
                    "player_id": "p1",
                    "room_id": "room_demo",
                    "scene_id": "scene_demo",
                    "zone_id": "zone_focus",
                    "actor_id": "char_c",
                    "intent_type": "move_intent",
                    "producer_ts": 201,
                    "move_mode": "locomotion",
                    "target_point": [1.2, 0.7, -1.2],
                },
            }
        )
        websocket.receive_json()
        websocket.send_json({"message_type": "player_input", "payload": _retrieve_payload()})
        ack = websocket.receive_json()
        retrieve_result = websocket.receive_json()

    inventory = InventoryProjector(main.inventory_definition_registry).rebuild(
        "character:char_c", main.gameplay_event_store.read_events()
    )
    possession = main.embodied_carry_place_authority_service.possession_projection("item:archive_token_01")
    transaction = main.gameplay_event_store.read_transactions()[-1]

    assert ack["payload"] == {
        "accepted": True,
        "source_type": "player_input",
        "route": "default_scene_inventory_authority",
    }
    assert retrieve_result["message_type"] == "embodied_inventory_retrieve_result"
    assert retrieve_result["payload"] == {
        "accepted": True,
        "target_object_id": "obj_archive_storage_chest",
        "constraint_code": "",
        "transaction_id": retrieve_result["payload"]["transaction_id"],
        "possession_semantics": "custody_only",
        "asset_ref": "item:archive_token_01",
        "presentation_directive": {
            "mode": "inventory_retrieved_for_presentation",
            "authority_only": True,
        },
    }
    assert retrieve_result["payload"]["transaction_id"].startswith(
        "tx:retrieve:char_c:obj_archive_storage_chest:202:"
    )
    assert inventory.locations == {}
    assert possession["custody_holder_ref"] == "character:char_c:hand"
    assert [event.event_type for event in transaction.events] == [
        "inventory.custody_changed",
        "gameplay.inventory.item_transferred_out",
        "scene.occupancy.changed",
        "embodied.inventory.retrieved",
    ]


@pytest.mark.parametrize(
    ("overrides", "constraint_code"),
    [
        ({"target_object_id": "obj_unreviewed_container"}, "retrieve_target_unknown"),
        ({"room_id": "room_other"}, "retrieve_context_mismatch"),
    ],
)
def test_websocket_default_scene_retrieve_rejects_unreviewed_or_wrong_context_without_mutation(
    overrides: dict[str, object], constraint_code: str
) -> None:
    main.reset_runtime_state()
    main.runtime._actor_positions["char_c"] = (1.2, 0.7, -1.2)
    client = TestClient(main.app)

    with client.websocket_connect("/ws") as websocket:
        websocket.send_json({"message_type": "player_input", "payload": _retrieve_payload(**overrides)})
        ack = websocket.receive_json()
        rejection = websocket.receive_json()

    assert ack["payload"]["accepted"] is False
    assert ack["payload"]["route"] == "default_scene_inventory_authority"
    assert rejection["message_type"] == "embodied_inventory_retrieve_result"
    assert rejection["payload"]["accepted"] is False
    assert rejection["payload"]["constraint_code"] == constraint_code
    assert rejection["payload"].get("presentation_directive", {}) == {}


def test_websocket_default_scene_stow_rejects_when_item_is_not_in_actor_custody() -> None:
    main.reset_runtime_state()
    client = TestClient(main.app)

    with client.websocket_connect("/ws") as websocket:
        websocket.send_json({"message_type": "player_input", "payload": _stow_payload()})
        ack = websocket.receive_json()
        rejection = websocket.receive_json()

    inventory = InventoryProjector(main.inventory_definition_registry).rebuild(
        "character:char_c",
        main.gameplay_event_store.read_events(),
    )
    possession = main.embodied_carry_place_authority_service.possession_projection("item:archive_token_01")

    assert ack == {
        "message_type": "ack",
        "payload": {
            "accepted": False,
            "source_type": "player_input",
            "route": "default_scene_inventory_authority",
        },
    }
    assert rejection["message_type"] == "embodied_inventory_stow_result"
    assert rejection["payload"]["accepted"] is False
    assert rejection["payload"]["target_object_id"] == "obj_archive_token"
    assert rejection["payload"]["constraint_code"] == "source_custody_mismatch"
    assert rejection["payload"]["transaction_id"] == ""
    assert rejection["payload"]["possession_semantics"] == ""
    assert rejection["payload"].get("presentation_directive", {}) == {}
    assert inventory.items == {}
    assert possession["custody_holder_ref"] == "world:anchor:archive_token_pedestal_01"


@pytest.mark.parametrize(
    ("overrides", "constraint_code"),
    [
        ({"room_id": "room_other"}, "pickup_context_mismatch"),
        ({"actor_id": "char_a"}, "pickup_actor_not_allowed"),
        ({"target_object_id": "obj_unreviewed_prop"}, "pickup_target_unknown"),
    ],
)
def test_websocket_default_scene_stow_rejects_invalid_context_actor_or_target(
    overrides: dict[str, object],
    constraint_code: str,
) -> None:
    main.reset_runtime_state()
    client = TestClient(main.app)

    with client.websocket_connect("/ws") as websocket:
        websocket.send_json({"message_type": "player_input", "payload": _stow_payload(**overrides)})
        ack = websocket.receive_json()
        rejection = websocket.receive_json()

    assert ack == {
        "message_type": "ack",
        "payload": {
            "accepted": False,
            "source_type": "player_input",
            "route": "default_scene_inventory_authority",
        },
    }
    assert rejection["message_type"] == "embodied_inventory_stow_result"
    assert rejection["payload"]["accepted"] is False
    assert rejection["payload"]["target_object_id"] == str(
        overrides.get("target_object_id", "obj_archive_token")
    )
    assert rejection["payload"]["constraint_code"] == constraint_code
    assert rejection["payload"]["transaction_id"] == ""
    assert rejection["payload"]["possession_semantics"] == ""
    assert rejection["payload"].get("presentation_directive", {}) == {}


def test_websocket_default_scene_stow_rejects_extra_payload_fields_via_pydantic_validation() -> None:
    main.reset_runtime_state()
    client = TestClient(main.app)

    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": _stow_payload(source_holder_ref="character:char_c:hand"),
            }
        )
        error_ack = websocket.receive_json()

    assert error_ack["message_type"] == "ack"
    assert error_ack["payload"]["accepted"] is False
    assert error_ack["payload"]["source_type"] == "player_input"
    assert error_ack["payload"]["route"] == "invalid_payload"
    assert error_ack["payload"]["error_type"] == "ValidationError"
    assert "Extra inputs are not permitted" in error_ack["payload"]["error_message"]
    assert "source_holder_ref" in error_ack["payload"]["error_message"]
