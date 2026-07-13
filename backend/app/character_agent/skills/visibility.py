from __future__ import annotations

from pydantic import Field, model_validator

from app.character_agent.skills.models import CharacterSkillState, SkillDefinition, StrictSkillModel

_HIDDEN_VISIBILITY_STATES = frozenset({"hidden", "locked", "private"})


class ObservedSkillBelief(StrictSkillModel):
    observer_actor_id: str
    subject_actor_id: str
    skill_id: str
    belief_state: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, strict=True)
    evidence_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_confidence_evidence_refs(self) -> "ObservedSkillBelief":
        if self.confidence > 0.0 and not self.evidence_refs:
            raise ValueError("observed skill belief confidence requires evidence_refs")
        return self


class PlayerFacingCapabilityHint(StrictSkillModel):
    subject_actor_id: str
    skill_id: str
    display_name: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, strict=True)
    visibility_state: str = "visible"


class ObservedSkillBeliefStore:
    def __init__(self) -> None:
        self._beliefs: dict[tuple[str, str, str], ObservedSkillBelief] = {}

    def upsert(self, belief: ObservedSkillBelief) -> None:
        key = (belief.observer_actor_id, belief.subject_actor_id, belief.skill_id)
        self._beliefs[key] = belief.model_copy(deep=True)

    def query(
        self,
        *,
        observer_actor_id: str,
        subject_actor_id: str = "",
        skill_id: str = "",
    ) -> list[ObservedSkillBelief]:
        matches: list[ObservedSkillBelief] = []
        for stored in self._beliefs.values():
            if stored.observer_actor_id != observer_actor_id:
                continue
            if subject_actor_id and stored.subject_actor_id != subject_actor_id:
                continue
            if skill_id and stored.skill_id != skill_id:
                continue
            matches.append(stored.model_copy(deep=True))
        return matches


def build_player_facing_capability_hints(
    *,
    subject_actor_id: str,
    skill_states: list[CharacterSkillState],
    skill_definitions: list[SkillDefinition],
) -> list[PlayerFacingCapabilityHint]:
    definitions_by_skill_id = {definition.skill_id: definition for definition in skill_definitions}
    hints: list[PlayerFacingCapabilityHint] = []
    for state in skill_states:
        if state.actor_id != subject_actor_id:
            continue

        definition = definitions_by_skill_id.get(state.skill_id)
        if definition is None:
            continue
        if not _is_player_visible(state=state, definition=definition):
            continue

        hints.append(
            PlayerFacingCapabilityHint(
                subject_actor_id=subject_actor_id,
                skill_id=state.skill_id,
                display_name=definition.display_name,
                confidence=state.confidence,
                visibility_state=_visibility_state(state=state, definition=definition),
            )
        )
    return hints


def _is_player_visible(*, state: CharacterSkillState, definition: SkillDefinition) -> bool:
    if definition.learnability == "locked":
        return False

    state_visibility = dict(state.visibility)
    default_visibility = dict(definition.visibility_default)

    if state_visibility.get("locked") is True:
        return False
    if default_visibility.get("locked") is True:
        return False
    if _visibility_state(state=state, definition=definition) in _HIDDEN_VISIBILITY_STATES:
        return False

    player_visible = state_visibility.get("player_visible")
    if isinstance(player_visible, bool):
        return player_visible

    default_player_visible = default_visibility.get("player_visible")
    if isinstance(default_player_visible, bool):
        return default_player_visible

    return True


def _visibility_state(*, state: CharacterSkillState, definition: SkillDefinition) -> str:
    state_value = state.visibility.get("visibility_state")
    if isinstance(state_value, str) and state_value.strip():
        return state_value.strip()

    default_value = definition.visibility_default.get("visibility_state")
    if isinstance(default_value, str) and default_value.strip():
        return default_value.strip()

    return "visible"


__all__ = [
    "ObservedSkillBelief",
    "ObservedSkillBeliefStore",
    "PlayerFacingCapabilityHint",
    "build_player_facing_capability_hints",
]
