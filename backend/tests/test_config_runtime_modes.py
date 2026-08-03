import importlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import app.config as config_module
from app.config import Settings


def test_settings_default_to_stub_modes_when_env_is_unset(monkeypatch) -> None:
    monkeypatch.setenv("DIALOGUE_MODE", "")
    monkeypatch.setenv("TTS_MODE", "")

    reloaded = importlib.reload(config_module)

    assert reloaded.settings.dialogue_mode == "stub"
    assert reloaded.settings.tts_mode == "stub"


def test_settings_read_dialogue_and_tts_modes_from_env(monkeypatch) -> None:
    monkeypatch.setenv("DIALOGUE_MODE", "online")
    monkeypatch.setenv("TTS_MODE", "stub")
    monkeypatch.setenv("CHARACTER_DIALOGUE_CASCADE_LIMIT", "240")

    reloaded = importlib.reload(config_module)

    assert reloaded.settings.dialogue_mode == "online"
    assert reloaded.settings.tts_mode == "stub"
    assert reloaded.settings.character_dialogue_cascade_limit == 240


def test_settings_read_tts_provider_and_voice_map_from_env(monkeypatch) -> None:
    monkeypatch.setenv("TTS_MODE", "openai_compatible")
    monkeypatch.setenv("TTS_PROVIDER_ENDPOINT", "https://tts.example.test/v1/audio/speech")
    monkeypatch.setenv("TTS_PROVIDER_API_KEY", "tts-key")
    monkeypatch.setenv("TTS_PROVIDER_MODEL", "speech-model")
    monkeypatch.setenv("TTS_OUTPUT_SAMPLE_RATE_HZ", "24000")
    monkeypatch.setenv("TTS_MAX_ENCODED_PAYLOAD_BYTES", "999999")
    monkeypatch.setenv("TTS_VOICE_MAP_JSON", '{"char_a":"voice-a"}')

    reloaded = importlib.reload(config_module)

    assert reloaded.settings.tts_mode == "openai_compatible"
    assert reloaded.settings.tts_provider_endpoint == "https://tts.example.test/v1/audio/speech"
    assert reloaded.settings.tts_provider_model == "speech-model"
    assert reloaded.settings.tts_voice_map == {"char_a": "voice-a"}
    assert reloaded.settings.tts_max_encoded_payload_bytes == 999999


def test_settings_read_tts_voice_profile_asset_configuration(monkeypatch) -> None:
    monkeypatch.setenv("TTS_VOICE_PROFILES_ENABLED", "true")
    monkeypatch.setenv("TTS_VOICE_CATALOG_PATH", "assets/tts/voice_catalog.json")
    monkeypatch.setenv("TTS_VOICE_BINDINGS_PATH", "assets/tts/voice_bindings.json")
    monkeypatch.setenv("TTS_VOICE_CATALOG_REVISION", "2026-08-03")
    monkeypatch.setenv("TTS_VOICE_REQUIRED_LANGUAGE", "zh-CN")
    monkeypatch.setenv("TTS_PRESENTATION_INSTRUCTIONS_ENABLED", "true")
    monkeypatch.setenv(
        "TTS_VOICE_ENROLLMENT_ENDPOINT",
        "https://workspace.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/customization",
    )

    reloaded = importlib.reload(config_module)

    assert reloaded.settings.tts_voice_profiles_enabled is True
    assert reloaded.settings.tts_voice_catalog_path == "assets/tts/voice_catalog.json"
    assert reloaded.settings.tts_voice_bindings_path == "assets/tts/voice_bindings.json"
    assert reloaded.settings.tts_voice_catalog_revision == "2026-08-03"
    assert reloaded.settings.tts_voice_required_language == "zh-CN"
    assert reloaded.settings.tts_presentation_instructions_enabled is True
    assert reloaded.settings.tts_voice_enrollment_endpoint == (
        "https://workspace.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/customization"
    )


def test_settings_accept_dashscope_http_tts_mode(monkeypatch) -> None:
    monkeypatch.setenv("TTS_MODE", "dashscope_http")

    reloaded = importlib.reload(config_module)

    assert reloaded.settings.tts_mode == "dashscope_http"


def test_settings_read_vla_fast_and_deep_route_configuration(monkeypatch) -> None:
    monkeypatch.setenv("VLA_ADVISORY_FAST_MODEL", "qwen3.7-flash-test")
    monkeypatch.setenv("VLA_ADVISORY_FAST_TIMEOUT_SECONDS", "3.5")
    monkeypatch.setenv("VLA_ADVISORY_FAST_ENABLE_THINKING", "false")
    monkeypatch.setenv("VLA_ADVISORY_DEEP_ENABLED", "true")
    monkeypatch.setenv("VLA_ADVISORY_DEEP_MODEL", "qwen3.7-plus-test")
    monkeypatch.setenv("VLA_ADVISORY_DEEP_TIMEOUT_SECONDS", "11.0")
    monkeypatch.setenv("VLA_ADVISORY_DEEP_ENABLE_THINKING", "true")
    monkeypatch.setenv("VLA_ADVISORY_DEEP_CONFIDENCE_THRESHOLD", "0.6")

    reloaded = importlib.reload(config_module)

    assert reloaded.settings.vla_advisory_fast_model == "qwen3.7-flash-test"
    assert reloaded.settings.vla_advisory_fast_timeout_seconds == 3.5
    assert reloaded.settings.vla_advisory_fast_enable_thinking is False
    assert reloaded.settings.vla_advisory_deep_enabled is True
    assert reloaded.settings.vla_advisory_deep_model == "qwen3.7-plus-test"
    assert reloaded.settings.vla_advisory_deep_timeout_seconds == 11.0
    assert reloaded.settings.vla_advisory_deep_enable_thinking is True
    assert reloaded.settings.vla_advisory_deep_confidence_threshold == 0.6


def test_settings_read_vla_json_mode_capability_from_env(monkeypatch) -> None:
    monkeypatch.setenv("VLA_PROVIDER_JSON_MODE_ENABLED", "true")

    reloaded = importlib.reload(config_module)

    assert reloaded.settings.vla_provider_json_mode_enabled is True


def test_settings_read_vla_live_proof_values_from_env(monkeypatch) -> None:
    monkeypatch.setenv("VLA_PROVIDER_REQUIRED_ARTIFACT_REFS", "visual_artifact:proof")
    monkeypatch.setenv("VLA_LIVE_PROOF_IMAGE_URL", "data:image/png;base64,aGVsbG8=")
    monkeypatch.setenv("VLA_PROVIDER_LIVE_PROOF_RUN_ID", "qwen-vla-live-test")

    reloaded = importlib.reload(config_module)

    assert reloaded.settings.vla_provider_required_artifact_refs == "visual_artifact:proof"
    assert reloaded.settings.vla_live_proof_image_url == "data:image/png;base64,aGVsbG8="
    assert reloaded.settings.vla_provider_live_proof_run_id == "qwen-vla-live-test"


def test_settings_read_backend_owned_phase3_mirror_configuration(monkeypatch) -> None:
    monkeypatch.setenv(
        "GAMEPLAY_MIRROR_PHASE3_ACTORS_JSON",
        json.dumps(
            [
                {
                    "actor_ref": "actor:configured",
                    "state_group_definitions": [
                        {"group_id": "core.resources", "definition_version": "1", "projection_schema_version": 1}
                    ],
                    "godot_view_policies": [
                        {"group_id": "core.resources", "godot_allowed_fields": ["entries"]}
                    ],
                    "godot_allowed_group_ids": ["core.resources"],
                    "registry_revision": "registry:phase3:v1",
                    "world_config_revision": "world:phase3:v1",
                    "active_patch_set_revision": "patch:phase3:v1",
                }
            ]
        ),
    )

    reloaded = importlib.reload(config_module)

    assert reloaded.settings.gameplay_mirror_phase3_actor_configs[0]["actor_ref"] == "actor:configured"


def test_phase3_mirror_configuration_requires_json_object_array(monkeypatch) -> None:
    monkeypatch.setenv("GAMEPLAY_MIRROR_PHASE3_ACTORS_JSON", "{\"actor_ref\":\"actor:bad\"}")

    with pytest.raises(ValueError, match="GAMEPLAY_MIRROR_PHASE3_ACTORS_JSON"):
        importlib.reload(config_module)


def test_settings_read_siming_llm_modes_from_env(monkeypatch) -> None:
    monkeypatch.setenv("SIMING_LLM_MODE", "http")
    monkeypatch.setenv("SIMING_LLM_API_KEY", "siming-key")
    monkeypatch.setenv("SIMING_LLM_ENDPOINT", "https://api.deepseek.com/chat/completions")
    monkeypatch.setenv("SIMING_LLM_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("SIMING_LLM_TIMEOUT_SECONDS", "6.5")
    monkeypatch.setenv("SIMING_LLM_PROVIDER_ORDER", "deepseek_chat,openai_responses")

    reloaded = importlib.reload(config_module)

    assert reloaded.settings.siming_llm_mode == "http"
    assert reloaded.settings.siming_llm_api_key == "siming-key"
    assert reloaded.settings.siming_llm_endpoint == "https://api.deepseek.com/chat/completions"
    assert reloaded.settings.siming_llm_model == "deepseek-v4-flash"
    assert reloaded.settings.siming_llm_timeout_seconds == 6.5
    assert reloaded.settings.siming_llm_provider_order == ["deepseek_chat", "openai_responses"]


def test_settings_read_project_dotenv_before_process_env(monkeypatch) -> None:
    env_path = Path(config_module.__file__).resolve().parents[2] / ".env"
    tts_env_path = env_path.with_name(".env.tts")
    original = env_path.read_text(encoding="utf-8") if env_path.exists() else None
    tts_original = tts_env_path.read_text(encoding="utf-8") if tts_env_path.exists() else None
    env_path.write_text(
        "\n".join(
            [
                "DIALOGUE_MODE=online",
                "TTS_MODE=stub",
                "SIMING_LLM_MODE=http",
                "SIMING_LLM_API_KEY=dotenv-key",
                "SIMING_LLM_ENDPOINT=https://api.deepseek.com/chat/completions",
                "SIMING_LLM_MODEL=deepseek-chat",
                "SIMING_LLM_TIMEOUT_SECONDS=7.5",
                "SIMING_LLM_PROVIDER_ORDER=deepseek_chat",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("DIALOGUE_MODE", raising=False)
    monkeypatch.delenv("TTS_MODE", raising=False)
    monkeypatch.delenv("SIMING_LLM_MODE", raising=False)
    monkeypatch.delenv("SIMING_LLM_API_KEY", raising=False)
    monkeypatch.delenv("SIMING_LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("SIMING_LLM_MODEL", raising=False)
    monkeypatch.delenv("SIMING_LLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("SIMING_LLM_PROVIDER_ORDER", raising=False)

    try:
        tts_env_path.write_text("", encoding="utf-8")
        reloaded = importlib.reload(config_module)
        assert reloaded.settings.dialogue_mode == "online"
        assert reloaded.settings.tts_mode == "stub"
        assert reloaded.settings.siming_llm_mode == "http"
        assert reloaded.settings.siming_llm_api_key == "dotenv-key"
        assert reloaded.settings.siming_llm_endpoint == "https://api.deepseek.com/chat/completions"
        assert reloaded.settings.siming_llm_model == "deepseek-chat"
        assert reloaded.settings.siming_llm_timeout_seconds == 7.5
        assert reloaded.settings.siming_llm_provider_order == ["deepseek_chat"]
    finally:
        if original is None:
            env_path.unlink(missing_ok=True)
        else:
            env_path.write_text(original, encoding="utf-8")
        if tts_original is None:
            tts_env_path.unlink(missing_ok=True)
        else:
            tts_env_path.write_text(tts_original, encoding="utf-8")
        importlib.reload(config_module)


def test_settings_read_repo_root_dotenv_when_backend_dotenv_is_missing(monkeypatch) -> None:
    backend_env_path = Path(config_module.__file__).resolve().parents[2] / ".env"
    repo_env_path = Path(config_module.__file__).resolve().parents[3] / ".env"
    original_backend = backend_env_path.read_text(encoding="utf-8") if backend_env_path.exists() else None
    original_repo = repo_env_path.read_text(encoding="utf-8") if repo_env_path.exists() else None
    backend_env_path.unlink(missing_ok=True)
    repo_env_path.write_text(
        "\n".join(
            [
                "SIMING_LLM_MODE=http",
                "SIMING_LLM_API_KEY=repo-dotenv-key",
                "SIMING_LLM_ENDPOINT=https://api.deepseek.com/chat/completions",
                "SIMING_LLM_MODEL=deepseek-chat",
                "SIMING_LLM_TIMEOUT_SECONDS=12.5",
                "SIMING_LLM_PROVIDER_ORDER=deepseek_chat",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("SIMING_LLM_MODE", raising=False)
    monkeypatch.delenv("SIMING_LLM_API_KEY", raising=False)
    monkeypatch.delenv("SIMING_LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("SIMING_LLM_MODEL", raising=False)
    monkeypatch.delenv("SIMING_LLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("SIMING_LLM_PROVIDER_ORDER", raising=False)

    try:
        reloaded = importlib.reload(config_module)
        assert reloaded.settings.siming_llm_mode == "http"
        assert reloaded.settings.siming_llm_api_key == "repo-dotenv-key"
        assert reloaded.settings.siming_llm_endpoint == "https://api.deepseek.com/chat/completions"
        assert reloaded.settings.siming_llm_model == "deepseek-chat"
        assert reloaded.settings.siming_llm_timeout_seconds == 12.5
        assert reloaded.settings.siming_llm_provider_order == ["deepseek_chat"]
    finally:
        if original_backend is None:
            backend_env_path.unlink(missing_ok=True)
        else:
            backend_env_path.write_text(original_backend, encoding="utf-8")
        if original_repo is None:
            repo_env_path.unlink(missing_ok=True)
        else:
            repo_env_path.write_text(original_repo, encoding="utf-8")
        importlib.reload(config_module)


def test_process_env_overrides_project_dotenv(monkeypatch) -> None:
    env_path = Path(config_module.__file__).resolve().parents[2] / ".env"
    original = env_path.read_text(encoding="utf-8") if env_path.exists() else None
    env_path.write_text("SIMING_LLM_MODEL=deepseek-chat\n", encoding="utf-8")
    monkeypatch.setenv("SIMING_LLM_MODEL", "deepseek-reasoner")

    try:
        reloaded = importlib.reload(config_module)
        assert reloaded.settings.siming_llm_model == "deepseek-reasoner"
    finally:
        if original is None:
            env_path.unlink(missing_ok=True)
        else:
            env_path.write_text(original, encoding="utf-8")
        importlib.reload(config_module)


def test_vla_env_file_overrides_project_dotenv_without_replacing_other_settings(monkeypatch) -> None:
    project_root = Path(config_module.__file__).resolve().parents[2]
    vla_env_path = project_root / ".env.vla"
    original = vla_env_path.read_text(encoding="utf-8") if vla_env_path.exists() else None
    monkeypatch.delenv("VLA_PROVIDER_MODE", raising=False)
    monkeypatch.delenv("VLA_ADVISORY_FAST_MODEL", raising=False)

    try:
        vla_env_path.write_text(
            "VLA_PROVIDER_MODE=http\nVLA_ADVISORY_FAST_MODEL=qwen3.7-flash-test\n",
            encoding="utf-8",
        )
        reloaded = importlib.reload(config_module)
        assert reloaded.settings.vla_provider_mode == "http"
        assert reloaded.settings.vla_advisory_fast_model == "qwen3.7-flash-test"
    finally:
        if original is None:
            vla_env_path.unlink(missing_ok=True)
        else:
            vla_env_path.write_text(original, encoding="utf-8")
        importlib.reload(config_module)


def test_tts_env_file_overrides_project_dotenv_without_replacing_other_settings(monkeypatch) -> None:
    project_root = Path(config_module.__file__).resolve().parents[2]
    tts_env_path = project_root / ".env.tts"
    original = tts_env_path.read_text(encoding="utf-8") if tts_env_path.exists() else None
    monkeypatch.delenv("TTS_DEFAULT_VOICE", raising=False)
    monkeypatch.delenv("TTS_PROVIDER_MODEL", raising=False)

    try:
        tts_env_path.write_text(
            "TTS_DEFAULT_VOICE=voice-from-tts-file\nTTS_PROVIDER_MODEL=qwen-audio-3.0-tts-flash\n",
            encoding="utf-8",
        )
        reloaded = importlib.reload(config_module)
        assert reloaded.settings.tts_default_voice == "voice-from-tts-file"
        assert reloaded.settings.tts_provider_model == "qwen-audio-3.0-tts-flash"
    finally:
        if original is None:
            tts_env_path.unlink(missing_ok=True)
        else:
            tts_env_path.write_text(original, encoding="utf-8")
        importlib.reload(config_module)
def test_deepseek_aliases_do_not_feed_character_settings(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "legacy-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "legacy-model")
    monkeypatch.setenv("CHARACTER_MODEL_API_KEY", "")
    monkeypatch.setenv("CHARACTER_MODEL_MODEL", "")

    reloaded = importlib.reload(config_module)

    assert reloaded.settings.character_model_api_key is None
    assert reloaded.settings.character_model_model is None


def test_character_timeout_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(character_model_timeout_seconds=0)


def test_character_dialogue_cascade_limit_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(character_dialogue_cascade_limit=0)


def test_siming_timeout_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(siming_llm_timeout_seconds=0)


def test_siming_routes_json_without_legacy_order_loads_empty_provider_order(monkeypatch) -> None:
    monkeypatch.setenv(
        "SIMING_LLM_ROUTES_JSON",
        json.dumps(
            [
                {
                    "route_id": "deepseek-live",
                    "provider": "deepseek_chat",
                    "endpoint": "https://api.deepseek.com/chat/completions",
                    "model": "deepseek-chat",
                    "api_key": "route-key",
                    "enabled": True,
                }
            ]
        ),
    )
    monkeypatch.setenv("SIMING_LLM_PROVIDER_ORDER", "")

    reloaded = importlib.reload(config_module)

    assert reloaded.settings.siming_llm_provider_order == []
    assert reloaded.settings.siming_llm_routes[0].provider == "deepseek_chat"
