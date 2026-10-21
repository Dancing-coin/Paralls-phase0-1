from __future__ import annotations

from types import MappingProxyType
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ThoughtModeDescriptor(BaseModel):
    """Registered input projection and information policy, never an executor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode_id: str = Field(min_length=1)
    activation_conditions: tuple[str, ...] = ()
    input_projection: tuple[str, ...] = ()
    domain: str = Field(min_length=1)
    question_schema: tuple[str, ...] = ()
    allowed_intents: tuple[str, ...] = ()
    priority_bias: float = Field(default=0.0, ge=0.0, le=1.0)
    resource_horizon: Literal["instant", "scene", "arc", "long_term"] = "scene"
    information_needs: tuple[str, ...] = ()
    information_request_types: tuple[str, ...] = ()
    exit_conditions: tuple[str, ...] = ()

    @field_validator(
        "activation_conditions", "input_projection", "question_schema", "allowed_intents",
        "information_needs", "information_request_types", "exit_conditions", mode="before"
    )
    @classmethod
    def normalize_lists(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            return (value,)
        return tuple(str(item) for item in value)  # type: ignore[arg-type]


class ThoughtModeRegistry:
    def __init__(self, descriptors: Mapping[str, ThoughtModeDescriptor] | None = None) -> None:
        self._descriptors = dict(descriptors or {})

    def register(self, descriptor: ThoughtModeDescriptor) -> None:
        if descriptor.mode_id in self._descriptors:
            raise ValueError(f"duplicate thought mode: {descriptor.mode_id}")
        self._descriptors[descriptor.mode_id] = descriptor

    def get(self, mode_id: str) -> ThoughtModeDescriptor:
        try:
            return self._descriptors[mode_id]
        except KeyError:
            raise KeyError(f"unknown thought mode: {mode_id}") from None

    def project_active(
        self, mode_ids: tuple[str, ...] | list[str], *, background_goals: tuple[str, ...] = ()
    ) -> tuple[ThoughtModeDescriptor, ...]:
        background = set(background_goals)
        projected: list[ThoughtModeDescriptor] = []
        for mode_id in dict.fromkeys(mode_ids):
            if mode_id in background and mode_id not in self._descriptors:
                continue
            projected.append(self.get(mode_id))
        return tuple(projected)

    @property
    def descriptors(self) -> Mapping[str, ThoughtModeDescriptor]:
        return MappingProxyType(dict(self._descriptors))
