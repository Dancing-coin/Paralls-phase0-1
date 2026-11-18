"""司命真相门禁镜像；这些记录不是 Owner 世界事实。"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

FactPhase = Literal['T0', 'T1', 'T2', 'T3']


class SimingLockedFact(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fact_id: str
    value: JsonValue
    world_anchor_id: str = ''
    state_key: str = ''
    category: Literal['foundation', 'case', 'session'] = 'session'
    producer_ts: int
    source_event_id: str
    evidence_refs: list[str] = Field(default_factory=list)
    source_event_refs: list[str] = Field(default_factory=list)


class SimingFactSource(BaseModel):
    model_config = ConfigDict(extra='forbid')
    producer_ts: int
    digest: str


class SimingFactCoreState(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal[1] = 1
    room_id: str
    scene_id: str
    phase: FactPhase = 'T0'
    last_ts: int | None = None
    facts: dict[str, SimingLockedFact] = Field(default_factory=dict)
    sources: dict[str, SimingFactSource] = Field(default_factory=dict)
    evidence_sources: dict[str, str] = Field(default_factory=dict)
