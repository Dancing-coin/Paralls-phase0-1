from __future__ import annotations


class CharacterStructuredOutputValidator:
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
        normalized["content"] = str(normalized.get("content", "") or "")
        normalized["tone"] = str(normalized.get("tone", "") or "")
        return normalized

    def _validate_l2_output(self, output: dict[str, object]) -> dict[str, object]:
        required = [
            "interpreted_summary",
            "interpretation_type",
            "salience_score",
            "ambiguity_level",
            "risk_level",
            "opportunity_level",
        ]
        self._require_keys(output, required, task_kind="l2_reasoning")
        normalized = dict(output)
        normalized["interpreted_summary"] = str(normalized.get("interpreted_summary", "") or "")
        normalized["interpretation_type"] = str(normalized.get("interpretation_type", "") or "")
        normalized["salience_score"] = float(normalized.get("salience_score", 0.0) or 0.0)
        normalized["ambiguity_level"] = str(normalized.get("ambiguity_level", "") or "")
        normalized["risk_level"] = str(normalized.get("risk_level", "") or "")
        normalized["opportunity_level"] = str(normalized.get("opportunity_level", "") or "")
        attention_target = str(normalized.get("attention_target", "") or "")
        normalized["attention_target"] = attention_target or None
        inner_prompt_candidate = str(normalized.get("inner_prompt_candidate", "") or "")
        normalized["inner_prompt_candidate"] = inner_prompt_candidate or None
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
        normalized["selected_intent"] = str(normalized.get("selected_intent", "") or "")
        normalized["recommended_intents"] = self._as_string_list(normalized.get("recommended_intents", []))
        normalized["risk_notes"] = self._as_string_list(normalized.get("risk_notes", []))
        normalized["why_this_now"] = str(normalized.get("why_this_now", "") or "")
        normalized["role_consistency_hint"] = str(normalized.get("role_consistency_hint", "") or "")
        return normalized

    def _require_keys(self, output: dict[str, object], keys: list[str], *, task_kind: str) -> None:
        missing = [key for key in keys if key not in output]
        if missing:
            raise ValueError(f"{task_kind} output missing required keys: {', '.join(missing)}")

    def _as_string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("structured model output list field must be a list")
        return [str(item) for item in value]
