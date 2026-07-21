from app.character_agent.gateway.model_router import CharacterModelRouter
from app.config import settings


def test_model_router_defaults_to_configured_online_provider(monkeypatch) -> None:
    monkeypatch.setattr(settings, "character_model_provider_kind", "qwen")
    router = CharacterModelRouter()

    route = router.resolve_route()

    assert route["route_mode"] == "online_default"
    assert route["provider_kind"] == "qwen"


def test_model_router_uses_current_settings_provider(monkeypatch) -> None:
    monkeypatch.setattr(settings, "character_model_provider_kind", "seed_doubao")

    route = CharacterModelRouter().resolve_route()

    assert route["route_mode"] == "online_default"
    assert route["provider_kind"] == "seed_doubao"


def test_model_router_supports_local_and_hybrid_routes() -> None:
    router = CharacterModelRouter()

    local_route = router.resolve_route("local_only")
    hybrid_route = router.resolve_route("hybrid_ready")

    assert local_route["route_mode"] == "local_only"
    assert local_route["provider_kind"] == "local"
    assert hybrid_route["route_mode"] == "hybrid_ready"
    assert hybrid_route["provider_kind"] == "hybrid"
