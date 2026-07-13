from __future__ import annotations

from typing import Any

from app.character_agent.skills.models import (
    CharacterSkillState,
    LearnedSkillLayer,
    PrimitiveActionPlan,
    SkillAffordanceSummary,
    SkillEvaluationResult,
    SkillLearningPolicy,
)
from app.character_agent.skills.registry import CharacterSkillRegistry


_RANK_ORDER = {
    "none": 0,
    "novice": 1,
    "basic": 2,
    "trained": 3,
    "expert": 4,
    "master": 5,
    "blocked": -1,
}


class CharacterSkillService:
    def __init__(self, *, registry: CharacterSkillRegistry | None = None) -> None:
        self._registry = registry or CharacterSkillRegistry()

    def initial_skill_states(self, *, actor_id: str, profile: dict[str, Any]) -> list[CharacterSkillState]:
        capability_layer = profile.get("capability_constraint_layer")
        if not isinstance(capability_layer, dict):
            capability_layer = {}
        skill_ids = capability_layer.get("skills")
        skill_id_list = skill_ids if isinstance(skill_ids, list) else []
        authored_skill_names = {
            str(skill_id)
            for skill_id in skill_id_list
        }
        states: list[CharacterSkillState] = []

        for skill in self._registry.skills():
            if skill.skill_id not in authored_skill_names:
                continue
            states.append(
                CharacterSkillState(
                    actor_id=actor_id,
                    skill_id=skill.skill_id,
                    source="authored",
                    rank="basic",
                    proficiency=0.5,
                    confidence=0.5,
                    visibility=dict(skill.visibility_default),
                )
            )

        return states

    def effective_skill_states(
        self,
        *,
        actor_id: str,
        profile: dict[str, Any],
        learned_overlay: LearnedSkillLayer | None = None,
        runtime_states: list[CharacterSkillState] | None = None,
    ) -> list[CharacterSkillState]:
        authored_states = self.initial_skill_states(actor_id=actor_id, profile=profile)
        learned_states = self._overlay_skill_states(
            actor_id=actor_id,
            learned_overlay=learned_overlay,
        )
        passthrough_runtime_states = self._runtime_skill_states(
            actor_id=actor_id,
            runtime_states=runtime_states or [],
        )

        return self._annotate_conflicts(
            authored_states + learned_states + passthrough_runtime_states
        )

    def build_affordance_summary(
        self,
        *,
        actor_id: str,
        skill_states: list[CharacterSkillState],
    ) -> SkillAffordanceSummary:
        effective_states = self._resolved_effective_rows_by_skill_id(
            actor_id=actor_id,
            skill_states=skill_states,
        )
        active_states = {
            skill_id: state
            for skill_id, state in effective_states.items()
            if self._rank_value(state.rank) > 0
        }
        family_records: dict[str, dict[str, object]] = {}
        available: dict[str, dict[str, object]] = {}
        blocked: dict[str, dict[str, object]] = {}

        for skill in self._registry.skills():
            family_keys = skill.domains or [skill.skill_id]
            examples = sorted(
                {
                    binding.action_id
                    for binding in self._registry.bindings()
                    if binding.skill_id == skill.skill_id
                }
            )
            if not examples:
                continue
            state = active_states.get(skill.skill_id)

            for family_key in family_keys:
                family = family_records.setdefault(
                    family_key,
                    {
                        "level": "blocked",
                        "skill_ids": [],
                        "examples": [],
                        "missing_skills": [],
                        "has_usable_skill": False,
                    },
                )
                family["skill_ids"] = self._merge_strings(family["skill_ids"], [skill.skill_id])
                family["examples"] = self._merge_strings(family["examples"], examples)
                if state is not None:
                    family["has_usable_skill"] = True
                    family["level"] = self._higher_rank(str(family["level"]), state.rank)
                else:
                    family["missing_skills"] = self._merge_strings(
                        family.get("missing_skills", []),
                        [skill.skill_id],
                    )

        for family_key, family in family_records.items():
            summary = {
                "level": family["level"],
                "skill_ids": family["skill_ids"],
                "examples": family["examples"],
            }
            if len(summary["skill_ids"]) == 1:
                summary["skill_id"] = summary["skill_ids"][0]
            missing_skills = family["missing_skills"]
            if missing_skills:
                summary["missing_skills"] = missing_skills
            if bool(family["has_usable_skill"]):
                available[family_key] = summary
            else:
                blocked[family_key] = summary

        return SkillAffordanceSummary(
            actor_id=actor_id,
            available_action_families=available,
            blocked_action_families=blocked,
        )

    def evaluate_action(
        self,
        *,
        actor_id: str,
        action_id: str,
        skill_states: list[CharacterSkillState],
        preferred_strategy_tags: list[str] | None = None,
    ) -> SkillEvaluationResult:
        preferred_strategy_tags = preferred_strategy_tags or []
        state_by_skill = self._resolved_effective_rows_by_skill_id(
            actor_id=actor_id,
            skill_states=skill_states,
        )
        viable_paths: list[dict[str, object]] = []
        blocked_paths: list[dict[str, object]] = []

        for binding in self._registry.bindings_for_action(action_id):
            state = state_by_skill.get(binding.skill_id)
            required_rank = str(binding.eligibility.get("required_rank", "none"))
            missing_requirements: list[str] = []

            if state is None or not self._state_meets_rank(state, required_rank):
                missing_requirements.append(f"{binding.skill_id}.{required_rank}")

            path_record = {
                "binding_id": binding.binding_id,
                "skill_id": binding.skill_id,
                "action_id": action_id,
                "skill_path_tags": list(binding.skill_path_tags),
            }

            if missing_requirements:
                blocked_paths.append(
                    {
                        **path_record,
                        "eligibility_status": "blocked",
                        "missing_requirements": missing_requirements,
                    }
                )
                continue

            viable_paths.append(
                {
                    **path_record,
                    "eligibility_status": "eligible",
                    "required_rank": required_rank,
                    "current_rank": state.rank,
                    "preference_score": self._preference_score(binding.skill_path_tags, preferred_strategy_tags),
                }
            )

        viable_paths.sort(
            key=lambda path: (
                int(path["preference_score"]),
                self._rank_value(str(path["current_rank"])),
                str(path["binding_id"]),
            ),
            reverse=True,
        )
        selected_path = viable_paths[0] if viable_paths else {}

        recommendation_reason: list[str] = []
        if selected_path:
            if int(selected_path.get("preference_score", 0)) > 0:
                recommendation_reason.append("preferred_strategy_match")
            recommendation_reason.append("eligible_skill_path_available")
        elif blocked_paths:
            recommendation_reason.append("no_eligible_skill_path")

        learning_policy = SkillLearningPolicy()

        return SkillEvaluationResult(
            actor_id=actor_id,
            action_id=action_id,
            selected_path=selected_path,
            viable_paths=viable_paths,
            blocked_paths=blocked_paths,
            recommendation_reason=recommendation_reason,
            learning_policy_snapshot=learning_policy.model_dump(),
        )

    def expand_primitive_plan(self, *, action_id: str, skill_path_id: str) -> PrimitiveActionPlan:
        action = self._registry.action(action_id)
        return PrimitiveActionPlan(
            composite_action_id=action_id,
            skill_path_id=skill_path_id,
            primitive_actions=list(action.primitive_sequence_templates.get(skill_path_id, [])),
            realization_keys=list(action.realization_keys),
        )

    def _state_meets_rank(self, state: CharacterSkillState, required_rank: str) -> bool:
        return self._rank_value(state.rank) >= self._rank_value(required_rank)

    def _rank_value(self, rank: str) -> int:
        return _RANK_ORDER.get(rank, -1)

    def _preference_score(self, path_tags: list[str], preferred_strategy_tags: list[str]) -> int:
        return sum(1 for tag in preferred_strategy_tags if tag in path_tags)

    def _higher_rank(self, left: str, right: str) -> str:
        if self._rank_value(right) > self._rank_value(left):
            return right
        return left

    def _merge_strings(self, current: object, additions: list[str]) -> list[str]:
        values = [str(item) for item in current] if isinstance(current, list) else []
        for item in additions:
            if item not in values:
                values.append(item)
        return values

    def _resolved_effective_rows_by_skill_id(
        self,
        *,
        actor_id: str,
        skill_states: list[CharacterSkillState],
    ) -> dict[str, CharacterSkillState]:
        resolved: dict[str, tuple[tuple[int, str, int], CharacterSkillState]] = {}
        for index, state in enumerate(
            self._skill_states_for_actor(actor_id=actor_id, skill_states=skill_states)
        ):
            candidate_key = (
                -self._rank_value(state.rank),
                state.source,
                index,
            )
            current = resolved.get(state.skill_id)
            if current is None or candidate_key < current[0]:
                resolved[state.skill_id] = (candidate_key, state)
        return {
            skill_id: resolved_state
            for skill_id, (_, resolved_state) in resolved.items()
        }

    def _skill_states_for_actor(
        self,
        *,
        actor_id: str,
        skill_states: list[CharacterSkillState],
    ) -> list[CharacterSkillState]:
        return [state for state in skill_states if state.actor_id == actor_id]

    def _overlay_skill_states(
        self,
        *,
        actor_id: str,
        learned_overlay: LearnedSkillLayer | None,
    ) -> list[CharacterSkillState]:
        if learned_overlay is None or not learned_overlay.enabled:
            return []
        return self._skill_states_for_actor(
            actor_id=actor_id,
            skill_states=list(learned_overlay.skill_states),
        )

    def _runtime_skill_states(
        self,
        *,
        actor_id: str,
        runtime_states: list[CharacterSkillState],
    ) -> list[CharacterSkillState]:
        states = self._skill_states_for_actor(actor_id=actor_id, skill_states=runtime_states)
        source_order = {
            "temporary": 0,
            "equipment": 1,
            "authority": 2,
            "scripted": 3,
            "constrained": 4,
            "authored": 5,
            "learned": 6,
        }
        return sorted(
            states,
            key=lambda state: (
                state.skill_id,
                source_order.get(state.source, 99),
            ),
        )

    def _annotate_conflicts(
        self,
        states: list[CharacterSkillState],
    ) -> list[CharacterSkillState]:
        rows_by_skill: dict[str, list[CharacterSkillState]] = {}
        for state in states:
            rows_by_skill.setdefault(state.skill_id, []).append(state)

        resolved_states: list[CharacterSkillState] = []
        for state in states:
            skill_rows = rows_by_skill.get(state.skill_id, [])
            copied_state = state.model_copy(deep=True)
            if len(skill_rows) > 1:
                sources = [row.source for row in skill_rows]
                copied_state.visibility["conflict"] = {
                    "skill_id": state.skill_id,
                    "sources": sources,
                    "current_source": state.source,
                    "rows": [
                        {
                            "source": row.source,
                            "rank": row.rank,
                            "evidence_refs": list(row.evidence_refs),
                            "restrictions": list(row.restrictions),
                        }
                        for row in skill_rows
                    ],
                }
            resolved_states.append(copied_state)
        return resolved_states
