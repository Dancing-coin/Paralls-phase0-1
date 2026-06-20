import importlib
import os

import app.config as config_module


def test_settings_default_to_stub_modes_when_env_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("DIALOGUE_MODE", raising=False)
    monkeypatch.delenv("TTS_MODE", raising=False)

    reloaded = importlib.reload(config_module)

    assert reloaded.settings.dialogue_mode == "stub"
    assert reloaded.settings.tts_mode == "stub"


def test_settings_read_dialogue_and_tts_modes_from_env(monkeypatch) -> None:
    monkeypatch.setenv("DIALOGUE_MODE", "online")
    monkeypatch.setenv("TTS_MODE", "stub")

    reloaded = importlib.reload(config_module)

    assert reloaded.settings.dialogue_mode == "online"
    assert reloaded.settings.tts_mode == "stub"
