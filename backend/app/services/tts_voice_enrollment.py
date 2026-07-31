"""Controlled, presentation-only voice-cloning enrollment primitives."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import Settings


class TTSVoiceEnrollmentError(RuntimeError):
    pass


class _VoiceEnrollmentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CharacterVoiceSourceAsset(_VoiceEnrollmentModel):
    """Metadata for a source clip held by a secure asset store, never its bytes."""

    contract: Literal["character_voice_source_asset.v1"]
    asset_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    asset_kind: Literal["voice_reference"]
    source_ref: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    rights_status: Literal["pending", "authorised", "revoked"]
    consent_ref: str | None = None
    retention_policy: Literal["revocable", "fixed_term"]

    @field_validator("source_ref")
    @classmethod
    def validate_secure_source_ref(cls, value: str) -> str:
        if not value.startswith("secure_asset://"):
            raise ValueError("source_ref must use the secure_asset scheme")
        return value

    @field_validator("consent_ref")
    @classmethod
    def validate_consent_ref(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("consent_ref cannot be blank when supplied")
        return value


class CharacterVoiceSourceAssetLoader:
    def __init__(self, root: str | Path | None = None) -> None:
        self._root = Path(root) if root is not None else Path(__file__).resolve().parents[3] / "assets" / "characters" / "voice_sources"

    def load(self, actor_id: str) -> CharacterVoiceSourceAsset:
        path = self._root / f"{actor_id}.yaml"
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise TTSVoiceEnrollmentError("voice source asset manifest is unavailable") from exc
        if not isinstance(payload, dict):
            raise TTSVoiceEnrollmentError("voice source asset manifest must be a mapping")
        try:
            asset = CharacterVoiceSourceAsset.model_validate(payload)
        except ValueError as exc:
            raise TTSVoiceEnrollmentError("voice source asset manifest is invalid") from exc
        if asset.actor_id != actor_id:
            raise TTSVoiceEnrollmentError("voice source asset actor_id does not match its filename")
        return asset


class VoiceSourceUrlIssuer(Protocol):
    """Owned by a secure asset store and authorised to mint a short-lived read URL."""

    def issue_read_url(self, source_asset: CharacterVoiceSourceAsset) -> str: ...


class VoiceEnrollmentProvider(Protocol):
    provider_name: str

    def create_voice(self, *, source_url: str, target_model: str, prefix: str) -> str: ...


class VoiceEnrollmentRecord(_VoiceEnrollmentModel):
    contract: Literal["tts_voice_enrollment.v1"] = "tts_voice_enrollment.v1"
    source_asset_id: str
    actor_id: str
    provider: str
    target_model: str
    voice_id: str
    enrollment_status: Literal["candidate"] = "candidate"

    def to_voice_binding_payload(self, *, catalog_revision: str = "pending-enrollment") -> dict[str, object]:
        """Produces a candidate only; human listening review must approve it later."""
        return {
            "contract": "tts_voice_profile.v1",
            "actor_id": self.actor_id,
            "provider": self.provider,
            "model": self.target_model,
            "voice_id": self.voice_id,
            "catalog_revision": catalog_revision,
            "selection_status": "candidate",
            "approved_by": None,
        }


class VoiceCloneEnrollmentService:
    def __init__(self, *, provider: VoiceEnrollmentProvider) -> None:
        self._provider = provider

    def enroll(
        self,
        *,
        source_asset: CharacterVoiceSourceAsset,
        source_url_issuer: VoiceSourceUrlIssuer,
        target_model: str,
        prefix: str,
    ) -> VoiceEnrollmentRecord:
        if source_asset.rights_status != "authorised" or not source_asset.consent_ref:
            raise TTSVoiceEnrollmentError("voice source asset is not authorised for enrollment")
        if not target_model.strip():
            raise TTSVoiceEnrollmentError("target TTS model is required")
        if not re.fullmatch(r"[A-Za-z0-9-]{1,48}", prefix):
            raise TTSVoiceEnrollmentError("voice enrollment prefix must contain only letters, numbers, or hyphens")

        source_url = source_url_issuer.issue_read_url(source_asset)
        parsed = urlparse(source_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise TTSVoiceEnrollmentError("voice source URL issuer must return an HTTPS URL")

        voice_id = self._provider.create_voice(source_url=source_url, target_model=target_model, prefix=prefix)
        if not voice_id.strip():
            raise TTSVoiceEnrollmentError("voice enrollment provider returned an empty voice ID")
        return VoiceEnrollmentRecord(
            source_asset_id=source_asset.asset_id,
            actor_id=source_asset.actor_id,
            provider=self._provider.provider_name,
            target_model=target_model,
            voice_id=voice_id,
        )


class DashScopeVoiceEnrollmentProvider:
    """DashScope Qwen-Audio voice-enrollment HTTP adapter."""

    provider_name = "dashscope_http"

    def __init__(self, configuration: Settings) -> None:
        if not configuration.tts_provider_api_key or not configuration.tts_voice_enrollment_endpoint:
            raise TTSVoiceEnrollmentError("DashScope voice enrollment requires an API key and endpoint")
        endpoint = urlparse(configuration.tts_voice_enrollment_endpoint)
        if endpoint.scheme != "https" or not endpoint.netloc or "{" in endpoint.netloc or "}" in endpoint.netloc:
            raise TTSVoiceEnrollmentError("DashScope voice enrollment endpoint requires a configured HTTPS workspace URL")
        self._endpoint = configuration.tts_voice_enrollment_endpoint
        self._api_key = configuration.tts_provider_api_key
        self._timeout_seconds = configuration.tts_provider_timeout_seconds

    def create_voice(self, *, source_url: str, target_model: str, prefix: str) -> str:
        body = json.dumps(
            {
                "model": "voice-enrollment",
                "input": {
                    "action": "create_voice",
                    "target_model": target_model,
                    "prefix": prefix,
                    "url": source_url,
                },
            }
        ).encode("utf-8")
        request = Request(
            self._endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read())
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            raise TTSVoiceEnrollmentError("DashScope voice enrollment request failed") from exc
        return self._extract_voice_id(payload)

    @staticmethod
    def _extract_voice_id(payload: object) -> str:
        if not isinstance(payload, dict):
            raise TTSVoiceEnrollmentError("DashScope voice enrollment response must be an object")
        output = payload.get("output")
        voice_id = output.get("voice_id") if isinstance(output, dict) else None
        if not isinstance(voice_id, str) or not voice_id.strip():
            raise TTSVoiceEnrollmentError("DashScope voice enrollment response is missing voice_id")
        return voice_id


__all__ = [
    "CharacterVoiceSourceAsset",
    "CharacterVoiceSourceAssetLoader",
    "DashScopeVoiceEnrollmentProvider",
    "TTSVoiceEnrollmentError",
    "VoiceCloneEnrollmentService",
    "VoiceEnrollmentRecord",
    "VoiceEnrollmentProvider",
    "VoiceSourceUrlIssuer",
]
