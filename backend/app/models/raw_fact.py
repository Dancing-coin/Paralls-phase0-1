from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.capture_clock import (
    DEFAULT_CLOCK_DOMAIN,
    derive_capture_id,
    derive_capture_root_id,
    derive_sample_ref_id,
    normalize_clock_domain,
)
from app.models.object_anchor import (
    append_unique_lineage,
    derive_world_anchor_id,
    subject_ref_from_event_parts,
    target_ref_from_event_parts,
)


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
    capture_root_id: str = ""
    capture_id: str = ""
    clock_domain: str = ""
    monotonic_tick: int | None = None
    source_frame_index: int | None = None
    wall_clock_ts: int | None = None
    sample_ref_id: str = ""
    world_anchor_id: str = ""
    subject_ref: str = ""
    target_ref: str = ""
    source_ref_lineage: list[str] = Field(default_factory=list)
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

    @model_validator(mode="after")
    def populate_capture_clock_contract(self) -> "RawFactEvent":
        if self.monotonic_tick is None:
            self.monotonic_tick = self.producer_ts
        if self.wall_clock_ts is None:
            self.wall_clock_ts = self.producer_ts
        if self.clock_domain == "":
            self.clock_domain = DEFAULT_CLOCK_DOMAIN
        else:
            self.clock_domain = normalize_clock_domain(self.clock_domain)
        if self.capture_root_id == "":
            self.capture_root_id = derive_capture_root_id(
                clock_domain=self.clock_domain,
                room_id=self.room_id,
                scene_id=self.scene_id,
                zone_id=self.zone_id,
                monotonic_tick=self.monotonic_tick,
            )
        if self.capture_id == "":
            subject_id = (
                self.source.actor_id
                or self.source.object_id
                or self.source.environment_id
                or self.targets.actor_id
                or self.targets.object_id
                or self.targets.environment_id
                or "world"
            )
            self.capture_id = derive_capture_id(
                capture_root_id=self.capture_root_id,
                consumer_scope="fact",
                subject_id=subject_id,
            )
        if self.sample_ref_id == "":
            self.sample_ref_id = derive_sample_ref_id(
                capture_root_id=self.capture_root_id,
                source_kind=self.fact_family,
                source_ref=f"{self.fact_type}:{self.producer_ts}",
            )
        if self.subject_ref == "":
            self.subject_ref = subject_ref_from_event_parts(
                source_actor_id=self.source.actor_id,
                source_object_id=self.source.object_id,
                source_environment_id=self.source.environment_id,
            )
        if self.target_ref == "":
            self.target_ref = target_ref_from_event_parts(
                target_actor_id=self.targets.actor_id,
                target_object_id=self.targets.object_id,
                target_environment_id=self.targets.environment_id,
            )
        if self.world_anchor_id == "":
            self.world_anchor_id = derive_world_anchor_id(target_ref=self.target_ref)
        self.source_ref_lineage = append_unique_lineage(
            self.source_ref_lineage,
            [self.sample_ref_id, f"raw_fact_event:{self.fact_family}:{self.fact_type}:{self.producer_ts}"],
        )
        return self
