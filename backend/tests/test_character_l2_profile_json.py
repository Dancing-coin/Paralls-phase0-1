"""Profile caches must be safe to persist in a JsonValue cognition frame."""

from types import SimpleNamespace

import pytest
from pydantic import BaseModel, JsonValue, TypeAdapter

from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service


class _ResourceTemplate(BaseModel):
    world_scope: tuple[str, ...]
    resources: tuple[dict[str, str], ...]


class _Profile(BaseModel):
    resource_template: _ResourceTemplate


@pytest.mark.parametrize("registry_backed", [True, False])
def test_nested_resource_template_remains_json_safe_in_l2_profile_cache(registry_backed):
    profile = _Profile(resource_template=_ResourceTemplate(
        world_scope=("world:main",), resources=({"resource_id": "core.stamina"},)))
    source = SimpleNamespace(get=lambda _: profile, load=lambda _: profile)
    service = CharacterAgentL2Service(profile_registry=source if registry_backed else None,
                                      profile_loader=source)
    first = service._profile_for_actor("char_a")
    TypeAdapter(JsonValue).validate_python(first)
    assert first["resource_template"]["world_scope"] == ["world:main"]
    first["resource_template"]["resources"].clear()
    assert service._profile_for_actor("char_a")["resource_template"]["resources"] == [
        {"resource_id": "core.stamina"}]
