from app.config import Settings
from app.services.siming_llm_provider import (
    DisabledSimingLlmCandidateProvider,
    HttpSimingLlmCandidateProvider,
    build_siming_llm_provider,
)


def test_settings_disable_siming_llm_by_default() -> None:
    settings = Settings()

    assert settings.siming_llm_mode == "disabled"
    assert settings.siming_llm_api_key is None


def test_provider_factory_returns_disabled_without_api_key() -> None:
    provider = build_siming_llm_provider(Settings(siming_llm_mode="http", siming_llm_api_key=None))

    assert isinstance(provider, DisabledSimingLlmCandidateProvider)


def test_provider_factory_returns_http_provider_when_configured() -> None:
    provider = build_siming_llm_provider(
        Settings(
            siming_llm_mode="http",
            siming_llm_api_key="test-key",
            siming_llm_endpoint="https://example.invalid/v1/responses",
            siming_llm_model="test-model",
        )
    )

    assert isinstance(provider, HttpSimingLlmCandidateProvider)
