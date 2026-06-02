from app.models.player_input import FocusTargetChange


class FocusStateService:
    def __init__(self) -> None:
        self._focus_by_actor: dict[str, dict[str, str]] = {}

    def update_focus(self, event: FocusTargetChange) -> dict[str, str]:
        state = {
            "room_id": event.room_id,
            "scene_id": event.scene_id,
            "zone_id": event.zone_id,
            "actor_id": event.actor_id,
            "target_actor_id": event.target_actor_id or "",
            "target_object_id": event.target_object_id or "",
            "producer_ts": str(event.producer_ts),
        }
        self._focus_by_actor[event.actor_id] = state
        return state

    def get_focus(self, actor_id: str) -> dict[str, str] | None:
        return self._focus_by_actor.get(actor_id)
