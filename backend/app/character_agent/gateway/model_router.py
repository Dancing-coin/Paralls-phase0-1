import os

from app.config import settings


class CharacterModelRouter:
    def resolve_route(self, route_override: str | None = None) -> dict[str, str]:
        env_override = os.getenv("CHARACTER_MODEL_ROUTE_OVERRIDE", "").strip()
        if route_override is None and env_override != "":
            route_override = env_override
        if route_override == "local_only":
            return {"route_mode": "local_only", "provider_kind": "local"}
        if route_override == "hybrid_ready":
            return {"route_mode": "hybrid_ready", "provider_kind": "hybrid"}
        provider_kind = str(settings.character_model_provider_kind or "").strip() or "qwen"
        return {"route_mode": "online_default", "provider_kind": provider_kind}
