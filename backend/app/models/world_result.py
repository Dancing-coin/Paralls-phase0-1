from pydantic import BaseModel


class WorldResultBase(BaseModel):
    request_ref: str = ""
    result_id: str = ""
    room_id: str
    scene_id: str = "scene_demo"
    zone_id: str = "zone_focus"
    actor_id: str = ""
    source_type: str
    result_type: str
    causation_id: str
    correlation_id: str = ""
    producer_ts: int
    target_object_id: str | None = None
    target_environment_id: str | None = None
    settlement_status: str = ""


class ActionResolutionResult(WorldResultBase):
    result_type: str = "action_resolution_result"
    resolution_status: str = ""
    resolved_entities: list[str] = []
    applied_state_changes: list[str] = []
    stable_state_summary: str = ""


class EnvironmentStateResult(WorldResultBase):
    result_type: str = "environment_state_result"
    previous_state: str
    current_state: str
    change_summary: str
    affected_zone_ids: list[str] = []
    field_delta_summary: list[str] = []
    temperature: str = "ambient"
    humidity: str = "stable"
    smoke_density: str = "clear"
    light_level: str = "normal"
    noise_level: str = "quiet"
    visibility_level: str = "clear"


class ObjectStateResult(WorldResultBase):
    result_type: str = "object_state_result"
    previous_state: str
    current_state: str
    change_summary: str


class VisibleFeedbackResult(WorldResultBase):
    result_type: str = "visible_feedback_result"
    feedback_mode: str
    feedback_payload: str


class BodyStateResult(WorldResultBase):
    result_type: str = "body_state_result"
    body_state_class: str
    previous_state: str
    current_state: str
    change_summary: str


class ConstraintStateResult(WorldResultBase):
    result_type: str = "constraint_state_result"
    constraint_type: str
    constraint_code: str = ""
    constraint_summary: str
    blocking_entity_refs: list[str] = []
