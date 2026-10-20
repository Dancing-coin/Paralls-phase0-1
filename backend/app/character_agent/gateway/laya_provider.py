from __future__ import annotations

import json
import hashlib
from pathlib import Path
from collections.abc import Callable, Sequence
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LayaSystemOneProvider:
    """Dedicated adapter for the pinned Laya `/v1/systemone` protocol.

    Laya chooses only from the frozen candidate ids. It never supplies execution
    parameters, authority facts, or fallback decisions.
    """

    SOURCE_COMMIT = "68804629e8ccd9d616d48a40e87de9fabbeae069"
    CHECKPOINT_REVISION = "1720e3e3357cfe1e281542e223f8273b0890ca34"
    PROVIDER_REVISION = f"laya:{SOURCE_COMMIT}:{CHECKPOINT_REVISION}"
    OPTION_TOKEN_LIMIT = 48
    OPTION_HEAD_MAX_LEN = 256
    DEFAULT_MAX_LEN = 2091
    SUPPORTED_MAX_LEN = 8192

    def __init__(self, *, endpoint: str, timeout_seconds: float = 20.0, api_key: str = "",
                 option_tokenizer: Callable[[str], Sequence[int]] | None = None,
                 tokenizer_path: str | None = None, tokenizer_sha256: str = "",
                 require_option_token_validation: bool = False) -> None:
        endpoint = str(endpoint or "").strip().rstrip("/")
        if not endpoint:
            raise ValueError("laya provider endpoint is required")
        self.endpoint = endpoint if endpoint.endswith("/v1/systemone") else endpoint + "/v1/systemone"
        self.timeout_seconds = float(timeout_seconds)
        self.api_key = str(api_key or "").strip()
        self.last_call: dict[str, object] | None = None
        self.last_option_token_audit: dict[str, object] | None = None
        self.last_input_budget: dict[str, object] | None = None
        self.require_option_token_validation = require_option_token_validation
        self.tokenizer_sha256 = tokenizer_sha256
        if tokenizer_path:
            if option_tokenizer is not None:
                raise ValueError("configure either tokenizer_path or option_tokenizer")
            # Optional local runtime support; never download or install a tokenizer.
            from tokenizers import Tokenizer
            tokenizer_bytes = Path(tokenizer_path).read_bytes()
            actual_sha = "sha256:" + hashlib.sha256(tokenizer_bytes).hexdigest()
            if tokenizer_sha256 and tokenizer_sha256 != actual_sha:
                raise ValueError("laya tokenizer pin does not match artifact")
            tokenizer = Tokenizer.from_str(tokenizer_bytes.decode("utf-8"))
            tokenizer.no_truncation()
            tokenizer.no_padding()
            option_tokenizer = lambda text: tokenizer.encode(text, add_special_tokens=False).ids
            self.tokenizer_sha256 = actual_sha
        self.option_tokenizer = option_tokenizer
        self.sequence_tokenizer = option_tokenizer

    def build_wire_request(self, request: dict[str, object]) -> dict[str, object]:
        """Validate frozen inputs and serialize the same payload used by live calls."""
        if request.get("task_kind") != "l3_planning":
            raise ValueError("laya provider only supports l3_planning")
        context = request.get("context")
        if not isinstance(context, dict):
            raise ValueError("laya provider requires a context object")
        raw_candidates = context.get("candidate_intents", [])
        if not isinstance(raw_candidates, list):
            raise ValueError("laya provider requires a frozen candidate list")
        candidates = [str(item).strip() for item in raw_candidates if str(item).strip()]
        if not candidates:
            raise ValueError("laya provider requires frozen candidates")
        if len(candidates) != len(set(candidates)):
            raise ValueError("laya provider requires unique frozen candidates")
        pinned_revision = context.get("provider_revision")
        if pinned_revision is not None and str(pinned_revision) != self.PROVIDER_REVISION:
            raise ValueError("laya provider revision is stale")
        frozen = context.get("frozen_candidates")
        mapping = context.get("candidate_mapping")
        if frozen is None and mapping is None and "candidate_digest" not in context:
            # Preserve the already verified direct adapter contract. The L3
            # prepared path always supplies the strict mapping below.
            mapping = {label: {"candidate_id": label, "wire_label": label, "description": label} for label in candidates}
        else:
            if not isinstance(frozen, list) or not isinstance(mapping, dict):
                raise ValueError("laya provider requires a frozen candidate mapping")
            frozen_labels = [
                str(item.get("wire_label", "") or "")
                for item in frozen
                if isinstance(item, dict) and str(item.get("wire_label", "") or "")
            ]
            if frozen_labels != candidates:
                raise ValueError("laya candidate order does not match frozen mapping")
            if set(mapping) != set(candidates):
                raise ValueError("laya candidate mapping is incomplete")
            if not str(context.get("candidate_digest", "") or ""):
                raise ValueError("laya candidate mapping digest is required")
            for index, label in enumerate(candidates):
                record = mapping.get(label)
                if not isinstance(record, dict) or str(record.get("candidate_id", "") or "") == "":
                    raise ValueError("laya candidate mapping is invalid")
                pins = record.get("revision_pins", {})
                if not isinstance(pins, dict):
                    raise ValueError("laya candidate revision pins are invalid")
                if record.get("diagnosis"):
                    raise ValueError("laya cannot receive diagnosed candidates")
                if record != frozen[index] or record.get("wire_label") != label:
                    raise ValueError("laya candidate mapping does not match frozen record")
                # Import at the boundary to avoid the planner/provider import
                # cycle. A caller cannot hand-edit either copy of a description.
                from app.character_agent.planning.l3_planner import CandidateCompiler
                if (
                    record.get("description_contract_revision") not in {
                        CandidateCompiler.DESCRIPTION_CONTRACT_REVISION,
                        CandidateCompiler.HISTORICAL_DESCRIPTION_CONTRACT_REVISION,
                    }
                    or record.get("description") != CandidateCompiler._semantic_description(record)
                ):
                    raise ValueError("laya candidate semantic description is not compiler-generated")
                if record.get("target_refs") and str(record.get("target_visibility", "") or "") not in {"visible", "none"}:
                    raise ValueError("laya target is invalid")
        state = self._state(context)
        payload = {
            "state": state,
            "model": "multilingual",
            "questions": {
                "choice": {
                    "type": "choice",
                    "instructions": "Choose exactly one complete action and target from the frozen candidates.",
                    "criteria": {
                        candidate: str((mapping.get(candidate) or {}).get("description", candidate) or candidate)
                        for candidate in candidates
                    },
                }
            },
        }
        self._validate_option_tokens(context, payload["questions"]["choice"]["criteria"])
        budget = self._validate_input_budget(context, state, payload["questions"]["choice"]["criteria"])
        if budget is not None:
            payload.update({"max_len": budget["max_len"], "head_max_len": budget["head_max_len"]})
        return payload

    def _validate_input_budget(self, context: dict[str, object], state: str,
                               criteria: dict[str, str]) -> dict[str, int] | None:
        """Validate the complete head + state + closing SEP before transport.

        The ordinary runtime keeps its historical wire shape unless a caller
        opts into the explicit budget contract. Calibration always opts in.
        """
        requested = context.get("max_len")
        required = context.get("input_budget_required") is True or requested is not None
        if not required:
            return None
        if self.sequence_tokenizer is None or not self.tokenizer_sha256:
            raise ValueError("input budget cannot be verified without a pinned tokenizer")
        if not isinstance(requested, int) or isinstance(requested, bool) or requested <= 0:
            raise ValueError("input budget max_len is missing or invalid")
        if requested > self.SUPPORTED_MAX_LEN:
            raise ValueError(f"input budget max_len exceeds supported limit {self.SUPPORTED_MAX_LEN}")
        head_max_len = context.get("head_max_len", self.OPTION_HEAD_MAX_LEN)
        if not isinstance(head_max_len, int) or isinstance(head_max_len, bool) or head_max_len <= 0:
            raise ValueError("input budget head_max_len is missing or invalid")
        if head_max_len > requested:
            raise ValueError("input budget head_max_len exceeds max_len")
        def count(text: str) -> int:
            ids = self.sequence_tokenizer(text)
            if not isinstance(ids, Sequence) or isinstance(ids, (str, bytes)):
                raise ValueError("input budget tokenizer returned unverifiable ids")
            return len(ids)

        # Pinned common.build_head encodes the instruction and every rendered
        # option independently, with CLS/SEP/MASK ids inserted between spans.
        instruction = "choice question: Choose exactly one complete action and target from the frozen candidates."
        instruction_tokens = count(instruction.replace("<mask>", " "))
        option_tokens = [count((" " + f"{label}: {description}").replace("<mask>", " "))
                         for label, description in criteria.items()]
        head_tokens = 3 + instruction_tokens + sum(1 + size for size in option_tokens)
        state_tokens = count(state.replace("<mask>", " "))
        required_tokens = head_tokens + state_tokens + 1
        if any(size >= self.OPTION_TOKEN_LIMIT for size in option_tokens):
            raise ValueError("input budget option would be truncated")
        if head_tokens > head_max_len:
            raise ValueError(f"input budget head exceeds head_max_len: {head_tokens}>{head_max_len}")
        if required_tokens > requested:
            raise ValueError(
                f"input budget exceeded before transport: required={required_tokens}, max_len={requested}"
            )
        self.last_input_budget = {
            "state_tokens": state_tokens,
            "head_tokens": head_tokens,
            "required_tokens": required_tokens,
            "max_len": requested,
            "head_max_len": head_max_len,
            "truncated": False,
        }
        return {"max_len": requested, "head_max_len": head_max_len}

    def _validate_option_tokens(self, context: dict[str, object], criteria: dict[str, str]) -> None:
        required = self.require_option_token_validation or context.get("option_token_validation_required") is True
        self.last_option_token_audit = None
        if required:
            if self.option_tokenizer is None or not self.tokenizer_sha256:
                raise ValueError("laya formal option validation requires a pinned tokenizer")
            if context.get("option_tokenizer_sha256") != self.tokenizer_sha256:
                raise ValueError("laya option tokenizer pin is missing or stale")
            from app.character_agent.planning.l3_planner import CandidateCompiler
            frozen = context.get("frozen_candidates")
            if not isinstance(frozen, list) or not frozen or any(
                not isinstance(item, dict) or item.get("description_contract_revision") != CandidateCompiler.DESCRIPTION_CONTRACT_REVISION
                for item in frozen
            ):
                raise ValueError("laya formal option validation requires current candidate semantics")
        if self.option_tokenizer is None:
            return
        counts = {}
        for label, description in criteria.items():
            # Pinned Laya common.build_head: leading space, render_options label,
            # mask sanitization, and raw encoding without special tokens.
            text = " " + f"{label}: {description}".replace("<mask>", " ")
            tokens = self.option_tokenizer(text)
            if not isinstance(tokens, Sequence) or isinstance(tokens, (str, bytes)):
                raise ValueError("laya option tokenizer must return raw token ids")
            counts[label] = len(tokens)
            if counts[label] >= self.OPTION_TOKEN_LIMIT:
                raise ValueError(f"laya option token limit exceeded: {label}={counts[label]} requires <{self.OPTION_TOKEN_LIMIT}")
        # build_head applies a second per-option truncation when mask+option
        # spans leave fewer than 16 tokens in the pinned 256-token head.
        if sum(count + 1 for count in counts.values()) > self.OPTION_HEAD_MAX_LEN - 16:
            raise ValueError("laya option head budget would truncate options")
        self.last_option_token_audit = {
            "tokenizer_sha256": self.tokenizer_sha256 or None,
            "option_token_limit": self.OPTION_TOKEN_LIMIT,
            "head_max_len": self.OPTION_HEAD_MAX_LEN,
            "counts": counts,
            "truncated": False,
            "formal_pins_verified": required,
        }

    def complete(self, request: dict[str, object]) -> dict[str, object]:
        payload = self.build_wire_request(request)
        context = request["context"]
        candidates = list(payload["questions"]["choice"]["criteria"])
        self.last_call = {"request": payload, "response": None, "latency_ms": None}
        started = monotonic()
        try:
            response = self._post(payload)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise ValueError(f"laya provider request failed: {exc.__class__.__name__}") from exc
        elapsed_ms = round((monotonic() - started) * 1000.0, 3)
        self.last_call.update(response=response, latency_ms=elapsed_ms)
        answer = ((response.get("answers") or {}).get("choice") if isinstance(response, dict) else None)
        if not isinstance(answer, dict):
            raise ValueError("laya response missing choice answer")
        selected = str(answer.get("choice", "") or "").strip()
        if selected not in candidates:
            raise ValueError("laya choice is not in frozen candidates")
        probabilities = answer.get("probabilities", {})
        if not isinstance(probabilities, dict):
            probabilities = {}
        frame = self._active_goal_frame(context.get("active_goal_frame"))
        result = {
            "candidate_intents": candidates,
            "selected_intent": selected,
            "recommended_intents": [selected],
            "risk_notes": [],
            "why_this_now": f"Laya selected frozen candidate {selected}",
            "role_consistency_hint": "laya-multilingual",
            "active_goal_tags": [str(item) for item in context.get("active_goal_tags", []) or []],
            "active_goal_frame": frame,
            "planning_status": "model",
            "fallback_mode": None,
            "laya_evidence": {
                "source_commit": self.SOURCE_COMMIT,
                "checkpoint_revision": self.CHECKPOINT_REVISION,
                "provider_revision": self.PROVIDER_REVISION,
                "frozen_request": self._frozen_request_evidence(context, candidates),
                "candidate_order": list(candidates),
                "mapping_digest": str(context.get("candidate_digest", "") or ""),
                "expiry": context.get("expiry", context.get("expires_at")),
                "choice_probabilities": {str(k): float(v) for k, v in probabilities.items() if isinstance(v, (int, float))},
                "latency_ms": elapsed_ms,
            },
        }
        self.last_call = {
            "request": payload,
            "response": response,
            "latency_ms": elapsed_ms,
            "frozen_request": self._frozen_request_evidence(context, candidates),
        }
        return result

    def _post(self, payload: dict[str, object]) -> dict[str, object]:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            with urlopen(Request(self.endpoint, data=body, headers=headers, method="POST"), timeout=self.timeout_seconds) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"laya provider request failed: {exc.__class__.__name__}") from exc
        if not isinstance(result, dict):
            raise ValueError("laya provider response must be an object")
        return result

    @staticmethod
    def _state(context: dict[str, object]) -> str:
        # Reuse the existing runtime profile projection; raw dossiers and private
        # archives are never serialized by this boundary.
        from app.character_agent.gateway.prompt_policy import CharacterPromptPolicy

        explicit = context.get("laya_state")
        profile = context.get("effective_profile", context.get("profile"))
        payload = {}
        if isinstance(explicit, str) and explicit.strip():
            payload["event"] = explicit.strip()
        else:
            payload.update(interpretation=context.get("interpretation") or {},
                           snapshot=context.get("snapshot") or {})
        if isinstance(profile, dict) and profile:
            payload["effective_profile_summary"] = CharacterPromptPolicy()._profile_summary(profile)
        # These are the actor-scoped, frozen L3 inputs, including already
        # budgeted recall. Do not copy the whole context: it also holds audit
        # metadata and may hold evaluation truth or unprojected profile data.
        for key in (
            "active_goal_tags", "active_goal_frame", "current_goal_state",
            "memory", "semantic_cards", "need_tension_state", "dynamic_state",
            "supervision_state", "background_agenda_state", "unresolved_tensions",
        ):
            if key in context:
                payload[key] = context[key]
        contract_fields = {
            "capability_envelope": ("actor_id", "turn_id", "capability_revision", "envelope_revision",
                "cognitive_limits", "active_domains", "allowed_action_families", "blocked_action_families",
                "degradation_reasons", "source_refs", "revision_pins", "envelope_digest"),
            "cognition_policy": ("policy_id", "actor_id", "turn_id", "tier", "provider_thinking_effort",
                "memory", "reasoning", "dialogue", "reasons", "source_refs", "revision_pins",
                "envelope_digest", "policy_digest"),
        }
        for key, fields in contract_fields.items():
            value = context.get(key)
            if isinstance(value, dict):
                payload[key] = {field: value[field] for field in fields if field in value}
        # Direct adapter callers with only an explicit event keep their contract.
        if set(payload) == {"event"}:
            return payload["event"]
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)

    @classmethod
    def _frozen_request_evidence(cls, context: dict[str, object], candidates: list[str]) -> dict[str, object]:
        """Copy existing prepared pins when present; never invent authority values."""
        evidence: dict[str, object] = {"candidate_ids": list(candidates)}
        for field in (
            "source_ref",
            "frame_digest",
            "expiry",
            "expires_at",
            "policy_revision",
            "input_revision_vector",
            "memory_revision_vector",
        ):
            if field in context:
                evidence[field] = context[field]
        frame = context.get("frame")
        if isinstance(frame, dict):
            for field in (
                "frame_digest",
                "turn_id",
                "policy_revision",
                "input_revision_vector",
                "memory_revision_vector",
            ):
                if field not in evidence and field in frame:
                    evidence[field] = frame[field]
        return evidence

    @staticmethod
    def _active_goal_frame(value: object) -> dict[str, object]:
        raw = dict(value) if isinstance(value, dict) else {}
        return {
            "primary_goal": str(raw.get("primary_goal", "preserve_continuity") or "preserve_continuity"),
            "long_term_goal": str(raw.get("long_term_goal", "") or ""),
            "mid_term_strategy": str(raw.get("mid_term_strategy", "") or ""),
            "immediate_goal": str(raw.get("immediate_goal", raw.get("primary_goal", "preserve_continuity")) or "preserve_continuity"),
            "supporting_goals": list(raw.get("supporting_goals", []) or []),
            "blockers": list(raw.get("blockers", []) or []),
            "goal_sources": list(raw.get("goal_sources", []) or []),
            "urgency": str(raw.get("urgency", "low") or "low"),
            "dominant_goal_id": str(raw.get("dominant_goal_id", "goal_preserve_continuity") or "goal_preserve_continuity"),
            "preserved_goal_ids": list(raw.get("preserved_goal_ids", []) or []),
            "suppressed_goal_ids": list(raw.get("suppressed_goal_ids", []) or []),
            "goal_arbitration_summary": str(raw.get("goal_arbitration_summary", "") or ""),
            "goal_portfolio": list(raw.get("goal_portfolio", []) or []),
        }
