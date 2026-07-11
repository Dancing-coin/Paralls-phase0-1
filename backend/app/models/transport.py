from pydantic import BaseModel, Field


class TransportBarrier(BaseModel):
    request_id: str = Field(min_length=1)
    producer_ts: int
