from pydantic import BaseModel, Field


class ActionRequest(BaseModel):
    request_id: str
    actor_id: str
    action_type: str
    target_actor_id: str = ""
    target_object_id: str = ""
    target_environment_id: str = ""
    payload: dict[str, object] = Field(default_factory=dict)
