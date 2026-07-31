import json

from app.config import Settings
from app.services.tts_service import TTSService


def _catalog_payload(*, provider: str = "dashscope_http", model: str = "qwen-audio-3.0-tts-flash") -> dict[str, object]:
    return {
        "contract": "tts_voice_catalog.v1",
        "provider": provider,
        "model": model,
        "catalog_revision": "2026-07-23",
        "voices": [
            {
                "voice_id": "qwen-audio-3.0-tts-flash-longlanghongmo",
                "language_tags": ["zh-CN"],
                "trait_tags": ["soft", "warm"],
            }
        ],
    }


def _bindings_payload(*, status: str = "approved", voice_id: str = "qwen-audio-3.0-tts-flash-longlanghongmo") -> dict[str, object]:
    return {
        "contract": "tts_voice_bindings.v1",
        "bindings": [
            {
                "contract": "tts_voice_profile.v1",
                "actor_id": "char_a",
                "provider": "dashscope_http",
                "model": "qwen-audio-3.0-tts-flash",
                "voice_id": voice_id,
                "catalog_revision": "2026-07-23",
                "selection_status": status,
                "approved_by": "human-listening-review",
            }
        ],
    }


def _settings(*, catalog_path: str, bindings_path: str, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "tts_mode": "dashscope_http",
        "tts_provider_endpoint": "https://workspace.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer",
        "tts_provider_api_key": "secret",
        "tts_provider_model": "qwen-audio-3.0-tts-flash",
        "tts_default_voice": "legacy-default",
        "tts_voice_map": {"char_a": "legacy-a"},
        "tts_voice_profiles_enabled": True,
        "tts_voice_catalog_path": catalog_path,
        "tts_voice_bindings_path": bindings_path,
    }
    values.update(overrides)
    return Settings(**values)


class _Provider:
    provider_name = "test_provider"

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def synthesize(self, *, content: str, voice_id: str) -> bytes:
        self.calls.append({"content": content, "voice_id": voice_id})
        return b"not-used"


def test_approved_matching_binding_overrides_the_legacy_actor_voice_map(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    bindings_path = tmp_path / "bindings.json"
    catalog_path.write_text(json.dumps(_catalog_payload()), encoding="utf-8")
    bindings_path.write_text(json.dumps(_bindings_payload()), encoding="utf-8")

    service = TTSService(configuration=_settings(catalog_path=str(catalog_path), bindings_path=str(bindings_path)))

    assert service.resolve_voice_id("char_a") == "qwen-audio-3.0-tts-flash-longlanghongmo"


def test_unapproved_profile_binding_falls_back_without_calling_the_provider(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    bindings_path = tmp_path / "bindings.json"
    catalog_path.write_text(json.dumps(_catalog_payload()), encoding="utf-8")
    bindings_path.write_text(json.dumps(_bindings_payload(status="candidate")), encoding="utf-8")
    provider = _Provider()

    audio = TTSService(
        configuration=_settings(catalog_path=str(catalog_path), bindings_path=str(bindings_path)),
        provider=provider,
    ).synthesize("char_a", "hello")

    assert provider.calls == []
    assert audio.mode == "stub"
    assert audio.status == "fallback"


def test_provider_or_model_mismatch_falls_back_without_calling_the_provider(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    bindings_path = tmp_path / "bindings.json"
    catalog_path.write_text(json.dumps(_catalog_payload(model="qwen-audio-3.0-tts-plus")), encoding="utf-8")
    bindings_path.write_text(json.dumps(_bindings_payload()), encoding="utf-8")
    provider = _Provider()

    audio = TTSService(
        configuration=_settings(catalog_path=str(catalog_path), bindings_path=str(bindings_path)),
        provider=provider,
    ).synthesize("char_a", "hello")

    assert provider.calls == []
    assert audio.mode == "stub"
    assert audio.status == "fallback"


def test_required_voice_language_rejects_an_incompatible_binding_before_provider_call(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    bindings_path = tmp_path / "bindings.json"
    catalog_path.write_text(json.dumps(_catalog_payload()), encoding="utf-8")
    bindings_path.write_text(json.dumps(_bindings_payload()), encoding="utf-8")
    provider = _Provider()

    audio = TTSService(
        configuration=_settings(
            catalog_path=str(catalog_path),
            bindings_path=str(bindings_path),
            tts_voice_required_language="en-US",
        ),
        provider=provider,
    ).synthesize("char_a", "hello")

    assert provider.calls == []
    assert audio.mode == "stub"
    assert audio.status == "fallback"


def test_profile_mode_uses_legacy_mapping_for_actors_without_a_binding(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    bindings_path = tmp_path / "bindings.json"
    catalog_path.write_text(json.dumps(_catalog_payload()), encoding="utf-8")
    bindings_path.write_text(json.dumps(_bindings_payload()), encoding="utf-8")
    service = TTSService(configuration=_settings(catalog_path=str(catalog_path), bindings_path=str(bindings_path)))

    assert service.resolve_voice_id("char_b") == "legacy-default"


def test_disabled_profile_mode_preserves_legacy_mapping_without_reading_assets() -> None:
    service = TTSService(
        configuration=Settings(
            tts_mode="stub",
            tts_default_voice="legacy-default",
            tts_voice_map={"char_a": "legacy-a"},
            tts_voice_profiles_enabled=False,
            tts_voice_catalog_path="not-a-real-file.json",
            tts_voice_bindings_path="not-a-real-file.json",
        )
    )

    assert service.resolve_voice_id("char_a") == "legacy-a"
