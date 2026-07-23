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
    original = env_path.read_text(encoding="utf-8") if env_path.exists() else None
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
