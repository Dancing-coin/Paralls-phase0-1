from __future__ import annotations

from app.character_agent.skills.models import ActionDefinition, SkillActionBinding, SkillDefinition


class CharacterSkillRegistry:
    def __init__(
        self,
        *,
        skills: list[SkillDefinition] | None = None,
        actions: list[ActionDefinition] | None = None,
        bindings: list[SkillActionBinding] | None = None,
    ) -> None:
        self._skills = {item.skill_id: item for item in skills or []}
        self._actions = {item.action_id: item for item in actions or []}
        self._bindings = {item.binding_id: item for item in bindings or []}

    @classmethod
    def compose(cls, *registries: "CharacterSkillRegistry") -> "CharacterSkillRegistry":
        skills: list[SkillDefinition] = []
        actions: list[ActionDefinition] = []
        bindings: list[SkillActionBinding] = []
        for registry in registries:
            skills.extend(registry._skills.values())
            actions.extend(registry._actions.values())
            bindings.extend(registry._bindings.values())
        return cls(skills=skills, actions=actions, bindings=bindings)

    def skill(self, skill_id: str) -> SkillDefinition:
        return self._skills[skill_id]

    def action(self, action_id: str) -> ActionDefinition:
        return self._actions[action_id]

    def skills(self) -> list[SkillDefinition]:
        return list(self._skills.values())

    def actions(self) -> list[ActionDefinition]:
        return list(self._actions.values())

    def bindings(self) -> list[SkillActionBinding]:
        return list(self._bindings.values())

    def bindings_for_action(self, action_id: str) -> list[SkillActionBinding]:
        return [binding for binding in self._bindings.values() if binding.action_id == action_id]
