from pydantic import BaseModel


class EnvironmentFieldState(BaseModel):
    field_id: str = ""
    room_id: str
    scene_id: str = "scene_demo"
    zone_id: str
    temperature: str = "ambient"
    humidity: str = "stable"
    smoke_density: str = "clear"
    light_level: str = "normal"
    noise_level: str = "quiet"
    visibility_level: str = "clear"
    producer_ts: int = 0
    updated_at: int = 0
    source_environment_id: str = ""
