from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_character_model_live as live
from registry import load_profile_registry


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_character_model_live_profile_is_explicit_only() -> None:
    registry = load_profile_registry(PROJECT_ROOT)

    profile = registry.profiles["character-model-live"]
    assert profile["script"] == "scripts/verification/verify_character_model_live.py"
    assert profile["include_in_all"] is False
    assert profile["result_artifact"] == ".harness/verification/character-model-live-report.json"


def test_character_model_live_rejects_missing_key(monkeypatch) -> None:
    monkeypatch.setattr(live.settings, "character_model_provider_kind", "deepseek")
    monkeypatch.setattr(live.settings, "character_model_api_key", None)
    monkeypatch.setattr(live.settings, "character_model_endpoint", "https://api.deepseek.com")
    monkeypatch.setattr(live.settings, "character_model_model", "deepseek-chat")
    monkeypatch.setattr(live.settings, "dialogue_mode", "online")

    result = live._config_guard()

    assert result is not None
    assert result["id"] == "credential_check"
    assert result["status"] == "failed"


def test_character_model_live_rejects_stub_and_route_override(monkeypatch) -> None:
    monkeypatch.setattr(live.settings, "character_model_provider_kind", "deepseek")
    monkeypatch.setattr(live.settings, "character_model_api_key", "key")
    monkeypatch.setattr(live.settings, "character_model_endpoint", "https://api.deepseek.com")
    monkeypatch.setattr(live.settings, "character_model_model", "deepseek-chat")
    monkeypatch.setattr(live.settings, "dialogue_mode", "stub")
    assert live._config_guard()["notes"] == "DIALOGUE_MODE=stub"  # type: ignore[index]

    monkeypatch.setattr(live.settings, "dialogue_mode", "online")
    monkeypatch.setenv("CHARACTER_MODEL_ROUTE_OVERRIDE", "local_only")
    assert "CHARACTER_MODEL_ROUTE_OVERRIDE" in str(live._config_guard()["notes"])  # type: ignore[index]


def test_character_model_live_rejects_non_deepseek_provider(monkeypatch) -> None:
    monkeypatch.setattr(live.settings, "character_model_provider_kind", "qwen")

    result = live._config_guard()

    assert result is not None
    assert "provider_kind=qwen" in str(result["notes"])
