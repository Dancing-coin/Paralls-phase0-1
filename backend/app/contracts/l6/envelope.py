from pydantic import BaseModel, Field


class EnvelopeContract(BaseModel):
    message_type: str
    payload: dict[str, object] = Field(default_factory=dict)
