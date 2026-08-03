import pytest

from app.gameplay.godot_mirror_projection import GodotGameplayMirrorProjectionError, project_godot_runtime_state
from app.gameplay.runtime_state import CharacterGameRuntimeStateBuilder, StateGroupDefinition, StateGroupRegistry
from app.gameplay.state_group_views import StateGroupConsumerViewPolicy, StateGroupViewProjector


def _state(payload: dict[str, object] | None = None):
    registry = StateGroupRegistry()
    registry.register(StateGroupDefinition(group_id="core.resources", definition_version="1", projection_schema_version=1))
    return CharacterGameRuntimeStateBuilder(registry).build(actor_ref="actor:a", enabled_group_ids=("core.resources",), group_payloads={"core.resources": payload or {"current": 7, "private_note": "hidden"}}, source_revision_vector={"stream": 1}, registry_revision="registry", world_config_revision="world", active_patch_set_revision="patch")


def test_projector_requires_filtered_godot_view_and_does_not_leak_fields() -> None:
    view = StateGroupViewProjector([StateGroupConsumerViewPolicy(group_id="core.resources", godot_allowed_fields=("current",))]).godot_view(_state(), allowed_group_ids=("core.resources",))
    envelope = project_godot_runtime_state(view)

    assert envelope["projection_kind"] == "gameplay_runtime_state.godot.v1"
    assert envelope["groups"]["core.resources"]["payload"] == {"current": 7}
    with pytest.raises(GodotGameplayMirrorProjectionError, match="godot_view_required"):
        project_godot_runtime_state(StateGroupViewProjector([]).authority_view(_state(), allowed_group_ids=("core.resources",)))


def test_projector_rejects_forbidden_fields_nested_inside_an_allowed_group() -> None:
    state = _state({"current": 7, "summary": {"private_mind_state": "must-not-cross"}})
    view = StateGroupViewProjector(
        [StateGroupConsumerViewPolicy(group_id="core.resources", godot_allowed_fields=("current", "summary"))]
    ).godot_view(state, allowed_group_ids=("core.resources",))

    with pytest.raises(GodotGameplayMirrorProjectionError, match="forbidden_projection_field"):
        project_godot_runtime_state(view)
