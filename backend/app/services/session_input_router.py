from app.models.player_input import DialogueSubmit, FocusTargetChange, InteractIntent, MoveIntent


class SessionInputRouter:
    """Routes structured session input; it is not a runtime host."""

    def __init__(self) -> None:
        self._actor_positions: dict[str, tuple[float, float, float]] = {}

    def accept_player_input(self, event: MoveIntent | DialogueSubmit | InteractIntent | FocusTargetChange) -> dict[str, object]:
        if event.intent_type == "dialogue_submit":
            return {"accepted": True, "route": "character_service"}
        if event.intent_type == "interact_intent":
            return {"accepted": True, "route": "esm_service"}
        if event.intent_type == "move_intent":
            if event.target_point is not None:
                self._actor_positions[event.actor_id] = tuple(event.target_point)
            return {"accepted": True, "route": "local_motion"}
        if event.intent_type == "focus_target_change":
            return {"accepted": True, "route": "character_service"}
        return {"accepted": False, "route": "unknown"}

    def get_actor_position(self, actor_id: str) -> tuple[float, float, float] | None:
        return self._actor_positions.get(actor_id)
