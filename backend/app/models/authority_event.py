from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Priority = Literal["p0", "p1", "p2", "p3"]
Durability = Literal["replayable", "reliable", "realtime"]


class AuthorityEventSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer: str
    system: str
    actor_id: str | None = None


class AuthorityEventRouting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audience_mode: str
    routing_mode: str
    target_ids: list[str] = Field(default_factory=list)


class AuthorityEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: str
    producer_ts: int
    room_id: str
    scene_id: str
    zone_id: str
    source: AuthorityEventSource
    routing: AuthorityEventRouting
    priority: Priority
    ttl: int | None = None
    durability: Durability
    causation_id: str
    correlation_id: str
    payload: dict[str, Any]

    @model_validator(mode="before")
    @classmethod
    def reject_forbidden_public_envelope_fields(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value

        forbidden = {
            "world_ts",
            "sim_tick_ts",
            "producer",
            "source_actor_id",
            "target_actor_ids",
        }
        present = sorted(forbidden.intersection(value.keys()))
        if present:
            joined = ", ".join(present)
            raise ValueError(f"forbidden authority envelope field(s): {joined}")
        return value
