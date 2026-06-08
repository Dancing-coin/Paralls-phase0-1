from pydantic import BaseModel


class EnvironmentFieldState(BaseModel):
    room_id: str
    zone_id: str
    light_level: str = "normal"
    noise_level: str = "quiet"
    producer_ts: int = 0
    source_environment_id: str = ""
