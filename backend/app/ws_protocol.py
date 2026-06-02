from pydantic import BaseModel


class Envelope(BaseModel):
    message_type: str
    payload: dict
