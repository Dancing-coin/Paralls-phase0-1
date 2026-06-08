from typing import Literal

from pydantic import BaseModel, Field


class RawFactSource(BaseModel):
    layer: str = "L1"
    system: str
    actor_id: str = ""
    object_id: str = ""
    environment_id: str = ""


class RawFactTargets(BaseModel):
    actor_id: str = ""
    object_id: str = ""
    environment_id: str = ""


class RawFactWorld(BaseModel):
    position: list[float] | None = None
    distance_m: float | None = None
    state_before: str = ""
    state_after: str = ""


class RawFactObservability(BaseModel):
    visual: bool = False
    auditory: bool = False
    occluded: bool = False


class RawFactAcoustics(BaseModel):
    loudness_band: str = ""
    speech_mode: str = ""
    reachability: str = ""
    ambient_noise: str = ""


class RawFactEvent(BaseModel):
    event_type: str = "raw_fact_event"
    fact_family: str
    fact_type: str
    relation_type: str = ""
    producer_ts: int
    room_id: str
    scene_id: str
    zone_id: str
    source: RawFactSource
    targets: RawFactTargets
    world: RawFactWorld = Field(default_factory=RawFactWorld)
    observability: RawFactObservability = Field(default_factory=RawFactObservability)
    acoustics: RawFactAcoustics = Field(default_factory=RawFactAcoustics)
    effect_kind: Literal["set", "clear", "replace", "pulse"] = "pulse"
    subject_key: str = ""
    ttl_ms: int | None = None
    causation_id: str = ""
    correlation_id: str = ""
