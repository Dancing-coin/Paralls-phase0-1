from __future__ import annotations

import math
from typing import Any, cast

from app.character_agent.models.cognition_delta import (
    CharacterBeliefDelta,
    CharacterDynamicStateDelta,
    CharacterHigherOrderDelta,
    CharacterSocialDelta,
)
from app.character_agent.models.goal_runtime import CharacterActiveGoalFrame
from app.character_agent.models.goal_runtime import CharacterGoalHint
from app.character_agent.models.goal_runtime import CharacterGoalPortfolioEntry


class CharacterStructuredOutputValidator:
    _L2_REQUIRED_KEYS = [
        "interpreted_summary",
        "interpretation_type",
        "salience_score",
        "ambiguity_level",
        "risk_level",
        "opportunity_level",
        "attention_target",
        "inner_prompt_candidate",
        "belief_deltas",
        "social_deltas",
        "higher_order_deltas",
        "dynamic_state_delta",
        "goal_hints",
        "reasoning_trace_summary",
    ]
    _LEVELS = {"low", "medium", "high"}

    def validate(self, *, task_kind: str, output: dict[str, object]) -> dict[str, object]:
        if not isinstance(output, dict):
            raise ValueError("structured model output must be a dictionary")
        if task_kind == "dialogue_generation":
            return self._validate_dialogue_output(output)
        if task_kind == "l3_planning":
            return self._validate_l3_output(output)
        return self._validate_l2_output(output)

    def _validate_dialogue_output(self, output: dict[str, object]) -> dict[str, object]:
        required = [
            "content",
            "tone",
        ]
        self._require_keys(output, required, task_kind="dialogue_generation")
        normalized = dict(output)
        normalized["content"] = str(normalized.get("content", "") or "").strip()
        normalized["tone"] = str(normalized.get("tone", "") or "").strip()
        if normalized["content"] == "":
            raise ValueError("dialogue_generation content must not be empty")
        if normalized["tone"] == "":
            raise ValueError("dialogue_generation tone must not be empty")
        return normalized

    def _validate_l2_output(self, output: dict[str, object]) -> dict[str, object]:
        self._require_keys(output, self._L2_REQUIRED_KEYS, task_kind="l2_reasoning")
        normalized = dict(output)
        normalized["interpreted_summary"] = str(normalized.get("interpreted_summary", "") or "").strip()
        normalized["interpretation_type"] = str(normalized.get("interpretation_type", "") or "").strip()
        if normalized["interpreted_summary"] == "":
            raise ValueError("l2_reasoning interpreted_summary must not be empty")
        if normalized["interpretation_type"] == "":
            raise ValueError("l2_reasoning interpretation_type must not be empty")
        normalized["salience_score"] = self._coerce_float(normalized.get("salience_score", 0.0), default=0.0)
        if normalized["salience_score"] < 0.0 or normalized["salience_score"] > 1.0:
            raise ValueError("l2_reasoning salience_score must be within 0.0..1.0")
        normalized["ambiguity_level"] = str(normalized.get("ambiguity_level", "") or "").strip()
        normalized["risk_level"] = str(normalized.get("risk_level", "") or "").strip()
        normalized["opportunity_level"] = str(normalized.get("opportunity_level", "") or "").strip()
        for key in ("ambiguity_level", "risk_level", "opportunity_level"):
            if normalized[key] not in self._LEVELS:
                raise ValueError(f"l2_reasoning {key} must be one of low, medium, high")
        attention_target = str(normalized.get("attention_target", "") or "")
        normalized["attention_target"] = attention_target or None
        inner_prompt_candidate = str(normalized.get("inner_prompt_candidate", "") or "")
        normalized["inner_prompt_candidate"] = inner_prompt_candidate or None
        normalized["belief_deltas"] = self._as_belief_delta_list(normalized.get("belief_deltas", []))
        normalized["social_deltas"] = self._as_social_delta_list(normalized.get("social_deltas", []))
        normalized["higher_order_deltas"] = self._as_higher_order_delta_list(normalized.get("higher_order_deltas", []))
        normalized["dynamic_state_delta"] = self._as_dynamic_state_delta(normalized.get("dynamic_state_delta", {}))
        normalized["goal_hints"] = self._as_goal_hint_list(normalized.get("goal_hints", []))
        reasoning_trace_summary = str(normalized.get("reasoning_trace_summary", "") or "")
        normalized["reasoning_trace_summary"] = reasoning_trace_summary or None
        cognition_status = str(normalized.get("cognition_status", "") or "")
        normalized["cognition_status"] = cognition_status or "model"
        fallback_mode = str(normalized.get("fallback_mode", "") or "")
        normalized["fallback_mode"] = fallback_mode or None
        return normalized

    def _validate_l3_output(self, output: dict[str, object]) -> dict[str, object]:
        required = [
            "candidate_intents",
            "selected_intent",
            "recommended_intents",
            "risk_notes",
            "why_this_now",
            "role_consistency_hint",
        ]
        self._require_keys(output, required, task_kind="l3_planning")
        normalized = dict(output)
        normalized["candidate_intents"] = self._as_string_list(normalized.get("candidate_intents", []))
        if not normalized["candidate_intents"]:
            raise ValueError("l3_planning candidate_intents must not be empty")
        normalized["selected_intent"] = str(normalized.get("selected_intent", "") or "").strip()
        if normalized["selected_intent"] == "":
            raise ValueError("l3_planning selected_intent must not be empty")
        if normalized["selected_intent"] not in normalized["candidate_intents"]:
            raise ValueError("l3_planning selected_intent must belong to candidate_intents")
        normalized["recommended_intents"] = self._as_string_list(normalized.get("recommended_intents", []))
        if not normalized["recommended_intents"]:
            raise ValueError("l3_planning recommended_intents must not be empty")
        normalized["risk_notes"] = self._as_string_list(normalized.get("risk_notes", []))
        normalized["why_this_now"] = str(normalized.get("why_this_now", "") or "").strip()
        if normalized["why_this_now"] == "":
            raise ValueError("l3_planning why_this_now must not be empty")
        normalized["role_consistency_hint"] = str(normalized.get("role_consistency_hint", "") or "").strip()
        normalized["active_goal_tags"] = self._as_string_list(normalized.get("active_goal_tags", []))
        normalized["active_goal_frame"] = self._as_active_goal_frame_mapping(normalized.get("active_goal_frame", {}))
        planning_status = str(normalized.get("planning_status", "") or "")
        normalized["planning_status"] = planning_status or "model"
        fallback_mode = str(normalized.get("fallback_mode", "") or "")
        normalized["fallback_mode"] = fallback_mode or None
        return normalized

    def _require_keys(self, output: dict[str, object], keys: list[str], *, task_kind: str) -> None:
        missing = [key for key in keys if key not in output]
        if missing:
            raise ValueError(f"{task_kind} output missing required keys: {', '.join(missing)}")

    def _as_string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("structured model output list field must be a list")
        return [str(item) for item in value]

    def _as_mapping_list(self, value: object) -> list[dict[str, object]]:
        if isinstance(value, dict):
            return [dict(value)] if value else []
        if not isinstance(value, list):
            raise ValueError("structured model output mapping list field must be a list")
        return [dict(item) for item in value if isinstance(item, dict)]

    def _as_goal_hint_list(self, value: object) -> list[dict[str, object]]:
        if not isinstance(value, list):
            raise ValueError("structured model output goal_hints field must be a list")
        hints: list[dict[str, object]] = []
        for item in value:
            if isinstance(item, dict):
                goal = str(item.get("goal", "") or "")
                if goal == "":
                    continue
                hints.append(
                    CharacterGoalHint(
                        goal=goal,
                        source=str(item.get("source", "") or "model"),
                        strength=self._coerce_float(item.get("strength", 0.5), default=0.5),
                        evidence_tags=self._as_string_list(item.get("evidence_tags", []))
                        if isinstance(item.get("evidence_tags", []), list)
                        else [],
                    ).model_dump()
                )
                continue
            goal = str(item or "").strip()
            if goal == "":
                continue
            hints.append(CharacterGoalHint(goal=goal, source="model", strength=0.5, evidence_tags=[]).model_dump())
        return hints

    def _as_belief_delta_list(self, value: object) -> list[dict[str, object]]:
        return [
            CharacterBeliefDelta(
                proposition_key=str(item.get("proposition_key", "") or ""),
                proposition=str(item.get("proposition", "") or ""),
                state=str(item.get("state", "suspected") or "suspected"),
                confidence=self._coerce_float(item.get("confidence", 0.0), default=0.0),
            ).model_dump()
            for item in self._as_mapping_list(value)
            if str(item.get("proposition_key", "") or "")
        ]

    def _as_social_delta_list(self, value: object) -> list[dict[str, object]]:
        return [
            CharacterSocialDelta(
                entity_id=str(item.get("entity_id", "") or ""),
                trust_baseline=self._coerce_float(item.get("trust_baseline", 0.5), default=0.5),
                suspicion_baseline=self._coerce_float(item.get("suspicion_baseline", 0.0), default=0.0),
                intimacy=self._coerce_float(item.get("intimacy", 0.0), default=0.0),
                dependency=self._coerce_float(item.get("dependency", 0.0), default=0.0),
                unresolved_tension=self._coerce_float(item.get("unresolved_tension", 0.0), default=0.0),
                shared_secret_refs=self._as_string_list(item.get("shared_secret_refs", []))
                if isinstance(item.get("shared_secret_refs", []), list)
                else [],
            ).model_dump()
            for item in self._as_mapping_list(value)
            if str(item.get("entity_id", "") or "")
        ]

    def _as_higher_order_delta_list(self, value: object) -> list[dict[str, object]]:
        return [
            CharacterHigherOrderDelta(
                subject_actor_id=str(item.get("subject_actor_id", "") or ""),
                proposition_key=str(item.get("proposition_key", "") or ""),
                meta_belief=str(item.get("meta_belief", "") or ""),
                confidence=self._coerce_float(item.get("confidence", 0.0), default=0.0),
            ).model_dump()
            for item in self._as_mapping_list(value)
            if str(item.get("subject_actor_id", "") or "") and str(item.get("meta_belief", "") or "")
        ]

    def _as_dynamic_state_delta(self, value: object) -> dict[str, float]:
        if not isinstance(value, dict):
            return {}
        allowed_fields = set(CharacterDynamicStateDelta.model_fields)
        filtered: dict[str, float] = {}
        for key, item in value.items():
            field_name = str(key)
            if field_name not in allowed_fields:
                raise ValueError(f"structured model output dynamic_state_delta field is unsupported: {field_name}")
            if item is None:
                continue
            filtered[field_name] = self._coerce_float(item, default=0.0)
        return CharacterDynamicStateDelta(**filtered).as_mapping()

    def _coerce_float(self, value: object, *, default: float) -> float:
        if value is None:
            return default
        if isinstance(value, bool):
            raise ValueError("structured model output numeric field must not be boolean")
        try:
            parsed = float(cast(Any, value))
        except (TypeError, ValueError) as exc:
            raise ValueError("structured model output numeric field must be finite") from exc
        if not math.isfinite(parsed):
            raise ValueError("structured model output numeric field must be finite")
        return parsed

    def _as_active_goal_frame_mapping(self, value: object) -> dict[str, object]:
        if not isinstance(value, dict):
            raise ValueError("structured model output active_goal_frame field must be a mapping")
        primary_goal = str(value.get("primary_goal", "") or "")
        if primary_goal == "":
            raise ValueError("structured model output active_goal_frame.primary_goal must not be empty")
        urgency = str(value.get("urgency", "low") or "low")
        if urgency not in self._LEVELS:
            raise ValueError("structured model output active_goal_frame.urgency must be one of low, medium, high")
        return CharacterActiveGoalFrame(
            primary_goal=primary_goal,
            long_term_goal=str(value.get("long_term_goal", "") or ""),
            mid_term_strategy=str(value.get("mid_term_strategy", "") or ""),
            immediate_goal=str(value.get("immediate_goal", "") or primary_goal),
            supporting_goals=self._as_string_list(value.get("supporting_goals", []))
            if isinstance(value.get("supporting_goals", []), list)
            else [],
            blockers=self._as_string_list(value.get("blockers", []))
            if isinstance(value.get("blockers", []), list)
            else [],
            goal_sources=self._as_string_list(value.get("goal_sources", []))
            if isinstance(value.get("goal_sources", []), list)
            else [],
            urgency=urgency,
            dominant_goal_id=str(value.get("dominant_goal_id", "") or ""),
            preserved_goal_ids=self._as_string_list(value.get("preserved_goal_ids", []))
            if isinstance(value.get("preserved_goal_ids", []), list)
            else [],
            suppressed_goal_ids=self._as_string_list(value.get("suppressed_goal_ids", []))
            if isinstance(value.get("suppressed_goal_ids", []), list)
            else [],
            goal_arbitration_summary=str(value.get("goal_arbitration_summary", "") or ""),
            goal_portfolio=self._as_goal_portfolio_entries(value.get("goal_portfolio", [])),
        ).model_dump()

    def _as_goal_portfolio_entries(self, value: object) -> list[CharacterGoalPortfolioEntry]:
        if not isinstance(value, list):
            return []
        entries: list[CharacterGoalPortfolioEntry] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            goal_id = str(item.get("goal_id", "") or "")
            goal = str(item.get("goal", "") or "")
            source = str(item.get("source", "") or "model")
            urgency = str(item.get("urgency", "low") or "low")
            if urgency not in self._LEVELS:
                raise ValueError("structured model output goal_portfolio urgency must be one of low, medium, high")
            if goal_id == "" or goal == "":
                continue
            entries.append(
                CharacterGoalPortfolioEntry(
                    goal_id=goal_id,
                    goal=goal,
                    horizon=str(item.get("horizon", "mid") or "mid"),
                    status=str(item.get("status", "active") or "active"),
                    priority=self._coerce_float(item.get("priority", 0.5), default=0.5),
                    urgency=urgency,
                    source=source,
                    target_ref=str(item.get("target_ref", "") or ""),
                    blockers=self._as_string_list(item.get("blockers", []))
                    if isinstance(item.get("blockers", []), list)
                    else [],
                    supporting_evidence=self._as_string_list(item.get("supporting_evidence", []))
                    if isinstance(item.get("supporting_evidence", []), list)
                    else [],
                )
            )
        return entries
