from __future__ import annotations

from app.character_agent.skills.models import CharacterSkillState, ObservedSkillBelief, PlayerFacingCapabilityHint
from app.character_agent.skills.registry import CharacterSkillRegistry


class ObservedSkillBeliefStore:
    def __init__(self) -> None:
        self._beliefs: dict[tuple[str, str, str], ObservedSkillBelief] = {}

    def record(self, belief: ObservedSkillBelief) -> ObservedSkillBelief:
        key = (belief.observer_actor_id, belief.subject_actor_id, belief.skill_id)
        self._beliefs[key] = belief.model_copy(deep=True)
        return self._beliefs[key].model_copy(deep=True)

    def query(self, *, observer_actor_id: str, subject_actor_id: str | None = None) -> list[ObservedSkillBelief]:
        beliefs: list[ObservedSkillBelief] = []
        for (observer_id, belief_subject_id, _), belief in self._beliefs.items():
            if observer_id != observer_actor_id:
                continue
            if subject_actor_id is not None and belief_subject_id != subject_actor_id:
                continue
            beliefs.append(belief.model_copy(deep=True))
        return beliefs


class SkillVisibilityProjector:
    def __init__(self, *, registry: CharacterSkillRegistry | None = None) -> None:
        self._registry = registry or CharacterSkillRegistry()

    def player_hints(
        self,
        *,
        actor_id: str,
        skill_states: list[CharacterSkillState],
        viewer_id: str = "player",
    ) -> list[PlayerFacingCapabilityHint]:
        hints: list[PlayerFacingCapabilityHint] = []
        for state in skill_states:
            if state.actor_id != actor_id:
                continue
            if not self._is_player_visible(state=state, viewer_id=viewer_id):
                continue

            skill = self._safe_skill(state.skill_id)
            hints.append(
                PlayerFacingCapabilityHint(
                    actor_id=actor_id,
                    skill_id=state.skill_id,
                    display_name=skill.display_name if skill is not None else state.skill_id,
                    hint_level=state.rank,
                    domains=list(skill.domains) if skill is not None else [],
                    confidence=state.confidence,
                    source="actual",
                    evidence_refs=list(state.evidence_refs),
                )
            )

        hints.sort(key=lambda hint: (hint.skill_id, hint.source))
        return hints

    def _is_player_visible(self, *, state: CharacterSkillState, viewer_id: str) -> bool:
        visibility = state.visibility
        if visibility.get("player_visible") is False:
            return False
        visible_to_players = visibility.get("visible_to_players")
        if isinstance(visible_to_players, list) and visible_to_players:
            allowed_viewers = {str(item) for item in visible_to_players}
            if viewer_id not in allowed_viewers:
                return False
        if state.rank == "blocked" and visibility.get("hide_when_locked", True):
            return False
        if "private" in {str(item) for item in visibility.get("tags", [])}:
            return False
        return True

    def _safe_skill(self, skill_id: str):
        try:
            return self._registry.skill(skill_id)
        except KeyError:
            return None
