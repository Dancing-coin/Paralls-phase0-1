from __future__ import annotations

import time
from enum import StrEnum
from typing import Any, Protocol

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
        return self


class VLAProviderResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_id: str
    request_id: str
    status: VLAProviderStatus
    advisory: bool = True
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
        if not request.artifact_refs:
            return VLAProviderResult(
                result_id=f"vla_result:{request.request_id}",
                request_id=request.request_id,
                status=VLAProviderStatus.BLOCKED_MISSING_ARTIFACTS,
                provider_id=self.provider_id,
                model_id=self.model_id,
                model_version=self.model_version,
                confidence=0.0,
                missing_inputs=["artifact_refs"],
                freshness="missing",
                expires_at=int(time.time()) + 1,
                trace_refs=[request.request_id],
                fallback_reason="blocked_missing_artifacts",
            )
        return VLAProviderResult(
            result_id=f"vla_result:{request.request_id}",
            request_id=request.request_id,
            status=VLAProviderStatus.MOCK_PROVIDER_VERIFIED,
            provider_id=self.provider_id,
            model_id=self.model_id,
            model_version=self.model_version,
            findings=[
                {
                    "finding_type": "visual_spatial_advisory",
                    "subject_ref": request.artifact_refs[0],
                    "summary": "local visual-spatial refs are sufficient for advisory interpretation",
                    "advisory": True,
                }
            ],
            confidence=0.62,
            freshness="fresh",
            expires_at=int(time.time()) + max(1, int(request.timeout_seconds)),
            trace_refs=[request.request_id, *request.structured_fact_refs],
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
        if self.endpoint == "" or self.api_key == "":
            return VLAProviderResult(
                result_id=f"vla_result:{request.request_id}",
                request_id=request.request_id,
                status=VLAProviderStatus.BLOCKED_MISSING_CREDENTIALS,
                provider_id=self.provider_id,
                model_id=self.model_id,
                model_version=self.model_version,
                confidence=0.0,
                missing_inputs=["VLA_PROVIDER_ENDPOINT", "VLA_PROVIDER_API_KEY"],
                freshness="missing",
                expires_at=int(time.time()) + 1,
                trace_refs=[request.request_id],
                fallback_reason="blocked_missing_credentials",
            )
        return VLAProviderResult(
            result_id=f"vla_result:{request.request_id}",
            request_id=request.request_id,
            status=VLAProviderStatus.CONFIGURED_UNVERIFIED,
            provider_id=self.provider_id,
            model_id=self.model_id,
            model_version=self.model_version,
            confidence=0.0,
            missing_inputs=["real_http_call_verification"],
            freshness="configured_unverified",
            expires_at=int(time.time()) + 1,
            trace_refs=[request.request_id],
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
