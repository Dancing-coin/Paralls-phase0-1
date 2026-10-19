from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from app.character_agent.skills.models import (
    CharacterSkillState,
    EffectiveSkillStateProjection,
    PrimitiveActionPlan,
    SkillAffordanceSummary,
    SkillEvaluationResult,
    SkillLearningPolicy,
    StableAbilitySkill,
    StableAbilitySnapshot,
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

_SOURCE_PRIORITY = {
    "constrained": 7,
    "authority": 6,
    "scripted": 5,
    "equipment": 4,
    "temporary": 3,
    "learned": 2,
    "authored": 1,
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
        authored_skill_names: set[str] = set()
        for skill_id in skill_id_list:
            try:
                authored_skill_names.add(self._registry.canonical_skill_id(str(skill_id)))
            except ValueError:
                # Legacy authoring projection remains permissive; strict runtime
                # compilation is provided by compile_stable_snapshot.
                continue
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

    def compile_stable_snapshot(
        self,
        *,
        actor_id: str,
        skill_states: list[CharacterSkillState],
        capability_revision: str | None = None,
        source_refs: list[str] | None = None,
        revoked_grants: set[str] | Mapping[str, object] | None = None,
        grants: Mapping[str, object] | None = None,
    ) -> StableAbilitySnapshot:
        """Compile stable skill facts without equipment or current resources.

        This is deliberately a pure projection. Unknown ids are authoring
        diagnostics only and fail closed at runtime; revoked grants are
        represented as blocked families and omitted from active skills.
        """
        revoked: set[str] = set()
        diagnostics: list[str] = []
        raw_revoked: set[str] = set()
        if isinstance(revoked_grants, Mapping):
            raw_revoked.update(str(key) for key in revoked_grants)
            for grant_id, value in revoked_grants.items():
                if isinstance(value, Mapping):
                    value = value.get("skill_ids", [])
                if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                    raw_revoked.update(str(item) for item in value)
        else:
            raw_revoked.update(str(item) for item in (revoked_grants or set()))
        if grants:
            for grant_id, value in grants.items():
                if not isinstance(value, Mapping):
                    continue
                status = str(value.get("status", "active"))
                if status != "revoked":
                    continue
                raw_revoked.update(str(grant_id) for _ in [0])
                skill_ids = value.get("skill_ids", [])
                if isinstance(skill_ids, Sequence) and not isinstance(skill_ids, (str, bytes)):
                    raw_revoked.update(str(item) for item in skill_ids)
        for item in raw_revoked:
            try:
                revoked.add(self._registry.canonical_skill_id(item))
            except ValueError:
                # Grant ids are not skill ids; they become useful diagnostics
                # when no skill mapping was supplied and do not widen access.
                diagnostics.append(f"revoked_grant:{item}")
        projected: dict[str, StableAbilitySkill] = {}
        refs = tuple(sorted(set(str(item) for item in (source_refs or []) if str(item))))
        for state in self._skill_states_for_actor(actor_id=actor_id, skill_states=skill_states):
            try:
                canonical_id = self._registry.canonical_skill_id(state.skill_id)
            except ValueError as exc:
                diagnostics.append(f"unknown_skill:{state.skill_id}")
                raise ValueError("unknown_skill") from exc
            skill = self._registry.skill(canonical_id)
            if canonical_id in revoked:
                diagnostics.append(f"revoked_grant:{canonical_id}")
                continue
            candidate = StableAbilitySkill(
                skill_id=canonical_id,
                source=state.source,
                rank=state.rank,
                proficiency=state.proficiency,
                confidence=state.confidence,
                domains=sorted(set(skill.domains)),
                source_refs=sorted(set((*refs, *state.evidence_refs))),
            )
            previous = projected.get(canonical_id)
            if previous is None or self._stable_priority(candidate) > self._stable_priority(previous):
                projected[canonical_id] = candidate

        skills = [projected[key] for key in sorted(projected)]
        active_ids = set(projected)
        allowed: set[str] = set()
        blocked: set[str] = set()
        for skill in self._registry.skills():
            families = set(skill.domains or {skill.skill_id})
            bindings = [binding for binding in self._registry.bindings() if binding.skill_id == skill.skill_id]
            if not bindings:
                continue
            if skill.skill_id in active_ids:
                allowed.update(families)
            else:
                blocked.update(families)
        blocked -= allowed
        capability_pin = capability_revision or f"capability:{actor_id}:{self._state_revision(skills)}"
        registry_revision = self._registry.revision()
        payload = {
            "actor_id": actor_id,
            "capability_revision": capability_pin,
            "registry_revision": registry_revision,
            "skills": [item.model_dump(mode="json") for item in skills],
            "allowed_action_families": sorted(allowed),
            "blocked_action_families": sorted(blocked),
            "source_refs": list(refs),
            "diagnostics": sorted(diagnostics),
        }
        digest = "sha256:" + hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        ).hexdigest()
        return StableAbilitySnapshot(
            actor_id=actor_id,
            capability_revision=capability_pin,
            registry_revision=registry_revision,
            skills=skills,
            allowed_action_families=sorted(allowed),
            blocked_action_families=sorted(blocked),
            source_refs=list(refs),
            diagnostics=sorted(diagnostics),
            digest=digest,
        )

    @staticmethod
    def _stable_priority(skill: StableAbilitySkill) -> tuple[int, float, float, str]:
        return (_RANK_ORDER.get(skill.rank, -1), skill.proficiency, skill.confidence, skill.source)

    @staticmethod
    def _state_revision(skills: list[StableAbilitySkill]) -> str:
        payload = [item.model_dump(mode="json") for item in skills]
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]

    def build_affordance_summary(
        self,
        *,
        actor_id: str,
        skill_states: list[CharacterSkillState],
        learned_skill_states: list[CharacterSkillState] | None = None,
        temporary_skill_states: list[CharacterSkillState] | None = None,
        equipment_skill_states: list[CharacterSkillState] | None = None,
        scripted_skill_states: list[CharacterSkillState] | None = None,
        learned_overlay_enabled: bool = True,
    ) -> SkillAffordanceSummary:
        projection = self.resolve_effective_skill_states(
            actor_id=actor_id,
            skill_states=skill_states,
            learned_skill_states=learned_skill_states,
            temporary_skill_states=temporary_skill_states,
            equipment_skill_states=equipment_skill_states,
            scripted_skill_states=scripted_skill_states,
            learned_overlay_enabled=learned_overlay_enabled,
        )
        active_states = {
            skill_id: state
            for skill_id, state in projection.primary_state_by_skill.items()
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
        learned_skill_states: list[CharacterSkillState] | None = None,
        temporary_skill_states: list[CharacterSkillState] | None = None,
        equipment_skill_states: list[CharacterSkillState] | None = None,
        scripted_skill_states: list[CharacterSkillState] | None = None,
        learned_overlay_enabled: bool = True,
    ) -> SkillEvaluationResult:
        preferred_strategy_tags = preferred_strategy_tags or []
        projection = self.resolve_effective_skill_states(
            actor_id=actor_id,
            skill_states=skill_states,
            learned_skill_states=learned_skill_states,
            temporary_skill_states=temporary_skill_states,
            equipment_skill_states=equipment_skill_states,
            scripted_skill_states=scripted_skill_states,
            learned_overlay_enabled=learned_overlay_enabled,
        )
        state_by_skill = dict(projection.primary_state_by_skill)
        viable_paths: list[dict[str, object]] = []
        blocked_paths: list[dict[str, object]] = []

        bindings = self._registry.bindings_for_action(action_id)
        for binding in bindings:
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
        elif not bindings:
            recommendation_reason.append("no_registered_skill_path")

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

    def resolve_effective_skill_states(
        self,
        *,
        actor_id: str,
        skill_states: list[CharacterSkillState],
        learned_skill_states: list[CharacterSkillState] | None = None,
        temporary_skill_states: list[CharacterSkillState] | None = None,
        equipment_skill_states: list[CharacterSkillState] | None = None,
        scripted_skill_states: list[CharacterSkillState] | None = None,
        learned_overlay_enabled: bool = True,
    ) -> EffectiveSkillStateProjection:
        collected: list[CharacterSkillState] = []
        overlays_applied: list[str] = []
        collected.extend(self._skill_states_for_actor(actor_id=actor_id, skill_states=skill_states))

        if learned_overlay_enabled:
            overlays_applied.append("learned")
            collected.extend(self._skill_states_for_actor(actor_id=actor_id, skill_states=learned_skill_states or []))
        if temporary_skill_states:
            overlays_applied.append("temporary")
            collected.extend(self._skill_states_for_actor(actor_id=actor_id, skill_states=temporary_skill_states))
        if equipment_skill_states:
            overlays_applied.append("equipment")
            collected.extend(self._skill_states_for_actor(actor_id=actor_id, skill_states=equipment_skill_states))
        if scripted_skill_states:
            overlays_applied.append("scripted")
            collected.extend(self._skill_states_for_actor(actor_id=actor_id, skill_states=scripted_skill_states))

        ordered_states = sorted(
            collected,
            key=lambda state: (
                state.skill_id,
                -self._source_priority(state.source),
                -self._rank_value(state.rank),
                -state.proficiency,
                -state.confidence,
            ),
        )

        primary_state_by_skill: dict[str, CharacterSkillState] = {}
        conflicts: list[dict[str, object]] = []
        states_by_skill: dict[str, list[CharacterSkillState]] = {}
        for state in ordered_states:
            states_by_skill.setdefault(state.skill_id, []).append(state)
            primary_state_by_skill.setdefault(state.skill_id, state)

        for skill_id, states_for_skill in states_by_skill.items():
            if len(states_for_skill) <= 1:
                continue
            primary = states_for_skill[0]
            conflicts.append(
                {
                    "skill_id": skill_id,
                    "selected_source": primary.source,
                    "selected_rank": primary.rank,
                    "sources": [state.source for state in states_for_skill],
                    "suppressed_sources": [state.source for state in states_for_skill[1:]],
                }
            )

        return EffectiveSkillStateProjection(
            actor_id=actor_id,
            states=[state.model_copy(deep=True) for state in ordered_states],
            primary_state_by_skill={
                skill_id: state.model_copy(deep=True)
                for skill_id, state in primary_state_by_skill.items()
            },
            conflicts=conflicts,
            overlays_applied=overlays_applied,
        )

    def _state_meets_rank(self, state: CharacterSkillState, required_rank: str) -> bool:
        return self._rank_value(state.rank) >= self._rank_value(required_rank)

    def _rank_value(self, rank: str) -> int:
        return _RANK_ORDER.get(rank, -1)

    def _preference_score(self, path_tags: list[str], preferred_strategy_tags: list[str]) -> int:
        return sum(1 for tag in preferred_strategy_tags if tag in path_tags)

    def _source_priority(self, source: str) -> int:
        return _SOURCE_PRIORITY.get(source, 0)

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

    def _skill_states_for_actor(
        self,
        *,
        actor_id: str,
        skill_states: list[CharacterSkillState],
    ) -> list[CharacterSkillState]:
        return [state for state in skill_states if state.actor_id == actor_id]
