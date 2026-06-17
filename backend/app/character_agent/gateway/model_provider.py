from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class CharacterModelProvider:
    def __init__(
        self,
        *,
        endpoint_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self._endpoint_url = (endpoint_url or os.getenv("CHARACTER_MODEL_ENDPOINT", "")).strip()
        self._api_key = (api_key or os.getenv("CHARACTER_MODEL_API_KEY", "")).strip()
        self._timeout_seconds = timeout_seconds

    def complete(self, request: dict[str, object]) -> dict[str, object]:
        if self._endpoint_url:
            try:
                return self._complete_via_http(request)
            except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
                return self._offline_complete(request)
        return self._offline_complete(request)

    def _complete_via_http(self, request: dict[str, object]) -> dict[str, object]:
        body = json.dumps(request).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        req = Request(self._endpoint_url, data=body, headers=headers, method="POST")
        with urlopen(req, timeout=self._timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("output"), dict):
            return dict(payload["output"])
        if isinstance(payload, dict):
            return dict(payload)
        raise ValueError("model provider response must be a JSON object")

    def _offline_complete(self, request: dict[str, object]) -> dict[str, object]:
        task_kind = str(request.get("task_kind", "") or "")
        context = request.get("context", {})
        if not isinstance(context, dict):
            context = {}
        if task_kind == "l3_planning":
            return self._offline_l3_output(context)
        return self._offline_l2_output(context)

    def _offline_l2_output(self, context: dict[str, object]) -> dict[str, object]:
        snapshot = context.get("snapshot", {})
        event = context.get("event", {})
        memory = context.get("memory", {})
        if not isinstance(snapshot, dict):
            snapshot = {}
        if not isinstance(event, dict):
            event = {}
        if not isinstance(memory, dict):
            memory = {}
        body_state_hints = snapshot.get("body_state_hints", [])
        if not isinstance(body_state_hints, list):
            body_state_hints = []
        summary = str(event.get("perceived_summary", "") or snapshot.get("perceived_summary", "") or "state_change")
        interpretation_type = "state_change"
        if str(event.get("body_state_class", "") or ""):
            interpretation_type = "body_state"
        elif body_state_hints:
            interpretation_type = "body_state"
        elif str(event.get("percept_channel", "") or "") == "auditory":
            interpretation_type = "social_signal"
        elif "visual_fact" in summary:
            interpretation_type = "opportunity"
        attention_targets = snapshot.get("attention_targets", [])
        if not isinstance(attention_targets, list):
            attention_targets = []
        relational_memories = memory.get("relational_memories", [])
        if not isinstance(relational_memories, list):
            relational_memories = []
        active_anomalies = snapshot.get("active_anomalies", [])
        if not isinstance(active_anomalies, list):
            active_anomalies = []
        recent_constraint_results = snapshot.get("recent_constraint_results", [])
        if not isinstance(recent_constraint_results, list):
            recent_constraint_results = []
        recent_world_changes = snapshot.get("recent_world_changes", [])
        if not isinstance(recent_world_changes, list):
            recent_world_changes = []
        last_siming_catalyst = str(snapshot.get("last_siming_catalyst", "") or "")
        vigilance_level = str(snapshot.get("vigilance_level", "") or "")
        distraction_level = str(snapshot.get("distraction_level", "") or "")
        attention_target = str(attention_targets[0] if attention_targets else event.get("target_actor_id", "") or event.get("target_object_id", "") or event.get("target_environment_id", "") or "")
        guarded_attention_target = self._is_guarded_relational_target(attention_target, relational_memories)
        salience_score = float(event.get("clarity_score", snapshot.get("clarity_score", 0.5)) or 0.5)
        opportunity_level = "medium" if interpretation_type in {"opportunity", "social_signal"} else "low"
        if recent_world_changes or last_siming_catalyst != "" or vigilance_level == "elevated":
            opportunity_level = "medium"
        risk_level = "medium" if interpretation_type == "body_state" else "low"
        if active_anomalies or recent_constraint_results or guarded_attention_target:
            risk_level = "medium"
        ambiguity_level = "medium" if float(event.get("certainty_score", snapshot.get("certainty_score", 1.0)) or 1.0) < 0.7 else "low"
        if distraction_level == "elevated":
            ambiguity_level = "medium"
        return {
            "interpreted_summary": summary,
            "interpretation_type": interpretation_type,
            "salience_score": salience_score,
            "ambiguity_level": ambiguity_level,
            "risk_level": risk_level,
            "opportunity_level": opportunity_level,
            "attention_target": attention_target or None,
            "inner_prompt_candidate": f"{str(event.get('actor_id', '') or snapshot.get('actor_id', '') or '')}:{summary}",
        }

    def _offline_l3_output(self, context: dict[str, object]) -> dict[str, object]:
        interpretation = context.get("interpretation", {})
        snapshot = context.get("snapshot", {})
        memory = context.get("memory", {})
        if not isinstance(interpretation, dict):
            interpretation = {}
        if not isinstance(snapshot, dict):
            snapshot = {}
        if not isinstance(memory, dict):
            memory = {}
        control_mode = str(context.get("control_mode", "") or "")
        attention_target = str(interpretation.get("attention_target", "") or "")
        relational_memories = memory.get("relational_memories", [])
        if not isinstance(relational_memories, list):
            relational_memories = []
        guarded_attention_target = self._is_guarded_relational_target(attention_target, relational_memories)
        guarded_relation_note = self._guarded_relational_note(attention_target, relational_memories)
        opportunity_level = str(interpretation.get("opportunity_level", "") or "low")
        recent_constraint_results = snapshot.get("recent_constraint_results", [])
        if not isinstance(recent_constraint_results, list):
            recent_constraint_results = []
        recent_world_changes = snapshot.get("recent_world_changes", [])
        if not isinstance(recent_world_changes, list):
            recent_world_changes = []
        vigilance_level = str(snapshot.get("vigilance_level", "") or "")
        distraction_level = str(snapshot.get("distraction_level", "") or "")
        effective_opportunity_level = opportunity_level
        if (recent_world_changes or vigilance_level == "elevated" or distraction_level == "elevated") and effective_opportunity_level == "low":
            effective_opportunity_level = "medium"
        candidate_intents = ["observe", "inspect_object", "self_protect"]
        if attention_target:
            candidate_intents.extend(["ask_probe", "share_info"])
        if effective_opportunity_level in {"medium", "high"}:
            candidate_intents.append("speak_public")
        if control_mode == "player_priority_assisted":
            candidate_intents.append("stay_silent")
        selected_intent = "observe"
        if guarded_attention_target or recent_constraint_results or str(interpretation.get("risk_level", "") or "low") in {"medium", "high"}:
            selected_intent = "self_protect"
        elif attention_target and effective_opportunity_level in {"medium", "high"}:
            selected_intent = "ask_probe"
        elif effective_opportunity_level in {"medium", "high"}:
            selected_intent = "speak_public"
        recommended_intents = [selected_intent, "observe"] if selected_intent != "observe" else ["observe"]
        if guarded_attention_target:
            recommended_intents = ["self_protect"] + [intent for intent in recommended_intents if intent != "self_protect"]
        if (recent_world_changes or vigilance_level == "elevated") and "speak_public" in candidate_intents:
            recommended_intents = ["speak_public"] + [intent for intent in recommended_intents if intent != "speak_public"]
        risk_notes = [str(item) for item in recent_constraint_results if str(item)]
        if guarded_relation_note:
            risk_notes = [guarded_relation_note] + [item for item in risk_notes if item != guarded_relation_note]
        why_this_now = str(
            guarded_relation_note
            or ""
            or (recent_world_changes[-1] if recent_world_changes else "")
            or (recent_constraint_results[-1] if recent_constraint_results else "")
            or ("heightened vigilance" if vigilance_level == "elevated" else "")
            or ("uncertain signal" if str(snapshot.get("distraction_level", "") or "") == "elevated" else "")
            or interpretation.get("interpreted_summary", "")
            or "model fallback"
        )
        role_consistency_hint = str(
            interpretation.get("inner_prompt_candidate", "")
            or guarded_relation_note
            or (recent_world_changes[-1] if recent_world_changes else "")
            or (recent_constraint_results[-1] if recent_constraint_results else "")
            or ("heightened vigilance" if vigilance_level == "elevated" else "")
            or ("uncertain signal" if str(snapshot.get("distraction_level", "") or "") == "elevated" else "")
            or "keep within role"
        )
        return {
            "candidate_intents": candidate_intents,
            "selected_intent": selected_intent,
            "recommended_intents": recommended_intents,
            "risk_notes": risk_notes,
            "why_this_now": why_this_now,
            "role_consistency_hint": role_consistency_hint,
        }

    def _is_guarded_relational_target(self, attention_target: str, relational_memories: list[object]) -> bool:
        if attention_target == "":
            return False
        for entry in relational_memories:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("entity_id", "") or "") != attention_target:
                continue
            if str(entry.get("belief_type", "") or "") != "trust_level":
                continue
            if str(entry.get("value", "") or "") == "guarded":
                return True
        return False

    def _guarded_relational_note(self, attention_target: str, relational_memories: list[object]) -> str:
        if attention_target == "":
            return ""
        for entry in relational_memories:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("entity_id", "") or "") != attention_target:
                continue
            if str(entry.get("belief_type", "") or "") != "trust_level":
                continue
            if str(entry.get("value", "") or "") == "guarded":
                return f"guarded relation with {attention_target}"
        return ""
