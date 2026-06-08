from pydantic import BaseModel, Field


class WorldExecutionResult(BaseModel):
    request_id: str
    result_type: str
    payload: dict[str, object] = Field(default_factory=dict)
