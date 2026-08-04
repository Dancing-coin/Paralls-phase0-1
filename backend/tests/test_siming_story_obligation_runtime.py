import pytest

from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
)
from app.models.siming_story_graph import NarrativeAttractor, NarrativeObligation, RuntimeStoryNode
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService
from app.services.siming_story_obligation_runtime import (
    SimingStoryObligationRuntime,
    StoryObligationError,
)


def _scope() -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:demo",
        session_id="session:demo",
        story_branch_id="branch:main",
    )


def _provenance(ref: str) -> GraphProvenance:
    return GraphProvenance(
        source_kind="runtime_outcome",
        source_ref=ref,
        causation_id=ref,
        correlation_id="corr:destroy:1",
        producer_system="siming_story_obligation_runtime",
    )


def obligation_o2() -> NarrativeObligation:
    return NarrativeObligation(
        obligation_id="O2",
        description="The time contradiction must have consequences.",
        status="open",
        pressure=0.8,
        source_fact_refs=["fact:time:contradiction"],
    )


def obligation_o6() -> NarrativeObligation:
    return NarrativeObligation(
        obligation_id="O6",
        description="The player cover-up must have consequences.",
        status="open",
        pressure=0.7,
        source_fact_refs=["esm:destroy:1"],
    )


@pytest.fixture
def graph() -> InMemoryHeavenlyGraphAdapter:
    return InMemoryHeavenlyGraphAdapter()


@pytest.fixture
def obligations(graph: InMemoryHeavenlyGraphAdapter) -> SimingStoryObligationRuntime:
    return SimingStoryObligationRuntime(graph, SimingHeavenlyMemoryService(graph))


def test_o2_transforms_to_o6_without_fulfillment(
    obligations: SimingStoryObligationRuntime,
) -> None:
    scope = _scope()
    obligations.seed(
        scope=scope,
        obligation=obligation_o2(),
        provenance=_provenance("story:O2"),
        recorded_at=10,
    )

    result = obligations.transform(
        scope=scope,
        source_obligation_id="O2",
        replacement=obligation_o6(),
        authority_result_ref="esm:destroy:1",
        correlation_id="corr:destroy:1",
        recorded_at=100,
    )

    assert result.source.status == "transformed"
    assert result.source.transformed_to_refs == ["O6"]
    assert result.replacement.status == "open"
    assert obligations.read(scope=scope, obligation_id="O2", valid_at=101) == result.source
    assert obligations.read(scope=scope, obligation_id="O6", valid_at=101) == result.replacement


def test_transform_rejects_replacement_marked_fulfilled_by_staging(
    obligations: SimingStoryObligationRuntime,
) -> None:
    scope = _scope()
    obligations.seed(
        scope=scope,
        obligation=obligation_o2(),
        provenance=_provenance("story:O2"),
        recorded_at=10,
    )

    with pytest.raises(StoryObligationError, match="open"):
        obligations.transform(
            scope=scope,
            source_obligation_id="O2",
            replacement=obligation_o6().model_copy(update={"status": "fulfilled"}),
            authority_result_ref="esm:destroy:1",
            correlation_id="corr:destroy:1",
            recorded_at=100,
        )


def test_attractor_allows_new_causal_instance_after_original_route_closes(
    graph: InMemoryHeavenlyGraphAdapter,
    obligations: SimingStoryObligationRuntime,
) -> None:
    scope = _scope()
    graph.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id="story:closed:N4",
            idempotency_key="story:closed:N4",
            scope=scope,
            nodes=[
                HeavenlyGraphNode(
                    node_id="runtime:N4:main",
                    node_type="runtime_story_node",
                    scope=scope,
                    validity=GraphValidity(valid_from=10),
                    recorded_at=10,
                    revision=1,
                    provenance=_provenance("esm:destroy:1"),
                    attributes=RuntimeStoryNode(
                        node_id="runtime:N4:main",
                        blueprint_id="N4",
                        lifecycle="aborted",
                        reachability="unreachable",
                        closure_reason="closed_by_player_choice",
                        terminal=True,
                        reopen_policy="never",
                    ).model_dump(mode="json"),
                )
            ],
        )
    )
    obligations.seed_attractor(
        scope=scope,
        attractor=NarrativeAttractor(
            attractor_id="A1",
            description="Reach a consequence for the destroyed evidence.",
            forbidden_terminal_node_refs=["runtime:N4:main"],
        ),
        provenance=_provenance("story:A1"),
        recorded_at=10,
    )

    assert obligations.evaluate_attractor(scope=scope, attractor_id="A1", valid_at=20).reachability == "blocked"

    graph.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id="story:new:N4",
            idempotency_key="story:new:N4",
            scope=scope,
            nodes=[
                HeavenlyGraphNode(
                    node_id="runtime:N4:aftermath",
                    node_type="runtime_story_node",
                    scope=scope,
                    validity=GraphValidity(valid_from=21),
                    recorded_at=21,
                    revision=1,
                    provenance=_provenance("fact:new:consequence"),
                    attributes=RuntimeStoryNode(
                        node_id="runtime:N4:aftermath",
                        blueprint_id="N4",
                        lifecycle="latent",
                        reopen_policy="new_causal_basis",
                        causal_basis_refs=["fact:new:consequence"],
                    ).model_dump(mode="json"),
                )
            ],
        )
    )

    assert obligations.evaluate_attractor(scope=scope, attractor_id="A1", valid_at=30).reachability == "reachable"
