import pytest
from pydantic import ValidationError

from app.models.siming_heavenly_graph import HeavenlyGraphScope
from app.models.siming_heavenly_memory import SimingContextRequest, WorldFactMemoryEntry


def test_world_fact_requires_authority_result_ref() -> None:
    with pytest.raises(ValidationError, match="authority_result_ref"):
        WorldFactMemoryEntry(
            entry_id="fact:letter:removed",
            world_anchor_id="obj_letter",
            state_key="surface_state",
            state_value="removed_from_surface",
            evidence_refs=["visual:letter:gone"],
        )


def test_context_request_rejects_actor_private_scope() -> None:
    with pytest.raises(ValidationError, match="siming_heavenly"):
        SimingContextRequest(
            scope=HeavenlyGraphScope(
                world_id="world:demo", session_id="session:demo", story_branch_id="branch:main",
                graph_namespace="actor_private", owner_actor_id="char_b",
            ),
            valid_at=10, recorded_at=10, seed_node_ids=["fact:letter:removed"],
            relevant_actor_ids=["char_b"],
        )
