from __future__ import annotations

import json
import os
from dataclasses import replace, dataclass
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import settings


_DEFAULT_ENDPOINTS = {
    "deepseek": "https://api.deepseek.com",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "seed_doubao": "",
    "openai_compatible": "",
}
_DEFAULT_MODELS = {
    "deepseek": "deepseek-chat",
    "qwen": "qwen3.7-plus",
    "seed_doubao": "doubao-seed-2.0-pro",
    "openai_compatible": "openai-compatible-chat",
}


@dataclass(frozen=True)
class CharacterModelCallEvidence:
    task_kind: str
    provider_kind: str
    model_name: str
    endpoint_host: str
    transport_attempted: bool
    transport_succeeded: bool
    fallback_used: bool
    error_type: str | None = None


class CharacterModelProvider:
    def __init__(
        self,
        *,
        provider_kind: str | None = None,
        endpoint_url: str | None = None,
        api_key: str | None = None,
        model_name: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        configured_provider_kind = provider_kind if provider_kind is not None else settings.character_model_provider_kind
        self._provider_kind = str(configured_provider_kind or "").strip() or "qwen"
        self._endpoint_url = self._default_endpoint(endpoint_url, use_settings=provider_kind is None)
        self._api_key = self._default_api_key(api_key, use_settings=provider_kind is None)
        self._model_name = self._default_model(model_name, use_settings=provider_kind is None)
        self._timeout_seconds = (
            float(timeout_seconds)
            if timeout_seconds is not None
            else float(settings.character_model_timeout_seconds)
        )
        self._last_call_evidence: CharacterModelCallEvidence | None = None

    @property
    def last_call_evidence(self) -> CharacterModelCallEvidence | None:
        if self._last_call_evidence is None:
            return None
        return replace(self._last_call_evidence)

    def complete(self, request: dict[str, object]) -> dict[str, object]:
        route = request.get("route", {})
        task_kind = str(request.get("task_kind", "") or "")
        provider_kind = self._provider_kind
        if isinstance(route, dict):
            provider_kind = str(route.get("provider_kind", provider_kind) or provider_kind)
        require_online = settings.character_model_require_online or os.getenv("CHARACTER_MODEL_REQUIRE_ONLINE", "").strip() == "1"
        if provider_kind == "local":
            if require_online:
                raise ValueError("online character model required; local provider is disabled")
            output = self._offline_complete(request)
            self._record_evidence(task_kind=task_kind, provider_kind=provider_kind, fallback_used=True)
            return output
        if provider_kind == "deepseek":
            return self._complete_strict(task_kind=task_kind, provider_kind=provider_kind, request=request)
        if provider_kind in {"qwen", "seed_doubao", "openai_compatible"}:
            if (not self._endpoint_url or not self._api_key) and not self._requires_model_semantic_ownership(task_kind):
                if require_online:
                    raise ValueError("online character model required; provider credentials are missing")
                output = self._offline_complete(request)
                self._record_evidence(task_kind=task_kind, provider_kind=provider_kind, fallback_used=True)
                return output
            return self._complete_strict(task_kind=task_kind, provider_kind=provider_kind, request=request)
        if provider_kind == "hybrid":
            try:
                return self._complete_strict(task_kind=task_kind, provider_kind=provider_kind, request=request)
            except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
                if require_online:
                    raise ValueError("online character model required; hybrid fallback is disabled")
                if self._requires_model_semantic_ownership(task_kind):
                    raise
                output = self._offline_complete(request)
                self._record_evidence(task_kind=task_kind, provider_kind=provider_kind, fallback_used=True)
                return output
        if self._requires_model_semantic_ownership(task_kind):
            self._record_evidence(
                task_kind=task_kind,
                provider_kind=provider_kind,
                fallback_used=False,
                error_type="ValueError",
            )
            raise ValueError(f"unsupported provider_kind for model-led task: {provider_kind or 'unknown'}")
        output = self._offline_complete(request)
        self._record_evidence(task_kind=task_kind, provider_kind=provider_kind, fallback_used=True)
        return output

    def stream_dialogue(self, request: dict[str, object], *, cancelled):
        """Stream dialogue display text only; L2/L3 keep `complete` unchanged."""
        if str(request.get("task_kind", "") or "") != "dialogue_generation":
            raise ValueError("stream_dialogue only supports dialogue_generation")
        if cancelled():
            yield {"event": "cancelled"}
            return

        route = request.get("route", {})
        provider_kind = self._provider_kind
        if isinstance(route, dict):
            provider_kind = str(route.get("provider_kind", provider_kind) or provider_kind)
        if provider_kind == "local" or (
            provider_kind in {"qwen", "seed_doubao", "openai_compatible"}
            and (not self._endpoint_url or not self._api_key)
        ):
            output = self._offline_complete(request)
            self._record_evidence(task_kind="dialogue_generation", provider_kind=provider_kind, fallback_used=True)
            yield from self._stream_local_dialogue(output, cancelled=cancelled, fallback_used=True)
            return

        emitted_delta = False
        try:
            for event in self._stream_via_deepseek(request, cancelled=cancelled):
                if event["event"] == "delta":
                    emitted_delta = True
                yield event
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
            if provider_kind == "hybrid" and not emitted_delta and not cancelled():
                output = self._offline_complete(request)
                self._record_evidence(task_kind="dialogue_generation", provider_kind=provider_kind, fallback_used=True)
                yield from self._stream_local_dialogue(output, cancelled=cancelled, fallback_used=True)
                return
            raise

    def _stream_local_dialogue(self, output: dict[str, object], *, cancelled, fallback_used: bool):
        content = str(output.get("content", "") or "")
        if cancelled():
            yield {"event": "cancelled"}
            return
        yield {"event": "delta", "delta": content}
        yield {"event": "completed", "output": output, "fallback_used": fallback_used}

    def _stream_via_deepseek(self, request: dict[str, object], *, cancelled):
        if not self._endpoint_url or not self._api_key:
            raise ValueError("character model provider requires endpoint and api key")
        body = json.dumps(self._build_deepseek_stream_request(request)).encode("utf-8")
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self._api_key}"}
        req = Request(self._deepseek_chat_completions_url(), data=body, headers=headers, method="POST")
        chunks: list[str] = []
        with urlopen(req, timeout=self._timeout_seconds) as response:
            for raw_line in response:
                if cancelled():
                    yield {"event": "cancelled"}
                    return
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                delta = self._stream_delta_from_payload(json.loads(data))
                if delta:
                    chunks.append(delta)
                    yield {"event": "delta", "delta": delta}
        content = "".join(chunks).strip()
        if not content:
            raise ValueError("character dialogue stream completed without text")
        self._record_evidence(
            task_kind="dialogue_generation",
            provider_kind=self._provider_kind,
            transport_attempted=True,
            transport_succeeded=True,
            fallback_used=False,
        )
        yield {
            "event": "completed",
            "output": {"content": content, "tone": "neutral"},
            "fallback_used": False,
        }

    def _build_deepseek_stream_request(self, request: dict[str, object]) -> dict[str, object]:
        prompt = request.get("prompt", {})
        policy = request.get("policy", {})
        if not isinstance(prompt, dict):
            prompt = {}
        if not isinstance(policy, dict):
            policy = {}
        return {
            "model": self._model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"{str(prompt.get('system_instruction', '') or '')}\n"
                        "Return only the character's spoken dialogue text. Do not return JSON or labels."
                    ),
                },
                {"role": "user", "content": str(prompt.get("user_instruction", "") or "")},
            ],
            "temperature": float(policy.get("temperature", 0.2) or 0.2),
            "max_tokens": int(policy.get("max_tokens", 400) or 400),
            "stream": True,
        }

    def _stream_delta_from_payload(self, payload: object) -> str:
        if not isinstance(payload, dict):
            raise ValueError("character dialogue stream event must be an object")
        choices = payload.get("choices", [])
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            return ""
        delta = choices[0].get("delta", {})
        return str(delta.get("content", "") or "") if isinstance(delta, dict) else ""

    def _complete_strict(
        self,
        *,
        task_kind: str,
        provider_kind: str,
        request: dict[str, object],
    ) -> dict[str, object]:
        try:
            output = self._complete_via_deepseek(request)
            self._record_evidence(
                task_kind=task_kind,
                provider_kind=provider_kind,
                transport_attempted=True,
                transport_succeeded=True,
                fallback_used=False,
            )
            return self._coerce_output_for_task(task_kind, output)
        except Exception as exc:
            self._record_evidence(
                task_kind=task_kind,
                provider_kind=provider_kind,
                transport_attempted=bool(self._endpoint_url and self._api_key),
                transport_succeeded=False,
                fallback_used=False,
                error_type=exc.__class__.__name__,
            )
            raise

    def _default_endpoint(self, endpoint_url: str | None, *, use_settings: bool = True) -> str:
        if endpoint_url:
            return endpoint_url.strip()
        if use_settings and settings.character_model_endpoint:
            return settings.character_model_endpoint.strip()
        return _DEFAULT_ENDPOINTS.get(self._provider_kind, "").strip()

    def _default_api_key(self, api_key: str | None, *, use_settings: bool = True) -> str:
        if api_key:
            return api_key.strip()
        if use_settings and settings.character_model_api_key:
            return settings.character_model_api_key.strip()
        return ""

    def _default_model(self, model_name: str | None, *, use_settings: bool = True) -> str:
        if model_name:
            return model_name.strip()
        if use_settings and settings.character_model_model:
            return settings.character_model_model.strip()
        return _DEFAULT_MODELS.get(self._provider_kind, _DEFAULT_MODELS["qwen"]).strip()

    def _requires_model_semantic_ownership(self, task_kind: str) -> bool:
        return task_kind in {"l2_reasoning", "l3_planning"}

    def _complete_via_deepseek(self, request: dict[str, object]) -> dict[str, object]:
        if not self._endpoint_url or not self._api_key:
            raise ValueError("character model provider requires endpoint and api key")
        body = json.dumps(self._build_deepseek_request(request)).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        req = Request(self._deepseek_chat_completions_url(), data=body, headers=headers, method="POST")
        with urlopen(req, timeout=self._timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return self._normalize_deepseek_response(payload)

    def _deepseek_chat_completions_url(self) -> str:
        if self._endpoint_url.endswith("/chat/completions"):
            return self._endpoint_url
        return self._endpoint_url.rstrip("/") + "/chat/completions"

    def _build_deepseek_request(self, request: dict[str, object]) -> dict[str, object]:
        prompt = request.get("prompt", {})
        policy = request.get("policy", {})
        if not isinstance(prompt, dict):
            prompt = {}
        if not isinstance(policy, dict):
            policy = {}
        required_output_keys = prompt.get("required_output_keys", [])
        return {
            "model": self._model_name,
            "messages": [
                {
                    "role": "system",
                    "content": str(prompt.get("system_instruction", "") or ""),
                },
                {
                    "role": "user",
                    "content": (
                        f"{str(prompt.get('user_instruction', '') or '')}\n"
                        f"Return valid JSON only. Required keys: {json.dumps(required_output_keys, ensure_ascii=True)}."
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
            "temperature": float(policy.get("temperature", 0.1) or 0.1),
            "max_tokens": int(policy.get("max_tokens", 800) or 800),
        }

    def _normalize_deepseek_response(self, payload: object) -> dict[str, object]:
        if not isinstance(payload, dict):
            raise ValueError("deepseek response must be a JSON object")
        choices = payload.get("choices", [])
        if not isinstance(choices, list) or not choices:
            raise ValueError("deepseek response must include at least one choice")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError("deepseek choice must be a JSON object")
        message = first_choice.get("message", {})
        if not isinstance(message, dict):
            raise ValueError("deepseek choice message must be a JSON object")
        content = str(message.get("content", "") or "").strip()
        if not content:
            raise ValueError("deepseek response content must not be empty")
        normalized = json.loads(content)
        if not isinstance(normalized, dict):
            raise ValueError("deepseek response content must decode to a JSON object")
        return normalized

    def _coerce_output_for_task(self, task_kind: str, output: dict[str, object]) -> dict[str, object]:
        normalized = dict(output)
        if task_kind == "l3_planning":
            normalized = self._coerce_l3_output(normalized)
        return normalized

    def _coerce_l3_output(self, output: dict[str, object]) -> dict[str, object]:
        normalized = dict(output)
        for key in ("candidate_intents", "recommended_intents", "risk_notes"):
            normalized[key] = self._coerce_string_list(normalized.get(key, []))

        selected_intent = str(normalized.get("selected_intent", "") or "").strip()
        candidate_intents = [str(item).strip() for item in normalized.get("candidate_intents", []) if str(item).strip() != ""]
        recommended_intents = [str(item).strip() for item in normalized.get("recommended_intents", []) if str(item).strip() != ""]
        if not isinstance(normalized.get("active_goal_tags"), list):
            normalized["active_goal_tags"] = []

        fallback_goal = selected_intent or (candidate_intents[0] if candidate_intents else "preserve_continuity")
        if not recommended_intents and selected_intent != "":
            normalized["recommended_intents"] = [selected_intent]

        goal_frame = normalized.get("active_goal_frame", {})
        if not isinstance(goal_frame, dict):
            goal_frame = {}
        primary_goal = str(goal_frame.get("primary_goal", "") or "").strip()
        if primary_goal == "":
            normalized["active_goal_frame"] = {
                "primary_goal": fallback_goal,
                "long_term_goal": str(goal_frame.get("long_term_goal", "") or fallback_goal),
                "mid_term_strategy": str(goal_frame.get("mid_term_strategy", "") or "hold_position"),
                "immediate_goal": str(goal_frame.get("immediate_goal", "") or fallback_goal),
                "supporting_goals": goal_frame.get("supporting_goals", []) if isinstance(goal_frame.get("supporting_goals", []), list) else [],
                "blockers": goal_frame.get("blockers", []) if isinstance(goal_frame.get("blockers", []), list) else [],
                "goal_sources": goal_frame.get("goal_sources", []) if isinstance(goal_frame.get("goal_sources", []), list) and goal_frame.get("goal_sources", []) else ["model_output_coercion"],
                "urgency": str(goal_frame.get("urgency", "low") or "low"),
                "dominant_goal_id": str(goal_frame.get("dominant_goal_id", "") or f"goal_{fallback_goal}"),
                "preserved_goal_ids": goal_frame.get("preserved_goal_ids", []) if isinstance(goal_frame.get("preserved_goal_ids", []), list) else [],
                "suppressed_goal_ids": goal_frame.get("suppressed_goal_ids", []) if isinstance(goal_frame.get("suppressed_goal_ids", []), list) else [],
                "goal_arbitration_summary": str(
                    goal_frame.get("goal_arbitration_summary", "")
                    or normalized.get("why_this_now", "")
                    or "provider returned a sparse goal frame; runtime applied a minimal executable fallback"
                ),
                "goal_portfolio": goal_frame.get("goal_portfolio", []) if isinstance(goal_frame.get("goal_portfolio", []), list) else [],
            }
        else:
            normalized["active_goal_frame"] = goal_frame
        return normalized

    def _coerce_string_list(self, value: object) -> list[object]:
        if isinstance(value, list):
            return value
        text = str(value or "").strip()
        if text == "":
            return []
        return [text]

    def _offline_complete(self, request: dict[str, object]) -> dict[str, object]:
        task_kind = str(request.get("task_kind", "") or "")
        context = request.get("context", {})
        if not isinstance(context, dict):
            context = {}
        if task_kind == "dialogue_generation":
            return self._offline_dialogue_output(context)
        if task_kind == "l3_planning":
            return self._offline_l3_output(context)
        return self._offline_l2_output(context)

    def _offline_dialogue_output(self, context: dict[str, object]) -> dict[str, object]:
        event = context.get("event", {})
        if not isinstance(event, dict):
            event = {}
        content = str(event.get("content", "") or "")
        lowered = content.lower()
        if "letter" in lowered:
            return {
                "content": "I saw something move near the desk.",
                "tone": "alert",
            }
        return {
            "content": "I am here. What do you need?",
            "tone": "neutral",
        }

    def _offline_l2_output(self, context: dict[str, object]) -> dict[str, object]:
        snapshot = context.get("snapshot", {})
        event = context.get("event", {})
        if not isinstance(snapshot, dict):
            snapshot = {}
        if not isinstance(event, dict):
            event = {}
        actor_id = str(event.get("actor_id", "") or snapshot.get("actor_id", "") or "")
        summary = str(
            event.get("perceived_summary", "")
            or event.get("presentation_hint", "")
            or snapshot.get("perceived_summary", "")
            or "model cognition unavailable; local-only stub active"
        )
        interpretation_type = "cognition_unavailable"
        if str(event.get("body_state_class", "") or "") or bool(snapshot.get("body_state_hints", [])):
            interpretation_type = "body_state"
        salience_score = float(event.get("clarity_score", snapshot.get("clarity_score", 0.5)) or 0.5)
        salience_boost = event.get("salience_boost")
        if isinstance(salience_boost, (int, float)):
            salience_score = max(salience_score, min(1.0, max(0.0, float(salience_boost))))
        attention_targets = snapshot.get("attention_targets", [])
        if not isinstance(attention_targets, list):
            attention_targets = []
        attention_target = str(
            attention_targets[0]
            if attention_targets
            else event.get("target_actor_id", "") or event.get("target_object_id", "") or event.get("target_environment_id", "") or ""
        )
        recent_world_changes = snapshot.get("recent_world_changes", [])
        if not isinstance(recent_world_changes, list):
            recent_world_changes = []
        recent_constraint_results = snapshot.get("recent_constraint_results", [])
        if not isinstance(recent_constraint_results, list):
            recent_constraint_results = []
        active_anomalies = snapshot.get("active_anomalies", [])
        if not isinstance(active_anomalies, list):
            active_anomalies = []
        vigilance_level = str(snapshot.get("vigilance_level", "") or "")
        distraction_level = str(snapshot.get("distraction_level", "") or "")
        opportunity_level = "medium" if recent_world_changes or str(snapshot.get("last_siming_catalyst", "") or "") != "" else "low"
        if vigilance_level == "elevated" and opportunity_level == "low":
            opportunity_level = "medium"
        if str(event.get("percept_channel", "") or "") == "siming" and interpretation_type != "body_state":
            risk_level = "low"
        else:
            risk_level = "medium" if interpretation_type == "body_state" or active_anomalies or recent_constraint_results else "low"
        ambiguity_level = "high"
        return {
            "interpreted_summary": summary,
            "interpretation_type": interpretation_type,
            "salience_score": salience_score,
            "ambiguity_level": ambiguity_level,
            "risk_level": risk_level,
            "opportunity_level": opportunity_level,
            "attention_target": attention_target or None,
            "inner_prompt_candidate": "local_only_stub",
            "belief_deltas": [],
            "social_deltas": [],
            "higher_order_deltas": [],
            "dynamic_state_delta": {},
            "goal_hints": [],
            "reasoning_trace_summary": f"local_only_stub:{actor_id}",
            "cognition_status": "continuity_floor",
            "fallback_mode": "local_only_stub",
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
        salience_score = float(interpretation.get("salience_score", 0.0) or 0.0)
        candidate_intents = ["observe", "self_protect"]
        if control_mode == "player_priority_assisted":
            candidate_intents.append("stay_silent")
        selected_intent = "observe"
        if recent_constraint_results or str(interpretation.get("risk_level", "") or "low") in {"medium", "high"}:
            selected_intent = "self_protect"
        elif control_mode == "player_priority_assisted":
            selected_intent = "stay_silent"
        recommended_intents = [selected_intent]
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
        active_goal_tags = ["preserve_continuity"]
        active_goal_frame = {
            "primary_goal": "preserve_continuity",
            "long_term_goal": "preserve_continuity",
            "mid_term_strategy": "hold_position",
            "immediate_goal": "preserve_continuity",
            "supporting_goals": [],
            "blockers": [],
            "goal_sources": ["local_only_fallback"],
            "urgency": "low",
            "dominant_goal_id": "goal_preserve_continuity",
            "preserved_goal_ids": [],
            "suppressed_goal_ids": [],
            "goal_arbitration_summary": "local continuity shell keeps only a minimal continuity goal active",
            "goal_portfolio": [
                {
                    "goal_id": "goal_preserve_continuity",
                    "goal": "preserve_continuity",
                    "horizon": "long",
                    "status": "active",
                    "priority": 0.5,
                    "urgency": "low",
                    "source": "local_only_fallback",
                    "supporting_evidence": ["continuity_floor"],
                }
            ],
        }
        if selected_intent == "self_protect":
            active_goal_tags = ["protect_self"]
            active_goal_frame = {
                "primary_goal": "protect_self",
                "long_term_goal": "preserve_safety",
                "mid_term_strategy": "stabilize_self",
                "immediate_goal": "protect_self",
                "supporting_goals": [],
                "blockers": ["recent_constraint_pressure"] if recent_constraint_results else [],
                "goal_sources": ["local_only_fallback"],
                "urgency": "high" if recent_constraint_results else "medium",
                "dominant_goal_id": "goal_protect_self",
                "preserved_goal_ids": ["goal_preserve_continuity"],
                "suppressed_goal_ids": [],
                "goal_arbitration_summary": "local continuity shell prioritizes self-protection while preserving continuity as a background goal",
                "goal_portfolio": [
                    {
                        "goal_id": "goal_protect_self",
                        "goal": "protect_self",
                        "horizon": "short",
                        "status": "active",
                        "priority": 0.8,
                        "urgency": "high" if recent_constraint_results else "medium",
                        "source": "local_only_fallback",
                        "blockers": ["recent_constraint_pressure"] if recent_constraint_results else [],
                        "supporting_evidence": risk_notes,
                    },
                    {
                        "goal_id": "goal_preserve_continuity",
                        "goal": "preserve_continuity",
                        "horizon": "long",
                        "status": "active",
                        "priority": 0.5,
                        "urgency": "low",
                        "source": "local_only_fallback",
                        "supporting_evidence": ["continuity_floor"],
                    },
                ],
            }
        return {
            "candidate_intents": candidate_intents,
            "selected_intent": selected_intent,
            "recommended_intents": recommended_intents,
            "risk_notes": risk_notes,
            "why_this_now": why_this_now,
            "role_consistency_hint": role_consistency_hint,
            "active_goal_tags": active_goal_tags,
            "active_goal_frame": active_goal_frame,
            "planning_status": "continuity_floor",
            "fallback_mode": "local_only_stub",
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

    def _is_guarded_attention_target(
        self,
        attention_target: str,
        relational_memories: list[object],
        social_memories: list[object],
    ) -> bool:
        if self._is_guarded_relational_target(attention_target, relational_memories):
            return True
        if attention_target == "":
            return False
        for entry in social_memories:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("entity_id", "") or "") != attention_target:
                continue
            suspicion = entry.get("suspicion_baseline")
            if isinstance(suspicion, (int, float)) and float(suspicion) >= 0.75:
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

    def _record_evidence(
        self,
        *,
        task_kind: str,
        provider_kind: str,
        transport_attempted: bool = False,
        transport_succeeded: bool = False,
        fallback_used: bool = False,
        error_type: str | None = None,
    ) -> None:
        self._last_call_evidence = CharacterModelCallEvidence(
            task_kind=task_kind,
            provider_kind=provider_kind,
            model_name=self._model_name,
            endpoint_host=_endpoint_host(self._endpoint_url),
            transport_attempted=transport_attempted,
            transport_succeeded=transport_succeeded,
            fallback_used=fallback_used,
            error_type=error_type,
        )


def _endpoint_host(endpoint_url: str) -> str:
    if not endpoint_url:
        return "not_configured"
    parsed = urlparse(endpoint_url if "://" in endpoint_url else f"https://{endpoint_url}")
    return parsed.hostname or "redacted_endpoint"
