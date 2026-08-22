import pytest

from app.models.siming_heavenly_graph import (
    GraphProvenance,
    HeavenlyGraphScope,
)
from app.models.siming_heavenly_memory import StorylineObligationMemoryEntry
from app.models.siming_story_graph import (
    AuthorityStoryOutcome,
    StoryNodeBlueprint,
    StoryOutcomeEffect,
    StoryOutcomePort,
)
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService
from app.services.siming_story_graph_runtime import (
    SimingStoryGraphRuntime,
    StoryNodeTransitionError,
)


def _scope() -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:demo",
        session_id="session:demo",
        story_branch_id="branch:main",
        room_id="room:throne",
        scene_id="scene:throne",
    )


def _provenance(blueprint_id: str) -> GraphProvenance:
    return GraphProvenance(
        source_kind="authored_seed",
        source_ref=f"author:story:{blueprint_id}",
        causation_id=f"author:story:{blueprint_id}",
        correlation_id=f"author:story:{blueprint_id}",
        producer_system="story_authoring",
    )


def _blueprints() -> list[StoryNodeBlueprint]:
    return [
        StoryNodeBlueprint(blueprint_id="N1", title="Bloodstain discovery"),
        StoryNodeBlueprint(blueprint_id="N2", title="Bell anomaly"),
        StoryNodeBlueprint(
            blueprint_id="N3",
            title="Repair record opportunity",
            outcome_ports=[
                StoryOutcomePort(
                    port_id="player_destroyed_evidence",
                    required_result_type="object_state_result",
                    target_ref="obj_letter",
                    required_state="removed_from_surface",
                    outcome_semantic="resolved_with_divergence",
                    effects=[
                        StoryOutcomeEffect(
                            target_blueprint_id="N4",
                            effect="close_permanently",
                            reason="player destroyed the original evidence",
                        ),
                        StoryOutcomeEffect(
                            target_blueprint_id="N5",
                            effect="mark_unreachable",
                            reason="the evidence route is closed by ledger",
                        ),
                    ],
                )
            ],
        ),
        StoryNodeBlueprint(blueprint_id="N4", title="Original evidence confrontation"),
        StoryNodeBlueprint(blueprint_id="N5", title="Public time contradiction"),
    ]


def _outcome() -> AuthorityStoryOutcome:
    return AuthorityStoryOutcome(
        result_type="object_state_result",
        target_ref="obj_letter",
        current_state="removed_from_surface",
        authority_result_ref="esm:destroy:1",
        correlation_id="corr:destroy:1",
        recorded_at=100,
    )


@pytest.fixture
def graph() -> InMemoryHeavenlyGraphAdapter:
    return InMemoryHeavenlyGraphAdapter()


@pytest.fixture
def memory(graph: InMemoryHeavenlyGraphAdapter) -> SimingHeavenlyMemoryService:
    return SimingHeavenlyMemoryService(graph)


@pytest.fixture
def runtime(
    graph: InMemoryHeavenlyGraphAdapter,
    memory: SimingHeavenlyMemoryService,
) -> SimingStoryGraphRuntime:
    return SimingStoryGraphRuntime(graph, memory)


def seed_n1_to_n5(runtime: SimingStoryGraphRuntime, scope: HeavenlyGraphScope) -> None:
    for blueprint in _blueprints():
        runtime.seed_blueprint(
            scope=scope,
            blueprint=blueprint,
            provenance=_provenance(blueprint.blueprint_id),
            recorded_at=10,
        )
        runtime.instantiate(
            scope=scope,
            blueprint_id=blueprint.blueprint_id,
            node_id=f"runtime:{blueprint.blueprint_id}:main",
            causal_basis_refs=[],
            recorded_at=10,
        )

    for recorded_at, expected, target in [
        (11, "latent", "eligible"),
        (12, "eligible", "selected"),
        (13, "selected", "staged"),
        (14, "staged", "active"),
        (15, "active", "resolving"),
    ]:
        runtime.transition(
            scope=scope,
            node_id="runtime:N3:main",
            expected=expected,
            target=target,
            reason="standard story progression",
            recorded_at=recorded_at,
        )


def test_destroyed_letter_resolves_divergence_and_permanently_closes_path(
    runtime: SimingStoryGraphRuntime,
    memory: SimingHeavenlyMemoryService,
) -> None:
    scope = _scope()
    seed_n1_to_n5(runtime, scope)

    result = runtime.apply_authority_outcome(scope=scope, outcome=_outcome())

    assert result.nodes["N3"].lifecycle == "resolved"
    assert result.nodes["N3"].outcome_port == "player_destroyed_evidence"
    assert result.nodes["N3"].outcome_semantic == "resolved_with_divergence"
    assert result.nodes["N4"].model_dump(
        include={"lifecycle", "closure_reason", "terminal", "reopen_policy"}
    ) == {
        "lifecycle": "aborted",
        "closure_reason": "closed_by_player_choice",
        "terminal": True,
        "reopen_policy": "never",
    }
    assert result.nodes["N5"].reachability == "unreachable_by_ledger"
    assert memory.get_entry(
        scope=scope,
        entry_id="story_outcome:esm:destroy:1",
        valid_at=100,
    ) == StorylineObligationMemoryEntry(
        entry_id="story_outcome:esm:destroy:1",
        record_type="outcome_port",
        lifecycle="resolved_with_divergence",
        supporting_fact_refs=["esm:destroy:1"],
    )


def test_terminal_node_instance_cannot_be_reactivated(
    runtime: SimingStoryGraphRuntime,
) -> None:
    scope = _scope()
    seed_n1_to_n5(runtime, scope)
    closed_n4 = runtime.apply_authority_outcome(scope=scope, outcome=_outcome()).nodes["N4"]

    with pytest.raises(StoryNodeTransitionError, match="terminal"):
        runtime.transition(
            scope=scope,
            node_id=closed_n4.node_id,
            expected="aborted",
            target="cooldown",
            reason="retry",
            recorded_at=101,
        )


def test_authority_outcome_requires_matching_port_predicate(
    runtime: SimingStoryGraphRuntime,
) -> None:
    scope = _scope()
    seed_n1_to_n5(runtime, scope)

    result = runtime.apply_authority_outcome(
        scope=scope,
        outcome=_outcome().model_copy(update={"current_state": "still_on_surface"}),
    )

    assert result.nodes == {}
    assert runtime.read_runtime_node(
        scope=scope,
        node_id="runtime:N3:main",
        valid_at=100,
    ).lifecycle == "resolving"


def test_terminal_outcome_is_idempotent_and_authored_blueprint_is_immutable(
    runtime: SimingStoryGraphRuntime,
) -> None:
    scope = _scope()
    seed_n1_to_n5(runtime, scope)
    before = runtime.read_blueprint(scope=scope, blueprint_id="N3", valid_at=99)

    first = runtime.apply_authority_outcome(scope=scope, outcome=_outcome())
    second = runtime.apply_authority_outcome(scope=scope, outcome=_outcome())

    assert second == first
    assert runtime.read_blueprint(scope=scope, blueprint_id="N3", valid_at=101) == before


def test_transition_rejects_stale_expected_lifecycle(
    runtime: SimingStoryGraphRuntime,
) -> None:
    scope = _scope()
    seed_n1_to_n5(runtime, scope)

    with pytest.raises(StoryNodeTransitionError, match="expected lifecycle"):
        runtime.transition(
            scope=scope,
            node_id="runtime:N3:main",
            expected="latent",
            target="eligible",
            reason="stale client",
            recorded_at=100,
        )
