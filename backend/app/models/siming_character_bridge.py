from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


BridgeBand = Literal["impulse", "opportunity", "fact_reveal"]
BridgeInputType = Literal["siming_high_level_message"]
DeliveryStatus = Literal[
    "accepted",
    "rejected",
    "deferred",
    "suggested_only",
    "rejected_by_filter",
    "blocked_by_world_constraint",
    "expired",
    "unroutable",
    "target_unavailable",
]


class SimingCharacterCompatibilityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    delivery_id: str
    actor_id: str
    input_type: BridgeInputType
    band: BridgeBand
    producer_ts: int
    room_id: str
    scene_id: str
    zone_id: str
    causation_id: str
    correlation_id: str
    presentation_hint: str | None = None
    target_actor_id: str | None = None
    target_object_id: str | None = None
    target_environment_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_forbidden_low_level_fields(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value

        forbidden = {
            "go_to_position",
            "kill_target_now",
            "believe_X_now",
            "choose_Y_now",
            "physical_success",
        }
        present = sorted(forbidden.intersection(value.keys()))
        if present:
            raise ValueError(f"forbidden compatibility input field(s): {', '.join(present)}")
        return value


class CharacterDeliveryAuditSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    delivery_id: str
    actor_id: str
    status: DeliveryStatus
    producer_ts: int
    causation_id: str
    correlation_id: str
