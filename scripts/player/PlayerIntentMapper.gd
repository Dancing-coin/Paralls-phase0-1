extends Node

@export var player_actor_id := "char_c"
@export var player_id := "p1"
@export var room_id := "room_demo"
@export var scene_id := "scene_demo"
@export var zone_id := "zone_focus"

func emit_dialogue_submit(target_actor_id: String, content: String) -> Dictionary:
    return {
        "message_type": "player_input",
        "payload": {
            "player_id": player_id,
            "room_id": room_id,
            "scene_id": scene_id,
            "zone_id": zone_id,
            "actor_id": player_actor_id,
            "intent_type": "dialogue_submit",
            "producer_ts": Time.get_ticks_msec(),
            "target_actor_id": target_actor_id,
            "content": content,
        }
    }

func emit_interact_intent(target_object_id: String, interaction_type: String) -> Dictionary:
    return {
        "message_type": "player_input",
        "payload": {
            "player_id": player_id,
            "room_id": room_id,
            "scene_id": scene_id,
            "zone_id": zone_id,
            "actor_id": player_actor_id,
            "intent_type": "interact_intent",
            "producer_ts": Time.get_ticks_msec(),
            "target_object_id": target_object_id,
            "interaction_type": interaction_type,
        }
    }

func emit_focus_target_change(target_actor_id: String = "", target_object_id: String = "") -> Dictionary:
    var payload := {
        "player_id": player_id,
        "room_id": room_id,
        "scene_id": scene_id,
        "zone_id": zone_id,
        "actor_id": player_actor_id,
        "intent_type": "focus_target_change",
        "producer_ts": Time.get_ticks_msec(),
    }
    if target_actor_id != "":
        payload["target_actor_id"] = target_actor_id
    if target_object_id != "":
        payload["target_object_id"] = target_object_id
    return {
        "message_type": "player_input",
        "payload": payload,
    }

func emit_move_intent(move_mode: String, target_point: Vector3) -> Dictionary:
    return {
        "message_type": "player_input",
        "payload": {
            "player_id": player_id,
            "room_id": room_id,
            "scene_id": scene_id,
            "zone_id": zone_id,
            "actor_id": player_actor_id,
            "intent_type": "move_intent",
            "producer_ts": Time.get_ticks_msec(),
            "move_mode": move_mode,
            "target_point": [target_point.x, target_point.y, target_point.z],
        }
    }

func emit_visual_fact_event(fact_type: String, relation_type: String, target_actor_id: String = "", target_object_id: String = "") -> Dictionary:
    var payload := {
        "actor_id": player_actor_id,
        "room_id": room_id,
        "scene_id": scene_id,
        "zone_id": zone_id,
        "producer_ts": Time.get_ticks_msec(),
        "fact_type": fact_type,
        "relation_type": relation_type,
    }
    if target_actor_id != "":
        payload["target_actor_id"] = target_actor_id
    if target_object_id != "":
        payload["target_object_id"] = target_object_id
    return {
        "message_type": "visual_fact_event",
        "payload": payload,
    }
