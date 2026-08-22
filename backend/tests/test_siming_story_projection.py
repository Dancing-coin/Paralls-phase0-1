import pytest
from pydantic import ValidationError

from app.models.siming_heavenly_graph import HeavenlyGraphScope
from app.models.siming_heavenly_memory import SimingCompiledContext, SimingContextRequest
from app.services.siming_story_projection import SimingGraphProjectionBundle, SimingStoryProjection


def _context() -> SimingCompiledContext:
    request = SimingContextRequest(
        scope=HeavenlyGraphScope(
            world_id="world:demo",
            session_id="session:demo",
            story_branch_id="branch:main",
            room_id="room:demo",
            scene_id="scene:demo",
        ),
        valid_at=20,
        seed_node_ids=["fact:b", "fact:a"],
    )
    return SimingCompiledContext(
        request=request,
        selected_node_refs=["fact:a", "fact:b"],
        selected_relation_refs=["rel:a"],
        truncated=False,
        context_hash="a" * 64,
    )


def test_projection_is_disposable_read_only_graph_basis_with_runtime_authorities() -> None:
    projection = SimingStoryProjection()
    bundle = projection.project(_context())

    assert set(bundle.model_fields_set) == {"state_tree", "storyline", "read_model", "debug_summary"}
    assert bundle.state_tree.environment.authority == "mirror"
    assert bundle.state_tree.character.authority == "mirror"
    assert bundle.state_tree.storyline.owner_system == "siming"
    assert bundle.state_tree.storyline.authority == "editable"
    assert bundle.read_model.derived_from_snapshot_ref == "a" * 64
    assert bundle.state_tree.snapshot_id == f"state-tree:{'a' * 64}"
    assert bundle.storyline.snapshot_id == f"storyline:{'a' * 64}"
    assert not any("write" in name.lower() for name in dir(projection))


def test_projection_bundle_rejects_non_json_debug_values() -> None:
    bundle = SimingStoryProjection().project(_context())

    with pytest.raises(ValidationError):
        SimingGraphProjectionBundle(
            state_tree=bundle.state_tree,
            storyline=bundle.storyline,
            read_model=bundle.read_model,
            debug_summary={"bad": object()},
        )
