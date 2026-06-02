from app.models.player_input import FocusTargetChange
from app.services.focus_state_service import FocusStateService


def test_focus_state_service_tracks_latest_focus_for_actor() -> None:
    service = FocusStateService()
    event = FocusTargetChange(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="focus_target_change",
        producer_ts=10,
        target_object_id="obj_letter",
    )

    state = service.update_focus(event)

    assert state["actor_id"] == "char_c"
    assert state["scene_id"] == "scene_demo"
    assert state["zone_id"] == "zone_focus"
    assert state["target_object_id"] == "obj_letter"
    assert service.get_focus("char_c") == state
