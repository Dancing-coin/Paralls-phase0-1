from pydantic import BaseModel, ConfigDict


class PlayerInputBase(BaseModel):
    player_id: str
    room_id: str
    scene_id: str = "scene_demo"
    zone_id: str = "zone_focus"
    actor_id: str
    intent_type: str
    producer_ts: int
    request_id: str = ""


class MoveIntent(PlayerInputBase):
    intent_type: str = "move_intent"
    move_mode: str
    target_point: tuple[float, float, float] | None = None


class DialogueSubmit(PlayerInputBase):
    intent_type: str = "dialogue_submit"
    target_actor_id: str
    content: str
    context_hint: str | None = None


class InteractIntent(PlayerInputBase):
    intent_type: str = "interact_intent"
    target_object_id: str
    interaction_type: str


class PickupIntent(PlayerInputBase):
    """A semantic pickup request whose world references are backend-resolved."""

    model_config = ConfigDict(extra="forbid")

    intent_type: str = "pickup_intent"
    target_object_id: str
    interaction_type: str = "grab"


class StowIntent(PlayerInputBase):
    model_config = ConfigDict(extra="forbid")

    intent_type: str = "stow_intent"
    target_object_id: str


class RetrieveIntent(PlayerInputBase):
    """A reviewed scene-container request with backend-selected inventory refs."""

    model_config = ConfigDict(extra="forbid")

    intent_type: str = "retrieve_intent"
    target_object_id: str


class FocusTargetChange(PlayerInputBase):
    intent_type: str = "focus_target_change"
    target_actor_id: str | None = None
    target_object_id: str | None = None
