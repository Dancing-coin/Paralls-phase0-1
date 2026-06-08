from pydantic import BaseModel


class ExecutionAck(BaseModel):
    request_id: str
    accepted: bool
    execution_lane: str
    rejection_reason: str = ""
