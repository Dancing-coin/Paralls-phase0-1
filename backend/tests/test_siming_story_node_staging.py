import pytest

from app.models.siming_heavenly_graph import GraphProvenance, HeavenlyGraphScope
from app.models.siming_resource_capability import (
    ResourceCapabilityPackage,
    ResourceMatch,
    StagingAck,
    StagingRequest,
)
from app.models.siming_story_graph import NarrativeObligation, StoryNodeBlueprint
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService
from app.services.siming_story_graph_runtime import SimingStoryGraphRuntime
from app.services.siming_story_node_staging import (
    SimingStoryNodeStaging,
    StoryNodeStagingError,
)
from app.services.siming_story_obligation_runtime import SimingStoryObligationRuntime


class _RejectingStagingGraph(InMemoryHeavenlyGraphAdapter):
    def write_batch(self, batch):  # type: ignore[no-untyped-def]
        if any(node.node_type == "memory:intervention_outcome" for node in batch.nodes):
            raise RuntimeError("staging write failed")
        return super().write_batch(batch)


def _scope() -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:demo",
        session_id="session:demo",
        story_branch_id="branch:main",
        room_id="room:throne",
        scene_id="scene:throne",
    )


def _provenance(ref: str) -> GraphProvenance:
    return GraphProvenance(
        source_kind="runtime_outcome",
        source_ref=ref,
        causation_id=ref,
        correlation_id="corr:seed",
        producer_system="test_siming_story_node_staging",
    )


def _resource_match() -> ResourceMatch:
    return ResourceMatch(
        accepted=True,
        capability=ResourceCapabilityPackage(
            capability_id="main_demo_throne_room",
            asset_bundle="main_demo_throne_room",
            scene_refs=["MainDemo.tscn"],
            actor_ids=["char_b", "char_c"],
            object_ids=["obj_letter"],
            environment_ids=["env_lamp"],
            realization_keys=["look_at_target"],
            semantic_purposes=["private_confrontation"],
            load_cost=0.0,
            loaded=True,
            cooldown_until=0,
        ),
        realization_signature="sig:private-confrontation",
    )


def _ack(source: str, accepted: bool, reason: str = "", correlation_id: str = "corr:1") -> StagingAck:
    return StagingAck(
        source=source,
        correlation_id=correlation_id,
        accepted=accepted,
        reason=reason,
    )


@pytest.fixture
def graph() -> InMemoryHeavenlyGraphAdapter:
    return InMemoryHeavenlyGraphAdapter()


@pytest.fixture
def memory(graph: InMemoryHeavenlyGraphAdapter) -> SimingHeavenlyMemoryService:
    return SimingHeavenlyMemoryService(graph)


@pytest.fixture
def story(
    graph: InMemoryHeavenlyGraphAdapter,
    memory: SimingHeavenlyMemoryService,
) -> SimingStoryGraphRuntime:
    return SimingStoryGraphRuntime(graph, memory)


@pytest.fixture
def obligations(
    graph: InMemoryHeavenlyGraphAdapter,
    memory: SimingHeavenlyMemoryService,
) -> SimingStoryObligationRuntime:
    return SimingStoryObligationRuntime(graph, memory)


@pytest.fixture
def stager(
    story: SimingStoryGraphRuntime,
    memory: SimingHeavenlyMemoryService,
    obligations: SimingStoryObligationRuntime,
) -> SimingStoryNodeStaging:
    return SimingStoryNodeStaging(story, memory, obligations)


@pytest.fixture
def staging_request(
    story: SimingStoryGraphRuntime,
    obligations: SimingStoryObligationRuntime,
) -> StagingRequest:
    scope = _scope()
    story.seed_blueprint(
        scope=scope,
        blueprint=StoryNodeBlueprint(blueprint_id="N1", title="Letter confrontation"),
        provenance=_provenance("author:story:N1"),
        recorded_at=10,
    )
    story.instantiate(
        scope=scope,
        blueprint_id="N1",
        node_id="runtime:N1:main",
        causal_basis_refs=[],
        recorded_at=10,
    )
    story.transition(
        scope=scope,
        node_id="runtime:N1:main",
        expected="latent",
        target="eligible",
        reason="facts_confirmed",
        recorded_at=11,
    )
    story.transition(
        scope=scope,
        node_id="runtime:N1:main",
        expected="eligible",
        target="selected",
        reason="hard_gates_passed",
        recorded_at=12,
    )
    obligations.seed(
        scope=scope,
        obligation=NarrativeObligation(
            obligation_id="O1",
            description="The letter must have consequences.",
            status="open",
            pressure=0.8,
            source_fact_refs=["fact:letter:discovered"],
        ),
        provenance=_provenance("story:O1"),
        recorded_at=10,
    )
    return StagingRequest(
        scope=scope,
        node_id="runtime:N1:main",
        correlation_id="corr:1",
        obligation_id="O1",
        recorded_at=20,
        resource_match=_resource_match(),
    )


def test_node_stages_only_after_all_required_acks(
    stager: SimingStoryNodeStaging,
    story: SimingStoryGraphRuntime,
    memory: SimingHeavenlyMemoryService,
    staging_request: StagingRequest,
) -> None:
    result = stager.complete(
        staging_request,
        acks=[_ack("godot", True), _ack("character", True), _ack("esm", True)],
    )

    assert result.status == "staged"
    assert result.story_node_lifecycle == "staged"
    assert result.obligation_status == "open"
    assert story.read_runtime_node(
        scope=staging_request.scope,
        node_id=staging_request.node_id,
        valid_at=20,
    ).lifecycle == "staged"
    assert memory.get_entry(
        scope=staging_request.scope,
        entry_id="story_staging:runtime:N1:main:corr:1",
        valid_at=20,
    ).stage == "staging"


def test_character_refusal_aborts_before_activation_and_keeps_obligation_open(
    stager: SimingStoryNodeStaging,
    story: SimingStoryGraphRuntime,
    obligations: SimingStoryObligationRuntime,
    staging_request: StagingRequest,
) -> None:
    result = stager.complete(
        staging_request,
        acks=[
            _ack("godot", True),
            _ack("character", False, "actor_refused"),
            _ack("esm", True),
        ],
    )

    assert result.status == "aborted_before_activation"
    assert result.story_node_lifecycle == "aborted"
    assert result.obligation_status == "open"
    assert story.read_runtime_node(
        scope=staging_request.scope,
        node_id=staging_request.node_id,
        valid_at=20,
    ).lifecycle == "aborted"
    assert obligations.read(
        scope=staging_request.scope,
        obligation_id="O1",
        valid_at=20,
    ).status == "open"


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        ("godot", "preload_failed"),
        ("esm", "world_precondition_failed"),
    ],
)
def test_godot_or_esm_refusal_aborts_before_activation(
    stager: SimingStoryNodeStaging,
    staging_request: StagingRequest,
    source: str,
    reason: str,
) -> None:
    acks = [_ack("godot", True), _ack("character", True), _ack("esm", True)]
    acks[[ack.source for ack in acks].index(source)] = _ack(source, False, reason)

    result = stager.complete(staging_request, acks=acks)

    assert result.status == "aborted_before_activation"
    assert result.reason == reason


@pytest.mark.parametrize(
    ("acks", "reason"),
    [
        ([_ack("godot", True), _ack("character", True)], "missing_staging_ack"),
        (
            [_ack("godot", True, correlation_id="corr:wrong"), _ack("character", True), _ack("esm", True)],
            "staging_ack_correlation_mismatch",
        ),
        (
            [_ack("godot", True), _ack("godot", True), _ack("character", True), _ack("esm", True)],
            "duplicate_staging_ack",
        ),
    ],
)
def test_incomplete_or_invalid_acknowledgements_abort_before_activation(
    stager: SimingStoryNodeStaging,
    staging_request: StagingRequest,
    acks: list[StagingAck],
    reason: str,
) -> None:
    result = stager.complete(staging_request, acks=acks)

    assert result.status == "aborted_before_activation"
    assert result.reason == reason


def test_player_divergence_cancels_staged_node(
    stager: SimingStoryNodeStaging,
    staging_request: StagingRequest,
) -> None:
    stager.complete(
        staging_request,
        acks=[_ack("godot", True), _ack("character", True), _ack("esm", True)],
    )

    result = stager.cancel(
        scope=staging_request.scope,
        node_id=staging_request.node_id,
        reason="player_diverged",
        correlation_id="corr:2",
        recorded_at=21,
    )

    assert result.status == "cancelled"
    assert result.story_node_lifecycle == "aborted"
    assert result.obligation_status == "open"


def test_replaying_same_acknowledgements_is_idempotent(
    stager: SimingStoryNodeStaging,
    graph: InMemoryHeavenlyGraphAdapter,
    staging_request: StagingRequest,
) -> None:
    acks = [_ack("godot", True), _ack("character", True), _ack("esm", True)]

    first = stager.complete(staging_request, acks=acks)
    second = stager.complete(staging_request, acks=acks)

    assert second == first
    assert graph.get_node(
        node_id=staging_request.node_id,
        scope=staging_request.scope,
        valid_at=20,
    ).revision == 4


def test_correlation_cannot_replay_a_different_open_obligation(
    stager: SimingStoryNodeStaging,
    obligations: SimingStoryObligationRuntime,
    staging_request: StagingRequest,
) -> None:
    stager.complete(
        staging_request,
        acks=[_ack("godot", True), _ack("character", True), _ack("esm", True)],
    )
    obligations.seed(
        scope=staging_request.scope,
        obligation=NarrativeObligation(
            obligation_id="O2",
            description="The player must learn who sent the letter.",
            status="open",
            pressure=0.6,
            source_fact_refs=["fact:letter:sender_unknown"],
        ),
        provenance=_provenance("story:O2"),
        recorded_at=20,
    )

    with pytest.raises(StoryNodeStagingError, match="reused"):
        stager.complete(
            staging_request.model_copy(update={"obligation_id": "O2"}),
            acks=[_ack("godot", True), _ack("character", True), _ack("esm", True)],
        )


def test_missing_obligation_does_not_stage_a_partial_node(
    stager: SimingStoryNodeStaging,
    story: SimingStoryGraphRuntime,
    memory: SimingHeavenlyMemoryService,
    staging_request: StagingRequest,
) -> None:
    missing_obligation = staging_request.model_copy(
        update={"obligation_id": "O_missing"}
    )

    with pytest.raises(StoryNodeStagingError, match="obligation"):
        stager.complete(
            missing_obligation,
            acks=[_ack("godot", True), _ack("character", True), _ack("esm", True)],
        )

    assert story.read_runtime_node(
        scope=staging_request.scope,
        node_id=staging_request.node_id,
        valid_at=20,
    ).lifecycle == "selected"
    assert memory.get_entry(
        scope=staging_request.scope,
        entry_id="story_staging:runtime:N1:main:corr:1",
        valid_at=20,
    ) is None


def test_staging_write_failure_does_not_commit_a_partial_node() -> None:
    graph = _RejectingStagingGraph()
    memory = SimingHeavenlyMemoryService(graph)
    story = SimingStoryGraphRuntime(graph, memory)
    obligations = SimingStoryObligationRuntime(graph, memory)
    stager = SimingStoryNodeStaging(story, memory, obligations)
    scope = _scope()
    story.seed_blueprint(
        scope=scope,
        blueprint=StoryNodeBlueprint(blueprint_id="N1", title="Letter confrontation"),
        provenance=_provenance("author:story:N1"),
        recorded_at=10,
    )
    story.instantiate(
        scope=scope,
        blueprint_id="N1",
        node_id="runtime:N1:main",
        causal_basis_refs=[],
        recorded_at=10,
    )
    story.transition(
        scope=scope,
        node_id="runtime:N1:main",
        expected="latent",
        target="eligible",
        reason="facts_confirmed",
        recorded_at=11,
    )
    story.transition(
        scope=scope,
        node_id="runtime:N1:main",
        expected="eligible",
        target="selected",
        reason="hard_gates_passed",
        recorded_at=12,
    )
    obligations.seed(
        scope=scope,
        obligation=NarrativeObligation(
            obligation_id="O1",
            description="The letter must have consequences.",
            status="open",
            pressure=0.8,
            source_fact_refs=["fact:letter:discovered"],
        ),
        provenance=_provenance("story:O1"),
        recorded_at=10,
    )
    request = StagingRequest(
        scope=scope,
        node_id="runtime:N1:main",
        correlation_id="corr:1",
        obligation_id="O1",
        recorded_at=20,
        resource_match=_resource_match(),
    )

    with pytest.raises(RuntimeError, match="staging write failed"):
        stager.complete(
            request,
            acks=[_ack("godot", True), _ack("character", True), _ack("esm", True)],
        )

    assert story.read_runtime_node(
        scope=scope,
        node_id="runtime:N1:main",
        valid_at=20,
    ).lifecycle == "selected"
    assert memory.get_entry(
        scope=scope,
        entry_id="story_staging:runtime:N1:main:corr:1",
        valid_at=20,
    ) is None


def test_correlation_cannot_replay_a_different_recorded_time(
    stager: SimingStoryNodeStaging,
    staging_request: StagingRequest,
) -> None:
    stager.complete(
        staging_request,
        acks=[_ack("godot", True), _ack("character", True), _ack("esm", True)],
    )

    with pytest.raises(StoryNodeStagingError, match="reused"):
        stager.complete(
            staging_request.model_copy(update={"recorded_at": 21}),
            acks=[_ack("godot", True), _ack("character", True), _ack("esm", True)],
        )
