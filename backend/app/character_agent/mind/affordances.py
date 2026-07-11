from __future__ import annotations

from copy import deepcopy

from app.character_agent.models.mind_frame import MentalFactorProjectionCard


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return deepcopy(value)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for entry in value:
        text = str(entry or "").strip()
        if text:
            items.append(text)
    return items


class CharacterMindAffordanceAdapter:
    def build_summary(
        self,
        *,
        effective_profile: dict[str, object] | None = None,
        supplied_skill_affordance_summary: dict[str, object] | None = None,
        supplied_action_affordance_summary: dict[str, object] | None = None,
        environment_affordance_summary: dict[str, object] | None = None,
        equipment_affordance_summary: dict[str, object] | None = None,
        physical_feasibility_summary: dict[str, object] | None = None,
    ) -> dict[str, dict[str, object]]:
        profile = _mapping(effective_profile)
        capability_constraints = _mapping(profile.get("capability_constraint_layer"))
        skill_summary = _mapping(supplied_skill_affordance_summary)
        skill_summary.pop("registry", None)

        profile_skill_ids = _string_list(capability_constraints.get("skills"))
        profile_limits = _string_list(capability_constraints.get("limits"))
        skill_summary["profile_skill_ids"] = profile_skill_ids
        skill_summary["profile_limits"] = profile_limits

        return {
            "skill_affordance": skill_summary,
            "action_affordance": _mapping(supplied_action_affordance_summary),
            "environment_affordance": _mapping(environment_affordance_summary),
            "equipment_affordance": _mapping(equipment_affordance_summary),
            "physical_feasibility": _mapping(physical_feasibility_summary),
        }

    def project_cards(
        self,
        summaries: dict[str, dict[str, object]],
    ) -> list[MentalFactorProjectionCard]:
        ordered_factor_types = [
            "skill_affordance",
            "action_affordance",
            "environment_affordance",
            "equipment_affordance",
            "physical_feasibility",
        ]
        cards: list[MentalFactorProjectionCard] = []
        for factor_type in ordered_factor_types:
            payload = _mapping(summaries.get(factor_type))
            cards.append(
                MentalFactorProjectionCard(
                    factor_type=factor_type,
                    layer="affordance",
                    scope="actor_private",
                    horizon="scene",
                    confidence=0.8 if payload else 0.0,
                    freshness="current" if payload else "unknown",
                    summary=factor_type.replace('_', ' '),
                    payload=payload,
                    source_refs=self._source_refs(factor_type, payload),
                )
            )
        return cards

    @staticmethod
    def _source_refs(factor_type: str, payload: dict[str, object]) -> list[str]:
        if not payload:
            return []
        return [f"{factor_type}:summary"]


__all__ = ["CharacterMindAffordanceAdapter"]
