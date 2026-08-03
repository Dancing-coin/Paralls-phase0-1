"""Provider/model-safe, presentation-only voice binding resolution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import Settings


class TTSVoiceProfileError(RuntimeError):
    pass


class _VoiceProfileModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VoiceCatalogEntry(_VoiceProfileModel):
    voice_id: str = Field(min_length=1)
    language_tags: list[str] = Field(default_factory=list)
    trait_tags: list[str] = Field(default_factory=list)
    usage_tags: list[str] = Field(default_factory=list)
    age_impression: str | None = None
    voice_gender_presentation: str | None = None
    review_ref: str | None = None


class TTSVoiceCatalog(_VoiceProfileModel):
    contract: Literal["tts_voice_catalog.v1"]
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    catalog_revision: str = Field(min_length=1)
    allowed_presentation_instructions: list[str] = Field(default_factory=list)
    voices: list[VoiceCatalogEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_voice_ids(self) -> TTSVoiceCatalog:
        voice_ids = [entry.voice_id for entry in self.voices]
        if len(set(voice_ids)) != len(voice_ids):
            raise ValueError("voice catalog contains duplicate voice_id values")
        return self


class TTSVoiceBinding(_VoiceProfileModel):
    contract: Literal["tts_voice_profile.v1"]
    actor_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    voice_id: str = Field(min_length=1)
    catalog_revision: str = Field(min_length=1)
    selection_status: Literal["candidate", "approved", "retired"]
    approved_by: str | None = None
    presentation_traits: list[str] = Field(default_factory=list)
    presentation_instruction: str | None = None


class TTSVoiceBindings(_VoiceProfileModel):
    contract: Literal["tts_voice_bindings.v1"]
    bindings: list[TTSVoiceBinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_actor_ids(self) -> TTSVoiceBindings:
        actor_ids = [binding.actor_id for binding in self.bindings]
        if len(set(actor_ids)) != len(actor_ids):
            raise ValueError("voice bindings contain duplicate actor_id values")
        return self


class TTSVoiceProfileResolver:
    """Resolves only operator-approved bindings for the configured provider model."""

    def __init__(self, configuration: Settings) -> None:
        self._configuration = configuration
        self._catalog: TTSVoiceCatalog | None = None
        self._bindings_by_actor_id: dict[str, TTSVoiceBinding] | None = None

    def resolve(self, actor_id: str) -> str | None:
        binding = self._binding_for_actor(actor_id)
        if binding is None:
            return None
        return binding.voice_id

    def resolve_presentation_instruction(self, actor_id: str) -> str | None:
        """Resolve only an authored, catalog-allowed instruction behind its feature flag."""
        if not self._configuration.tts_presentation_instructions_enabled:
            return None
        binding = self._binding_for_actor(actor_id)
        if binding is None or not binding.presentation_instruction:
            return None
        assert self._catalog is not None
        if binding.presentation_instruction not in self._catalog.allowed_presentation_instructions:
            raise TTSVoiceProfileError("TTS voice presentation instruction is not catalog-allowed")
        return binding.presentation_instruction

    def _binding_for_actor(self, actor_id: str) -> TTSVoiceBinding | None:
        if not self._configuration.tts_voice_profiles_enabled:
            return None
        self._load_assets()
        assert self._bindings_by_actor_id is not None
        binding = self._bindings_by_actor_id.get(actor_id)
        if binding is not None:
            self._validate_binding(binding)
        return binding

    def _load_assets(self) -> None:
        if self._catalog is not None and self._bindings_by_actor_id is not None:
            return

        catalog_path = self._resolve_asset_path(self._configuration.tts_voice_catalog_path, "catalog")
        bindings_path = self._resolve_asset_path(self._configuration.tts_voice_bindings_path, "bindings")
        try:
            catalog_payload = json.loads(catalog_path.read_text(encoding="utf-8"))
            bindings_payload = json.loads(bindings_path.read_text(encoding="utf-8"))
            catalog = TTSVoiceCatalog.model_validate(catalog_payload)
            bindings = TTSVoiceBindings.model_validate(bindings_payload)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise TTSVoiceProfileError("TTS voice profile assets are invalid or unavailable") from exc

        self._catalog = catalog
        self._bindings_by_actor_id = {binding.actor_id: binding for binding in bindings.bindings}

    @staticmethod
    def _resolve_asset_path(value: str | None, label: str) -> Path:
        if not value:
            raise TTSVoiceProfileError(f"TTS voice profile {label} path is not configured")
        candidate = Path(value)
        if candidate.is_absolute():
            return candidate
        return Path(__file__).resolve().parents[3] / candidate

    def _validate_binding(self, binding: TTSVoiceBinding) -> None:
        assert self._catalog is not None
        catalog = self._catalog
        if binding.selection_status != "approved":
            raise TTSVoiceProfileError("TTS voice binding is not approved")
        if binding.provider != catalog.provider or binding.model != catalog.model:
            raise TTSVoiceProfileError("TTS voice binding does not match its catalog")
        if binding.catalog_revision != catalog.catalog_revision:
            raise TTSVoiceProfileError("TTS voice binding references a different catalog revision")
        if binding.provider != self._configuration.tts_mode or binding.model != self._configuration.tts_provider_model:
            raise TTSVoiceProfileError("TTS voice binding does not match the configured provider model")
        voice = next((entry for entry in catalog.voices if entry.voice_id == binding.voice_id), None)
        if voice is None:
            raise TTSVoiceProfileError("TTS voice binding references an unknown catalog voice")
        required_language = self._configuration.tts_voice_required_language
        if required_language and required_language not in voice.language_tags:
            raise TTSVoiceProfileError("TTS voice binding does not support the required language")


__all__ = [
    "TTSVoiceBinding",
    "TTSVoiceBindings",
    "TTSVoiceCatalog",
    "VoiceCatalogEntry",
    "TTSVoiceProfileError",
    "TTSVoiceProfileResolver",
]
