from pydantic import BaseModel, Field


class PresentationCommand(BaseModel):
    command_id: str
    actor_id: str
    command_type: str
    payload: dict[str, object] = Field(default_factory=dict)
