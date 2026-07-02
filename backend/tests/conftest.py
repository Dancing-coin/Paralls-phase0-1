from __future__ import annotations

import sys

import pytest

from app.config import Settings


@pytest.fixture(autouse=True)
def disable_live_siming_llm_for_unit_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    test_settings = Settings()
    import app.config as config_module

    monkeypatch.setattr(config_module, "settings", test_settings)
    app_main = sys.modules.get("app.main")
    if app_main is not None:
        monkeypatch.setattr(app_main, "settings", test_settings)
