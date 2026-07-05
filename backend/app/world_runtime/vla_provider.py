from __future__ import annotations

import time
from enum import StrEnum
from typing import Any, Literal, Protocol

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
    context_namespace: str
    cache_namespace: str
    model_id: str
    model_version: str = "unverified"
    timeout_seconds: float = 8.0
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
            context_namespace=frame.multimodal_context_id,
            cache_namespace=frame.cache_namespace,
            model_id=model_id,
            model_version=model_version,
            timeout_seconds=timeout_seconds,
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
    findings: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    conflict_refs: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    freshness: str = "fresh"
    expires_at: int = 0
    trace_refs: list[str] = Field(default_factory=list)
    fallback_reason: str = ""
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
                model_id=self.model_id,
                model_version=self.model_version,
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
            model_id=self.model_id,
            model_version=self.model_version,
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
    ) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.model_id = model_id
        self.model_version = model_version
        self.provider_id = provider_id

    def interpret(self, request: VLAProviderRequest) -> VLAProviderResult:
        capture_kwargs = _result_capture_clock_from_request(request)
        if self.endpoint == "" or self.api_key == "":
            return VLAProviderResult(
                result_id=f"vla_result:{request.request_id}",
                request_id=request.request_id,
                status=VLAProviderStatus.BLOCKED_MISSING_CREDENTIALS,
                **capture_kwargs,
                provider_id=self.provider_id,
                model_id=self.model_id,
                model_version=self.model_version,
                confidence=0.0,
                missing_inputs=["VLA_PROVIDER_ENDPOINT", "VLA_PROVIDER_API_KEY"],
                freshness="missing",
                expires_at=int(time.time()) + 1,
                trace_refs=[request.request_id, request.capture_root_id, request.capture_id],
                fallback_reason="blocked_missing_credentials",
            )
        return VLAProviderResult(
            result_id=f"vla_result:{request.request_id}",
            request_id=request.request_id,
            status=VLAProviderStatus.CONFIGURED_UNVERIFIED,
            **capture_kwargs,
            provider_id=self.provider_id,
            model_id=self.model_id,
            model_version=self.model_version,
            confidence=0.0,
            missing_inputs=["real_http_call_verification"],
            freshness="configured_unverified",
            expires_at=int(time.time()) + 1,
            trace_refs=[request.request_id, request.capture_root_id, request.capture_id],
            fallback_reason="configured_unverified",
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
