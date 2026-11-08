from __future__ import annotations

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


def get_domain_for_fact_type(fact_type: FactType) -> str:
    return _DOMAINS.get(fact_type, "unknown")


__all__ = ["FactType", "get_domain_for_fact_type"]
