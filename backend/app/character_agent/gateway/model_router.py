class CharacterModelRouter:
    def resolve_route(self, route_override: str | None = None) -> dict[str, str]:
        if route_override == "local_only":
            return {"route_mode": "local_only", "provider_kind": "local"}
        if route_override == "hybrid_ready":
            return {"route_mode": "hybrid_ready", "provider_kind": "hybrid"}
        return {"route_mode": "online_default", "provider_kind": "deepseek"}
