import pytest
from pydantic import ValidationError

from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
)


def make_scope(*, branch_id: str = "branch:main") -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:demo",
        session_id="session:demo",
        story_branch_id=branch_id,
        room_id="room_demo",
        scene_id="scene_demo",
    )


def make_provenance(*, source_ref: str = "authority:event:1") -> GraphProvenance:
    return GraphProvenance(
        source_kind="authority_event",
        source_ref=source_ref,
        causation_id="cause:1",
        correlation_id="corr:1",
        producer_system="system_l6",
    )


def make_node(
    *,
    node_id: str = "fact:lamp",
    revision: int = 1,
    supersedes_revision: int | None = None,
    branch_id: str = "branch:main",
) -> HeavenlyGraphNode:
    return HeavenlyGraphNode(
        node_id=node_id,
        node_type="world_fact",
        scope=make_scope(branch_id=branch_id),
        validity=GraphValidity(valid_from=10),
        recorded_at=12,
        revision=revision,
        supersedes_revision=supersedes_revision,
        attributes={"state": "dim"},
        provenance=make_provenance(),
    )


def test_graph_validity_rejects_empty_half_open_interval() -> None:
    with pytest.raises(ValidationError, match="valid_to must be greater"):
        GraphValidity(valid_from=10, valid_to=10)


def test_first_revision_rejects_supersedes_revision() -> None:
    with pytest.raises(ValidationError, match="revision 1 cannot supersede"):
        make_node(revision=1, supersedes_revision=1)


def test_later_revision_requires_immediate_predecessor() -> None:
    with pytest.raises(ValidationError, match="immediate predecessor"):
        make_node(revision=3, supersedes_revision=1)


def test_write_batch_rejects_cross_scope_entities() -> None:
    with pytest.raises(ValidationError, match="batch scope"):
        HeavenlyGraphWriteBatch(
            transaction_id="graph_tx:1",
            idempotency_key="authority:event:1",
            scope=make_scope(branch_id="branch:main"),
            nodes=[make_node(branch_id="branch:other")],
        )


def test_write_batch_rejects_duplicate_entity_revisions() -> None:
    node = make_node()

    with pytest.raises(ValidationError, match="duplicate node revision"):
        HeavenlyGraphWriteBatch(
            transaction_id="graph_tx:1",
            idempotency_key="authority:event:1",
            scope=make_scope(),
            nodes=[node, node.model_copy(deep=True)],
        )
