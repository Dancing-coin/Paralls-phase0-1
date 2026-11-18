from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FactType(StrEnum):
    WORLD_FACT = "world_fact_event"
    VISUAL_FACT = "visual_fact_event"
    ESM_RESULT = "esm_result_event"
    CHARACTER_BEHAVIOR = "character_behavior_event"
    CONVERSATION_RESOLUTION = "conversation_resolution_event"
    CONSTRAINT_STATE = "constraint_state_event"
    POPULATION_CADENCE = "population_cadence_event"
    DAILY_RHYTHM_FATIGUE_STATE = "daily_rhythm.fatigue_state"
    DAILY_RHYTHM_NEED_PRESSURE_STATE = "daily_rhythm.need_pressure_state"
    DAILY_RHYTHM_STARVATION_CREDIT_STATE = "daily_rhythm.starvation_credit_state"
    DAILY_RHYTHM_ACTIVITY_PHASE_STATE = "daily_rhythm.activity_phase_state"

    @classmethod
    def from_event_type(cls, event_type: str) -> "FactType | None":
        try:
            return cls(event_type)
        except ValueError:
            return None

    def to_event_type(self) -> str:
        return self.value


_DOMAINS = {
    FactType.WORLD_FACT: "world",
    FactType.VISUAL_FACT: "visual",
    FactType.ESM_RESULT: "esm_world",
    FactType.CHARACTER_BEHAVIOR: "character",
    FactType.CONVERSATION_RESOLUTION: "conversation",
    FactType.CONSTRAINT_STATE: "esm_world",
    FactType.POPULATION_CADENCE: "population",
    FactType.DAILY_RHYTHM_FATIGUE_STATE: "daily_rhythm",
    FactType.DAILY_RHYTHM_NEED_PRESSURE_STATE: "daily_rhythm",
    FactType.DAILY_RHYTHM_STARVATION_CREDIT_STATE: "daily_rhythm",
    FactType.DAILY_RHYTHM_ACTIVITY_PHASE_STATE: "daily_rhythm",
}

_GAMEPLAY_FACT_DOMAINS = {
    "gameplay.inventory.item_moved": "inventory",
    "gameplay.organization.production_work_contribution_accepted": "organization",
    "gameplay.ownership.right_transferred": "ownership",
    "gameplay.economy.account_credited": "economy",
    "gameplay.survival.obligation_settled": "survival_body",
    "gameplay.survival.body_changed": "survival_body",
    "gameplay.resource.capability_committed": "resource_scene",
    "gameplay.scene.result_committed": "resource_scene",
    "gameplay.resource.scale_projection_probe": "resource_scene",
}


@dataclass(frozen=True)
class FactTypeRef:
    value: str
    domain: str


class FactTypeRegistry:
    """Typed event references; gameplay entries are sourced from schema declarations."""

    def __init__(self) -> None:
        self._refs: dict[str, FactTypeRef] = {
            fact.value: FactTypeRef(fact.value, domain)
            for fact, domain in _DOMAINS.items()
        }
        self._refs.update({key: FactTypeRef(key, domain) for key, domain in _GAMEPLAY_FACT_DOMAINS.items()})
        self._load_gameplay_schemas()

    def _load_gameplay_schemas(self) -> None:
        from app.gameplay.event_schema_registry import gameplay_schema_event_types

        for event_type in gameplay_schema_event_types():
            self._refs.setdefault(event_type, FactTypeRef(event_type, event_type.split(".", 2)[1]))

    def from_event_type(self, event_type: str) -> FactType | FactTypeRef | None:
        try:
            return FactType(event_type)
        except ValueError:
            pass
        return self._refs.get(event_type)

    def domain_for(self, fact_type: FactType | FactTypeRef) -> str:
        return _DOMAINS.get(fact_type, fact_type.domain if isinstance(fact_type, FactTypeRef) else "unknown")

    def register_event_type(self, event_type: str) -> FactTypeRef | None:
        return self.from_event_type(event_type)

    def event_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._refs))

    def validate_event_type_coverage(self) -> None:
        """S3: fail startup when schema declarations outgrow Siming's mapping."""
        from app.gameplay.event_schema_registry import gameplay_schema_event_types

        for event_type in gameplay_schema_event_types():
            ref = self.from_event_type(event_type)
            if ref is None or self.domain_for(ref) in {"", "unknown"}:
                raise RuntimeError(f"fact_type_registry_missing:{event_type}")
        # Phase 2: consume explicit Owner domain declarations instead of schema-name domains.


FACT_TYPE_REGISTRY = FactTypeRegistry()


def get_domain_for_fact_type(fact_type: FactType) -> str:
    return _DOMAINS.get(fact_type, "unknown")


__all__ = ["FACT_TYPE_REGISTRY", "FactType", "FactTypeRef", "FactTypeRegistry", "get_domain_for_fact_type"]
