from __future__ import annotations

import json
import time
from enum import StrEnum
from typing import Any, Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.world_runtime.intelligence_upgrade import PerceptionQueryFrame


class VLAProviderStatus(StrEnum):
    DISABLED = "disabled"
    BLOCKED_MISSING_CREDENTIALS = "blocked_missing_credentials"
    BLOCKED_MISSING_ARTIFACTS = "blocked_missing_artifacts"
    CONFIGURED_UNVERIFIED = "configured_unverified"
    MOCK_PROVIDER_VERIFIED = "mock_provider_verified"
    REAL_PROVIDER_VERIFIED = "real_provider_verified"
    TIMEOUT = "timeout"
    DEGRADED = "degraded"
    ERROR = "error"


class VLAAdvisoryRoute(StrEnum):
    ADVISORY_FAST = "advisory-fast"
    ADVISORY_DEEP = "advisory-deep"


class VLAProviderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    owner_kind: str
    owner_id: str
    query_frame: PerceptionQueryFrame
    subject_ref: str = ""
    target_ref: str = ""
    world_anchor_id: str = ""
    source_ref_lineage: list[str] = Field(default_factory=list)
    capture_root_id: str = ""
    capture_id: str = ""
    clock_domain: str = ""
    monotonic_tick: int | None = None
    source_frame_index: int | None = None
    artifact_refs: list[str] = Field(default_factory=list)
    structured_fact_refs: list[str] = Field(default_factory=list)
    grounding_entity_refs: list[str] = Field(default_factory=list)
    grounding_collider_refs: list[str] = Field(default_factory=list)
    grounding_anchor_refs: list[str] = Field(default_factory=list)
    grounding_affordance_refs: list[str] = Field(default_factory=list)
    context_namespace: str
    cache_namespace: str
    model_id: str
    model_version: str = "unverified"
    timeout_seconds: float = 8.0
    advisory_route: VLAAdvisoryRoute = VLAAdvisoryRoute.ADVISORY_FAST
    route_reason: str = "default_fast"
    escalation_from_request_id: str = ""
    advisory_only: bool = True

    @classmethod
    def from_pqf(
        cls,
        frame: PerceptionQueryFrame,
        *,
        owner_kind: str,
        owner_id: str,
        model_id: str,
        model_version: str = "unverified",
        timeout_seconds: float = 8.0,
        advisory_route: VLAAdvisoryRoute = VLAAdvisoryRoute.ADVISORY_FAST,
        route_reason: str = "default_fast",
        escalation_from_request_id: str = "",
    ) -> "VLAProviderRequest":
        artifact_refs = [
            ref.ref_id
            for ref in [
                *frame.visual_inputs,
                *frame.spatial_inputs,
                *frame.auditory_inputs,
                *frame.embodied_inputs,
                *frame.skeletal_inputs,
                *frame.environment_inputs,
            ]
        ]
        return cls(
            request_id=f"vla_request:{owner_kind}:{owner_id}:{frame.query_id}",
            owner_kind=owner_kind,
            owner_id=owner_id,
            query_frame=frame,
            subject_ref=frame.subject_ref,
            target_ref=frame.target_ref,
            world_anchor_id=frame.world_anchor_id,
            source_ref_lineage=list(frame.source_ref_lineage),
            capture_root_id=frame.capture_root_id,
            capture_id=frame.capture_id,
            clock_domain=frame.clock_domain,
            monotonic_tick=frame.monotonic_tick,
            source_frame_index=frame.source_frame_index,
            artifact_refs=artifact_refs,
            structured_fact_refs=list(frame.structured_fact_refs),
            grounding_entity_refs=list(frame.grounding_entity_refs),
            grounding_collider_refs=list(frame.grounding_collider_refs),
            grounding_anchor_refs=list(frame.grounding_anchor_refs),
            grounding_affordance_refs=list(frame.grounding_affordance_refs),
            context_namespace=frame.multimodal_context_id,
            cache_namespace=frame.cache_namespace,
            model_id=model_id,
            model_version=model_version,
            timeout_seconds=timeout_seconds,
            advisory_route=advisory_route,
            route_reason=route_reason,
            escalation_from_request_id=escalation_from_request_id,
        )

    @model_validator(mode="after")
    def validate_context_and_input_boundary(self) -> "VLAProviderRequest":
        if self.capture_root_id == "":
            self.capture_root_id = self.query_frame.capture_root_id
        if self.capture_id == "":
            self.capture_id = self.query_frame.capture_id
        if self.clock_domain == "":
            self.clock_domain = self.query_frame.clock_domain
        if self.monotonic_tick is None:
            self.monotonic_tick = self.query_frame.monotonic_tick
        if self.source_frame_index is None:
            self.source_frame_index = self.query_frame.source_frame_index
        if self.subject_ref == "":
            self.subject_ref = self.query_frame.subject_ref
        if self.target_ref == "":
            self.target_ref = self.query_frame.target_ref
        if self.world_anchor_id == "":
            self.world_anchor_id = self.query_frame.world_anchor_id
        if not self.source_ref_lineage:
            self.source_ref_lineage = list(self.query_frame.source_ref_lineage)
        if not self.grounding_entity_refs:
            self.grounding_entity_refs = list(self.query_frame.grounding_entity_refs)
        if not self.grounding_collider_refs:
            self.grounding_collider_refs = list(self.query_frame.grounding_collider_refs)
        if not self.grounding_anchor_refs:
            self.grounding_anchor_refs = list(self.query_frame.grounding_anchor_refs)
        if not self.grounding_affordance_refs:
            self.grounding_affordance_refs = list(self.query_frame.grounding_affordance_refs)
        if not self.advisory_only:
            raise ValueError("VLA requests must be advisory-only")
        if self.context_namespace != self.query_frame.multimodal_context_id:
            raise ValueError("VLA request context must inherit the PQF context")
        if self.cache_namespace != self.query_frame.cache_namespace:
            raise ValueError("VLA request cache namespace must inherit the PQF namespace")
        if "shared" in self.context_namespace or "shared" in self.cache_namespace:
            raise ValueError("VLA runtime context/cache namespaces must not be shared")
        expected_prefix = "character_mm:" if self.owner_kind == "character" else "siming_mm:"
        if self.owner_kind in {"character", "siming"} and not self.context_namespace.startswith(expected_prefix):
            raise ValueError(f"{self.owner_kind} VLA request must use {expected_prefix} context")
        if self.capture_root_id != self.query_frame.capture_root_id:
            raise ValueError("VLA request capture_root_id must inherit the PQF capture root")
        if self.clock_domain != self.query_frame.clock_domain:
            raise ValueError("VLA request clock_domain must inherit the PQF clock domain")
        if self.monotonic_tick != self.query_frame.monotonic_tick:
            raise ValueError("VLA request monotonic_tick must inherit the PQF monotonic tick")
        if self.grounding_entity_refs != self.query_frame.grounding_entity_refs:
            raise ValueError("VLA request grounding_entity_refs must inherit the PQF grounding catalog")
        if self.grounding_collider_refs != self.query_frame.grounding_collider_refs:
            raise ValueError("VLA request grounding_collider_refs must inherit the PQF grounding catalog")
        if self.grounding_anchor_refs != self.query_frame.grounding_anchor_refs:
            raise ValueError("VLA request grounding_anchor_refs must inherit the PQF grounding catalog")
        if self.grounding_affordance_refs != self.query_frame.grounding_affordance_refs:
            raise ValueError("VLA request grounding_affordance_refs must inherit the PQF grounding catalog")
        return self


class VLAProviderResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_id: str
    request_id: str
    status: VLAProviderStatus
    advisory: bool = True
    subject_ref: str = ""
    target_ref: str = ""
    world_anchor_id: str = ""
    source_ref_lineage: list[str] = Field(default_factory=list)
    capture_root_id: str = ""
    capture_id: str = ""
    clock_domain: str = ""
    monotonic_tick: int | None = None
    source_frame_index: int | None = None
    capture_relation: Literal["same_capture_tick", "late_advisory"] = "same_capture_tick"
    provider_id: str
    model_id: str
    model_version: str
    advisory_route: VLAAdvisoryRoute = VLAAdvisoryRoute.ADVISORY_FAST
    route_reason: str = "default_fast"
    escalation_from_request_id: str = ""
    findings: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    conflict_refs: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    freshness: str = "fresh"
    expires_at: int = 0
    trace_refs: list[str] = Field(default_factory=list)
    fallback_reason: str = ""
    provider_http_status: int | None = None
    provider_error_code: str = ""
    provider_error_param: str = ""
    provider_error_category: str = ""
    failure_phase: str = ""
    provider_thinking_enabled: bool | None = None
    writes_world_truth: bool = False
    writes_esm_authority: bool = False
    controls_actor: bool = False

    @model_validator(mode="after")
    def validate_advisory_boundary(self) -> "VLAProviderResult":
        if not self.advisory:
            raise ValueError("VLAProviderResult must remain advisory")
        if self.writes_world_truth or self.writes_esm_authority or self.controls_actor:
            raise ValueError("VLA result must not write world truth, ESM authority, or actor control")
        enriched_findings: list[dict[str, Any]] = []
        for finding in self.findings:
            enriched = dict(finding)
            if self.subject_ref:
                enriched.setdefault("subject_ref", self.subject_ref)
            if self.target_ref:
                enriched.setdefault("target_ref", self.target_ref)
            if self.world_anchor_id:
                enriched.setdefault("world_anchor_id", self.world_anchor_id)
            if self.source_ref_lineage:
                enriched.setdefault("source_ref_lineage", list(self.source_ref_lineage))
            enriched.setdefault("advisory", True)
            enriched.setdefault("world_truth_marker", "subjective_not_world_truth")
            enriched_findings.append(enriched)
        self.findings = enriched_findings
        return self


class VLAProviderProtocol(Protocol):
    provider_id: str
    model_id: str
    model_version: str

    def interpret(self, request: VLAProviderRequest) -> VLAProviderResult: ...


class DisabledVLAProvider:
    provider_id = "disabled_vla_provider"
    model_id = "disabled"
    model_version = "disabled"

    def interpret(self, request: VLAProviderRequest) -> VLAProviderResult:
        return VLAProviderResult(
            result_id=f"vla_result:{request.request_id}",
            request_id=request.request_id,
            status=VLAProviderStatus.DISABLED,
            **_result_capture_clock_from_request(request),
            provider_id=self.provider_id,
            model_id=request.model_id,
            model_version=request.model_version,
            advisory_route=request.advisory_route,
            route_reason=request.route_reason,
            escalation_from_request_id=request.escalation_from_request_id,
            confidence=0.0,
            freshness="disabled",
            expires_at=int(time.time()) + 1,
            trace_refs=[request.request_id, request.capture_root_id, request.capture_id],
            fallback_reason="provider_disabled",
        )


class DeterministicMockVLAProvider:
    provider_id = "deterministic_mock_vla_provider"
    model_id = "mock-visual-spatial-advisor"
    model_version = "mock-schema-v1"

    def interpret(self, request: VLAProviderRequest) -> VLAProviderResult:
        capture_kwargs = _result_capture_clock_from_request(request)
        if not request.artifact_refs:
            return VLAProviderResult(
                result_id=f"vla_result:{request.request_id}",
                request_id=request.request_id,
                status=VLAProviderStatus.BLOCKED_MISSING_ARTIFACTS,
                **capture_kwargs,
                provider_id=self.provider_id,
                model_id=request.model_id,
                model_version=request.model_version,
                advisory_route=request.advisory_route,
                route_reason=request.route_reason,
                escalation_from_request_id=request.escalation_from_request_id,
                confidence=0.0,
                missing_inputs=["artifact_refs"],
                freshness="missing",
                expires_at=int(time.time()) + 1,
                trace_refs=[request.request_id, request.capture_root_id, request.capture_id],
                fallback_reason="blocked_missing_artifacts",
            )
        return VLAProviderResult(
            result_id=f"vla_result:{request.request_id}",
            request_id=request.request_id,
            status=VLAProviderStatus.MOCK_PROVIDER_VERIFIED,
            **capture_kwargs,
            provider_id=self.provider_id,
            model_id=request.model_id,
            model_version=request.model_version,
            advisory_route=request.advisory_route,
            route_reason=request.route_reason,
            escalation_from_request_id=request.escalation_from_request_id,
            findings=[
                {
                    "finding_type": "visual_spatial_advisory",
                    "subject_ref": request.subject_ref or request.artifact_refs[0],
                    "target_ref": request.target_ref,
                    "world_anchor_id": request.world_anchor_id,
                    "source_ref_lineage": list(request.source_ref_lineage),
                    "summary": "local visual-spatial refs are sufficient for advisory interpretation",
                    "advisory": True,
                    "world_truth_marker": "subjective_not_world_truth",
                }
            ],
            confidence=0.62,
            freshness="fresh",
            expires_at=int(time.time()) + max(1, int(request.timeout_seconds)),
            trace_refs=[request.request_id, request.capture_root_id, request.capture_id, *request.structured_fact_refs],
        )


class HTTPVLAProviderAdapter:
    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        model_id: str,
        model_version: str = "configured-unverified",
        provider_id: str = "http_vla_provider",
        json_mode_enabled: bool = False,
        advisory_fast_enable_thinking: bool | None = None,
        advisory_deep_enable_thinking: bool | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.model_id = model_id
        self.model_version = model_version
        self.provider_id = provider_id
        self.json_mode_enabled = json_mode_enabled
        self._thinking_enabled_by_route = {
            VLAAdvisoryRoute.ADVISORY_FAST: advisory_fast_enable_thinking,
            VLAAdvisoryRoute.ADVISORY_DEEP: advisory_deep_enable_thinking,
        }

    @classmethod
    def from_runtime_settings(cls) -> "HTTPVLAProviderAdapter":
        from app.config import settings

        return cls(
            endpoint=settings.vla_provider_endpoint or "",
            api_key=settings.vla_provider_api_key or "",
            model_id=settings.vla_provider_model,
            model_version=settings.vla_provider_model_version,
            provider_id=f"{settings.vla_provider_kind}_vla_provider",
            json_mode_enabled=settings.vla_provider_json_mode_enabled,
            advisory_fast_enable_thinking=settings.vla_advisory_fast_enable_thinking,
            advisory_deep_enable_thinking=settings.vla_advisory_deep_enable_thinking,
        )

    def interpret(self, request: VLAProviderRequest) -> VLAProviderResult:
        capture_kwargs = _result_capture_clock_from_request(request)
        if self.endpoint == "" or self.api_key == "":
            return VLAProviderResult(
                result_id=f"vla_result:{request.request_id}",
                request_id=request.request_id,
                status=VLAProviderStatus.BLOCKED_MISSING_CREDENTIALS,
                **capture_kwargs,
                provider_id=self.provider_id,
                model_id=request.model_id,
                model_version=request.model_version,
                advisory_route=request.advisory_route,
                route_reason=request.route_reason,
                escalation_from_request_id=request.escalation_from_request_id,
                confidence=0.0,
                missing_inputs=["VLA_PROVIDER_ENDPOINT", "VLA_PROVIDER_API_KEY"],
                freshness="missing",
                expires_at=int(time.time()) + 1,
                trace_refs=[request.request_id, request.capture_root_id, request.capture_id],
                fallback_reason="blocked_missing_credentials",
            )
        image_sources = self._eligible_image_sources(request)
        if not image_sources:
            return VLAProviderResult(
                result_id=f"vla_result:{request.request_id}",
                request_id=request.request_id,
                status=VLAProviderStatus.BLOCKED_MISSING_ARTIFACTS,
                **capture_kwargs,
                provider_id=self.provider_id,
                model_id=request.model_id,
                model_version=request.model_version,
                advisory_route=request.advisory_route,
                route_reason=request.route_reason,
                escalation_from_request_id=request.escalation_from_request_id,
                confidence=0.0,
                missing_inputs=["eligible_visual_artifact_ref"],
                freshness="missing",
                expires_at=int(time.time()) + 1,
                trace_refs=[request.request_id, request.capture_root_id, request.capture_id],
                fallback_reason="blocked_missing_eligible_visual_artifact",
            )

        try:
            transport_request = Request(
                self._chat_completions_url(),
                data=json.dumps(self._request_payload(request, image_sources), ensure_ascii=True).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST",
            )
            with urlopen(transport_request, timeout=request.timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
            payload = self._provider_payload(response_payload)
            confidence = self._confidence(payload.get("confidence", 0.0))
            findings = self._sanitize_findings(payload.get("findings", []), request, default_confidence=confidence)
            conflict_refs = self._string_list(payload.get("conflict_refs", []))
            missing_inputs = self._string_list(payload.get("missing_inputs", []))
        except TimeoutError:
            return self._degraded_result(
                request,
                status=VLAProviderStatus.TIMEOUT,
                fallback_reason="provider_timeout",
                failure_phase="transport_timeout",
            )
        except HTTPError as exc:
            provider_error_code, provider_error_param, provider_error_category = self._http_error_details(exc)
            return self._degraded_result(
                request,
                status=VLAProviderStatus.ERROR,
                fallback_reason="provider_http_error",
                provider_http_status=exc.code,
                provider_error_code=provider_error_code,
                provider_error_param=provider_error_param,
                provider_error_category=provider_error_category,
                failure_phase="provider_http_response",
            )
        except URLError:
            return self._degraded_result(
                request,
                status=VLAProviderStatus.ERROR,
                fallback_reason="provider_transport_unavailable",
                failure_phase="provider_transport",
            )
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            return self._degraded_result(
                request,
                status=VLAProviderStatus.ERROR,
                fallback_reason="provider_response_invalid",
                failure_phase="provider_response_schema",
            )

        return VLAProviderResult(
            result_id=f"vla_result:{request.request_id}",
            request_id=request.request_id,
            status=VLAProviderStatus.REAL_PROVIDER_VERIFIED,
            **capture_kwargs,
            provider_id=self.provider_id,
            model_id=request.model_id,
            model_version=request.model_version,
            advisory_route=request.advisory_route,
            route_reason=request.route_reason,
            escalation_from_request_id=request.escalation_from_request_id,
            findings=findings,
            confidence=confidence,
            conflict_refs=conflict_refs,
            missing_inputs=missing_inputs,
            freshness="fresh",
            expires_at=int(time.time()) + max(1, int(request.timeout_seconds)),
            trace_refs=[request.request_id, request.capture_root_id, request.capture_id, "provider_transport:http"],
            provider_thinking_enabled=self._thinking_enabled(request),
        )

    def _chat_completions_url(self) -> str:
        if self.endpoint.endswith("/chat/completions"):
            return self.endpoint
        return self.endpoint.rstrip("/") + "/chat/completions"

    def _request_payload(self, request: VLAProviderRequest, image_sources: list[str]) -> dict[str, object]:
        context = {
            "request_id": request.request_id,
            "owner_kind": request.owner_kind,
            "owner_id": request.owner_id,
            "advisory_route": request.advisory_route.value,
            "route_reason": request.route_reason,
            "subject_ref": request.subject_ref,
            "target_ref": request.target_ref,
            "world_anchor_id": request.world_anchor_id,
            "capture_root_id": request.capture_root_id,
            "capture_id": request.capture_id,
            "clock_domain": request.clock_domain,
            "monotonic_tick": request.monotonic_tick,
            "source_frame_index": request.source_frame_index,
            "artifact_refs": request.artifact_refs,
            "structured_fact_refs": request.structured_fact_refs,
            "grounding_reference_catalog": self._grounding_catalog(request),
            "spatial_reference": request.query_frame.spatial_reference.model_dump(mode="json"),
            "attention_context": request.query_frame.attention_context.model_dump(mode="json"),
            "known_scene_truth_policy": "structured_fact_refs_and_scene_bindings_take_precedence_over_vla_estimates",
        }
        content: list[dict[str, object]] = [
            {
                "type": "text",
                "text": (
                    "Return one UTF-8 JSON object only: no Markdown, prose wrapper, or code fence. "
                    "Required shape: {\"findings\":[{\"summary\":string,\"confidence\":number,"
                    "\"candidate_entity_refs\":[string],\"candidate_collider_refs\":[string],"
                    "\"candidate_anchor_refs\":[string],\"candidate_affordance_refs\":[string],"
                    "\"uncertainty\":string,\"conflicts_with\":[string],\"evidence_artifact_refs\":[string]}],"
                    "\"confidence\":number,\"conflict_refs\":[string],\"missing_inputs\":[string]}. "
                    "Findings are non-authoritative visual/spatial advisories only. Use candidate_entity_refs, "
                    "candidate_collider_refs, candidate_anchor_refs, and candidate_affordance_refs only with exact values from the "
                    "grounding_reference_catalog. When a finding directly names a visible catalog ref, include that exact ref in its "
                    "matching candidate list; otherwise leave the list empty. "
                    "Catalog values are scene-truth pointers, not visual proof. Never return actions, "
                    "world state writes, settlement, physics, transforms, velocities, bone controls, or actor controls. "
                    f"PQF-derived context: {json.dumps(context, ensure_ascii=True, sort_keys=True)}"
                ),
            },
            *[{"type": "image_url", "image_url": {"url": source}} for source in image_sources],
        ]
        payload: dict[str, object] = {
            "model": request.model_id,
            "messages": [
                {
                    "role": "system",
            "content": "You are a visual-spatial advisory provider for a game runtime. Structured scene facts are authoritative.",
                },
                {"role": "user", "content": content},
            ],
            "temperature": 0.0,
        }
        if self.json_mode_enabled:
            payload["response_format"] = {"type": "json_object"}
        thinking_enabled = self._thinking_enabled(request)
        if thinking_enabled is not None:
            payload["enable_thinking"] = thinking_enabled
        return payload

    def _thinking_enabled(self, request: VLAProviderRequest) -> bool | None:
        return self._thinking_enabled_by_route[request.advisory_route]

    @staticmethod
    def _eligible_image_sources(request: VLAProviderRequest) -> list[str]:
        sources: list[str] = []
        for ref in request.query_frame.visual_inputs:
            source = ref.stable_source_ref.strip()
            if source.startswith("https://") or source.startswith("data:image/"):
                sources.append(source)
        return sources

    @staticmethod
    def _provider_payload(response_payload: object) -> dict[str, object]:
        if not isinstance(response_payload, dict):
            raise ValueError("VLA provider response must be an object")
        choices = response_payload.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ValueError("VLA provider response must contain a choice")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise ValueError("VLA provider response choice must contain a message")
        content = message.get("content")
        if isinstance(content, str):
            decoded = json.loads(HTTPVLAProviderAdapter._strip_json_fence(content))
        elif isinstance(content, dict):
            decoded = content
        else:
            raise ValueError("VLA provider response content must be JSON")
        if not isinstance(decoded, dict):
            raise ValueError("VLA provider content must decode to an object")
        return decoded

    @staticmethod
    def _strip_json_fence(content: str) -> str:
        stripped = content.strip()
        if not stripped.startswith("```"):
            return stripped
        lines = stripped.splitlines()
        if len(lines) < 3 or not lines[-1].strip().startswith("```"):
            return stripped
        first = lines[0].strip().lower()
        if first not in {"```", "```json", "```jsonc"}:
            return stripped
        return "\n".join(lines[1:-1]).strip()

    def _sanitize_findings(
        self,
        raw_findings: object,
        request: VLAProviderRequest,
        *,
        default_confidence: float,
    ) -> list[dict[str, Any]]:
        if isinstance(raw_findings, str):
            raw_findings = [raw_findings]
        if not isinstance(raw_findings, list):
            raise ValueError("VLA provider findings must be a list")
        findings: list[dict[str, Any]] = []
        for raw in raw_findings:
            if isinstance(raw, str) and raw.strip():
                findings.append(
                    {
                        "finding_type": "visual_spatial_advisory",
                        "summary": raw.strip(),
                        "confidence": default_confidence,
                        "candidate_entity_refs": [],
                        "candidate_affordance_refs": [],
                        "uncertainty": "provider returned an ungrounded textual finding",
                        "conflicts_with": [],
                        "evidence_artifact_refs": list(request.artifact_refs),
                    }
                )
                continue
            if not isinstance(raw, dict):
                raise ValueError("VLA provider finding must be an object")
            summary = str(raw.get("summary", "") or "").strip()
            if summary == "":
                raise ValueError("VLA provider finding summary is required")
            allowed_refs = self._grounding_catalog(request)
            candidate_entity_refs = self._allowed_candidate_refs(raw.get("candidate_entity_refs", []), allowed_refs["entity_refs"])
            candidate_collider_refs = self._allowed_candidate_refs(
                raw.get("candidate_collider_refs", []), allowed_refs["collider_refs"]
            )
            candidate_anchor_refs = self._allowed_candidate_refs(raw.get("candidate_anchor_refs", []), allowed_refs["anchor_refs"])
            candidate_affordance_refs = self._allowed_candidate_refs(
                raw.get("candidate_affordance_refs", []), allowed_refs["affordance_refs"]
            )
            uncertainty = str(raw.get("uncertainty", "") or "")
            if not (candidate_entity_refs or candidate_collider_refs or candidate_anchor_refs or candidate_affordance_refs) and uncertainty == "":
                uncertainty = "provider returned no refs from the grounded candidate catalog"
            finding: dict[str, Any] = {
                "finding_type": str(raw.get("finding_type", "visual_spatial_advisory") or "visual_spatial_advisory"),
                "summary": summary,
                "confidence": self._confidence(raw.get("confidence", 0.0)),
                "candidate_entity_refs": candidate_entity_refs,
                "candidate_collider_refs": candidate_collider_refs,
                "candidate_anchor_refs": candidate_anchor_refs,
                "candidate_affordance_refs": candidate_affordance_refs,
                "uncertainty": uncertainty,
                "conflicts_with": self._string_list(raw.get("conflicts_with", [])),
                "evidence_artifact_refs": [
                    ref for ref in self._string_list(raw.get("evidence_artifact_refs", [])) if ref in request.artifact_refs
                ],
            }
            findings.append(finding)
        return findings

    @staticmethod
    def _grounding_catalog(request: VLAProviderRequest) -> dict[str, list[str]]:
        return {
            "entity_refs": list(request.grounding_entity_refs),
            "collider_refs": list(request.grounding_collider_refs),
            "anchor_refs": list(request.grounding_anchor_refs),
            "affordance_refs": list(request.grounding_affordance_refs),
        }

    def _allowed_candidate_refs(self, value: object, allowed: list[str]) -> list[str]:
        allowed_refs = set(allowed)
        return [ref for ref in self._string_list(value) if ref in allowed_refs]

    @staticmethod
    def _string_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    @staticmethod
    def _confidence(value: object) -> float:
        confidence = float(value or 0.0)
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("VLA provider confidence must be between 0 and 1")
        return confidence

    @staticmethod
    def _http_error_details(error: HTTPError) -> tuple[str, str, str]:
        payload = HTTPVLAProviderAdapter._http_error_payload(error)
        if payload is None:
            return "", "", ""
        provider_error = payload.get("error")
        if not isinstance(provider_error, dict):
            return "", "", ""
        return (
            HTTPVLAProviderAdapter._sanitize_provider_error_value(provider_error.get("code") or provider_error.get("type")),
            HTTPVLAProviderAdapter._sanitize_provider_error_value(provider_error.get("param")),
            HTTPVLAProviderAdapter._classify_provider_error_message(provider_error.get("message")),
        )

    @staticmethod
    def _http_error_payload(error: HTTPError) -> dict[str, object] | None:
        try:
            payload = json.loads(error.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, OSError):
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    @staticmethod
    def _sanitize_provider_error_value(value: object) -> str:
        if not isinstance(value, str):
            return ""
        return "".join(character for character in value if character.isalnum() or character in {"_", "-", "."})[:80]

    @staticmethod
    def _classify_provider_error_message(value: object) -> str:
        if not isinstance(value, str):
            return "provider_rejected_request"
        message = value.lower()
        if "response_format" in message or "json_object" in message or "json mode" in message:
            return "unsupported_json_mode"
        if "image_url" in message or "image" in message or "vision" in message or "multimodal" in message:
            return "unsupported_image_input"
        if "model" in message:
            return "model_capability_or_entitlement"
        if "message" in message or "content" in message:
            return "request_content_schema"
        return "provider_rejected_request"

    def _degraded_result(
        self,
        request: VLAProviderRequest,
        *,
        status: VLAProviderStatus,
        fallback_reason: str,
        provider_http_status: int | None = None,
        provider_error_code: str = "",
        provider_error_param: str = "",
        provider_error_category: str = "",
        failure_phase: str = "",
    ) -> VLAProviderResult:
        return VLAProviderResult(
            result_id=f"vla_result:{request.request_id}",
            request_id=request.request_id,
            status=status,
            **_result_capture_clock_from_request(request, capture_relation="late_advisory"),
            provider_id=self.provider_id,
            model_id=request.model_id,
            model_version=request.model_version,
            advisory_route=request.advisory_route,
            route_reason=request.route_reason,
            escalation_from_request_id=request.escalation_from_request_id,
            confidence=0.0,
            freshness="degraded",
            expires_at=int(time.time()) + 1,
            trace_refs=[request.request_id, request.capture_root_id, request.capture_id, "provider_transport:http"],
            fallback_reason=fallback_reason,
            provider_http_status=provider_http_status,
            provider_error_code=provider_error_code,
            provider_error_param=provider_error_param,
            provider_error_category=provider_error_category,
            failure_phase=failure_phase,
            provider_thinking_enabled=self._thinking_enabled(request),
        )


class LocalVLAProviderAdapter(HTTPVLAProviderAdapter):
    def __init__(self, *, model_id: str, endpoint: str = "", provider_id: str = "local_vla_provider") -> None:
        super().__init__(
            endpoint=endpoint,
            api_key="local",
            model_id=model_id,
            model_version="local-configured-unverified",
            provider_id=provider_id,
        )

    def interpret(self, request: VLAProviderRequest) -> VLAProviderResult:
        return VLAProviderResult(
            result_id=f"vla_result:{request.request_id}",
            request_id=request.request_id,
            status=VLAProviderStatus.CONFIGURED_UNVERIFIED,
            **_result_capture_clock_from_request(request),
            provider_id=self.provider_id,
            model_id=request.model_id,
            model_version=request.model_version,
            advisory_route=request.advisory_route,
            route_reason=request.route_reason,
            escalation_from_request_id=request.escalation_from_request_id,
            confidence=0.0,
            missing_inputs=["local_provider_transport_verification"],
            freshness="configured_unverified",
            expires_at=int(time.time()) + 1,
            trace_refs=[request.request_id, request.capture_root_id, request.capture_id],
            fallback_reason="configured_unverified",
        )


def _result_capture_clock_from_request(
    request: VLAProviderRequest,
    *,
    capture_relation: Literal["same_capture_tick", "late_advisory"] = "same_capture_tick",
) -> dict[str, object]:
    return {
        "capture_root_id": request.capture_root_id,
        "capture_id": request.capture_id,
        "clock_domain": request.clock_domain,
        "monotonic_tick": request.monotonic_tick,
        "source_frame_index": request.source_frame_index,
        "capture_relation": capture_relation,
        "subject_ref": request.subject_ref,
        "target_ref": request.target_ref,
        "world_anchor_id": request.world_anchor_id,
        "source_ref_lineage": list(request.source_ref_lineage),
    }
