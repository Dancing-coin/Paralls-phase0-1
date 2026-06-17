from app.character_agent.gateway.model_router import CharacterModelRouter


def test_model_router_defaults_to_online_route() -> None:
    router = CharacterModelRouter()

    route = router.resolve_route()

    assert route["route_mode"] == "online_default"
    assert route["provider_kind"] == "online"


def test_model_router_supports_local_and_hybrid_routes() -> None:
    router = CharacterModelRouter()

    local_route = router.resolve_route("local_only")
    hybrid_route = router.resolve_route("hybrid_ready")

    assert local_route["route_mode"] == "local_only"
    assert local_route["provider_kind"] == "local"
    assert hybrid_route["route_mode"] == "hybrid_ready"
    assert hybrid_route["provider_kind"] == "hybrid"
