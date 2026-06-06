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
    causation_id: str = ""
    correlation_id: str = ""
