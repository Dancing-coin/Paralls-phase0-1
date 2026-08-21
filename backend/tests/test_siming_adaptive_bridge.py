from dataclasses import dataclass

import pytest

from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.storage.graph_memory_store import CharacterGraphMemoryStore
from app.character_agent.storage.memory_store import CharacterAgentMemoryStore
from app.character_agent.storage.memory_store_router import CharacterMemoryStoreRouter
from app.models.siming_actor_memory_read import (
    ActorMemoryReadResult,
    ActorMemoryRevisionVector,
)
from app.models.siming_adaptive_bridge import (
    AdaptiveBridgeNodeProposal,
    SimingLlmProposalAudit,
)
from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
    HeavenlyNodeQuery,
)
from app.models.siming_heavenly_memory import (
    SimingContextRequest,
    WorldFactMemoryEntry,
)
from app.models.siming_story_graph import NarrativeObligation, RuntimeStoryNode
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.siming_actor_memory_gateway import ActorMemoryReadGateway
from app.services.siming_adaptive_bridge import SimingAdaptiveBridge
from app.services.siming_context_compiler import SimingContextCompiler
from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService
from app.services.siming_resource_capability_registry import ResourceCapabilityRegistry
from app.services.siming_story_graph_runtime import SimingStoryGraphRuntime
from app.services.siming_story_obligation_runtime import SimingStoryObligationRuntime


def _scope() -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:demo",
        session_id="session:demo",
        story_branch_id="branch:main",
        room_id="room:throne",
        scene_id="scene:throne",
    )


def _actor_scope(actor_id: str) -> HeavenlyGraphScope:
    return _scope().model_copy(
        update={"graph_namespace": "actor_private", "owner_actor_id": actor_id}
    )


def _provenance(source_ref: str) -> GraphProvenance:
    return GraphProvenance(
        source_kind="authority_event",
        source_ref=source_ref,
        causation_id=source_ref,
        correlation_id="corr:destroy:1",
        producer_system="system_l6",
    )


def _proposal() -> AdaptiveBridgeNodeProposal:
    return AdaptiveBridgeNodeProposal.model_validate(
        {
            "proposal_id": "proposal:private-confrontation:1",
            "pattern": "private_confrontation",
            "correlation_id": "corr:destroy:1",
            "causal_gap_ref": "fact:letter:destroyed",
            "title": "Private confrontation after the letter is destroyed",
            "target_actor_id": "char_b",
            "supporting_fact_refs": ["fact:letter:destroyed"],
            "required_actor_memory_refs": ["observation:char_b:authority:letter:destroyed"],
            "obligation_refs": ["O6"],
            "attractor_refs": [],
            "realization_request": {
                "node_id": "runtime:bridge:proposal:private-confrontation:1",
                "actor_bindings": {"speaker": "char_b", "listener": "char_c"},
                "target_object_id": "obj_letter",
                "target_environment_id": "env_lamp",
                "required_realization_keys": ["look_at_target", "focus_attention"],
                "camera_pattern": "two_actor_confrontation",
                "semantic_purpose": "private_confrontation",
                "location_state": "throne_room:letter_removed",
            },
            "autonomy_reason": "char_b chooses to confront the player",
        }
    )


def _audit() -> SimingLlmProposalAudit:
    return SimingLlmProposalAudit(
        provider="openai_responses",
        route_id="route-live",
        model="model-live",
        request_id="request-live",
        correlation_id="corr:destroy:1",
        latency_ms=12,
        response_artifact_hash="a" * 64,
    )


class _IncompleteGateway:
    def read(self, request: object) -> ActorMemoryReadResult:
        return ActorMemoryReadResult(
            actor_id="char_b",
            story_branch_id="branch:main",
            valid_at=100,
            revision_vector=ActorMemoryRevisionVector(),
            completeness="memory_surface_incomplete",
            reason="revision_vector_mismatch",
            bundle=CharacterMemoryRecordBundle(),
        )


def _actor_gateway(
    graph: InMemoryHeavenlyGraphAdapter,
    *,
    observed: bool,
    lineage_only: bool = False,
) -> ActorMemoryReadGateway:
    store = CharacterGraphMemoryStore(graph, scope_resolver=_actor_scope)
    router = CharacterMemoryStoreRouter(
        light_store=CharacterAgentMemoryStore(),
        graph_store=store,
        heavy_actor_ids=frozenset({"char_b"}),
    )
    if observed:
        source_event_id = (
            "char_b:perceived:letter-removal"
            if lineage_only
            else "authority:letter:destroyed"
        )
        router.write_event(
            {
                "event_id": source_event_id,
                "event_index": 100,
                "actor_id": "char_b",
                "event_type": "character_perceived_event",
                "producer_ts": 100,
                "payload": {
                    "summary": "the letter was destroyed",
                    "target_actor_id": "obj_letter",
                    "percept_channel": "visual",
                    "source_ref_lineage": (
                        ["authority:letter:destroyed"] if lineage_only else []
                    ),
                },
            }
        )
    return ActorMemoryReadGateway(CharacterAgentRuntime(memory_store=router))


@dataclass
class _BridgeSetup:
    bridge: SimingAdaptiveBridge
    graph: InMemoryHeavenlyGraphAdapter
    scope: HeavenlyGraphScope


def _bridge_setup(
    *,
    observed: bool = True,
    incomplete_memory: bool = False,
    obligation_status: str = "open",
    resource_available: bool = True,
    actor_autonomy: bool = True,
    recorded_at: int = 100,
    lineage_only: bool = False,
) -> _BridgeSetup:
    graph = InMemoryHeavenlyGraphAdapter()
    scope = _scope()
    memory = SimingHeavenlyMemoryService(graph)
    fact = WorldFactMemoryEntry(
        entry_id="fact:letter:destroyed",
        world_anchor_id="obj_letter",
        state_key="surface_state",
        state_value="removed_from_surface",
        authority_result_ref="authority:letter:destroyed",
    )
    memory.write_entry(
        scope=scope,
        entry=fact,
        validity=GraphValidity(valid_from=100),
        recorded_at=recorded_at,
        revision=1,
        supersedes_revision=None,
        provenance=_provenance(fact.authority_result_ref),
        transaction_id="tx:letter:destroyed",
        idempotency_key="fact:letter:destroyed",
    )
    context = SimingContextCompiler(graph).compile(
        SimingContextRequest(
            scope=scope,
            valid_at=100,
            recorded_at=recorded_at,
            seed_node_ids=[fact.entry_id],
        )
    )
    story = SimingStoryGraphRuntime(graph, memory)
    obligations = SimingStoryObligationRuntime(graph, memory)
    obligations.seed(
        scope=scope,
        obligation=NarrativeObligation(
            obligation_id="O6",
            description="The destruction must have a consequence",
            status=obligation_status,
            pressure=0.5,
            source_fact_refs=[fact.entry_id],
        ),
        provenance=_provenance("obligation:O6"),
        recorded_at=recorded_at,
    )
    resources = ResourceCapabilityRegistry()
    if not resource_available:
        resources.set_cooldown("main_demo_throne_room", until=101)
    gateway = (
        _IncompleteGateway()
        if incomplete_memory
        else _actor_gateway(graph, observed=observed, lineage_only=lineage_only)
    )
    return _BridgeSetup(
        bridge=SimingAdaptiveBridge(
            graph=graph,
            compiled_context=context,
            story_runtime=story,
            obligations=obligations,
            resources=resources,
            actor_memory_gateway=gateway,
            actor_autonomy=lambda _: actor_autonomy,
        ),
        graph=graph,
        scope=scope,
    )


def _seed_terminal_node(
    graph: InMemoryHeavenlyGraphAdapter,
    scope: HeavenlyGraphScope,
) -> None:
    node = RuntimeStoryNode(
        node_id="runtime:terminal:letter",
        blueprint_id="N4",
        lifecycle="aborted",
        closure_reason="closed_by_player_choice",
        terminal=True,
        reopen_policy="never",
    )
    graph.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id="terminal:letter",
            idempotency_key="terminal:letter",
            scope=scope,
            nodes=[
                HeavenlyGraphNode(
                    node_id=node.node_id,
                    node_type="runtime_story_node",
                    scope=scope,
                    validity=GraphValidity(valid_from=100),
                    recorded_at=100,
                    revision=1,
                    provenance=_provenance("terminal:letter"),
                    attributes=node.model_dump(mode="json"),
                )
            ],
        )
    )


def test_private_confrontation_commits_new_node_when_all_gates_pass() -> None:
    setup = _bridge_setup()

    result = setup.bridge.validate_and_commit(_proposal(), provider_audit=_audit())

    assert result.accepted is True
    assert result.runtime_node_ref == "runtime:bridge:proposal:private-confrontation:1"
    assert result.graph_transaction_ref == "story_instantiate:runtime:bridge:proposal:private-confrontation:1"
    assert setup.bridge.story_runtime.read_runtime_node(
        scope=setup.scope,
        node_id=result.runtime_node_ref,
        valid_at=100,
    ).lifecycle == "latent"


def test_private_confrontation_accepts_graph_obligation_reference() -> None:
    setup = _bridge_setup()
    proposal = _proposal().model_copy(update={"obligation_refs": ["obligation:O6"]})

    result = setup.bridge.validate_and_commit(proposal, provider_audit=_audit())

    assert result.accepted is True


def test_private_confrontation_accepts_actor_observation_authority_lineage() -> None:
    setup = _bridge_setup(lineage_only=True)

    result = setup.bridge.validate_and_commit(_proposal(), provider_audit=_audit())

    assert result.accepted is True


@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("missing_fact", "supporting_fact_missing"),
        ("terminal_reuse", "terminal_node_resurrection"),
        ("incomplete_memory", "memory_surface_incomplete"),
        ("no_observation", "actor_did_not_observe"),
        ("closed_obligation", "obligation_not_open"),
        ("missing_resource", "resource_unavailable"),
        ("actor_refusal", "actor_autonomy_rejected"),
    ],
)
def test_bridge_rejection_matrix(case: str, reason: str) -> None:
    setup = _bridge_setup(
        observed=case != "no_observation",
        incomplete_memory=case == "incomplete_memory",
        obligation_status="fulfilled" if case == "closed_obligation" else "open",
        resource_available=case != "missing_resource",
        actor_autonomy=case != "actor_refusal",
    )
    proposal = _proposal()
    if case == "missing_fact":
        proposal = proposal.model_copy(update={"supporting_fact_refs": ["fact:missing"]})
    if case == "terminal_reuse":
        _seed_terminal_node(setup.graph, setup.scope)
        proposal = proposal.model_copy(update={"causal_gap_ref": "runtime:terminal:letter"})

    result = setup.bridge.validate_and_commit(proposal, provider_audit=_audit())

    assert result.accepted is False
    assert reason in result.reason_codes
    assert result.runtime_node_ref is None
    assert result.graph_transaction_ref is None


def test_accepted_bridge_replays_without_a_second_runtime_node() -> None:
    setup = _bridge_setup()

    first = setup.bridge.validate_and_commit(_proposal(), provider_audit=_audit())
    second = setup.bridge.validate_and_commit(_proposal(), provider_audit=_audit())

    assert second == first
    assert len(
        setup.graph.query_nodes(
            HeavenlyNodeQuery(
                scope=setup.scope,
                valid_at=100,
                node_types=["runtime_story_node"],
                limit=None,
            )
        )
    ) == 1


def test_bridge_preserves_zero_context_recorded_time() -> None:
    setup = _bridge_setup(recorded_at=0)

    setup.bridge.validate_and_commit(_proposal(), provider_audit=_audit())

    audit = setup.graph.get_node(
        node_id="adaptive_bridge_audit:proposal:private-confrontation:1",
        scope=setup.scope,
        valid_at=100,
        recorded_at=100,
    )
    assert audit.recorded_at == 0


def test_bridge_records_safe_provider_and_validation_audit() -> None:
    setup = _bridge_setup()

    setup.bridge.validate_and_commit(_proposal(), provider_audit=_audit())

    audit = setup.graph.get_node(
        node_id="adaptive_bridge_audit:proposal:private-confrontation:1",
        scope=setup.scope,
        valid_at=100,
    )
    assert audit.attributes["provider_audit"]["response_artifact_hash"] == "a" * 64
    assert audit.attributes["proposal"]["target_actor_id"] == "char_b"
    assert audit.attributes["validation"]["accepted"] is True
    assert "compiled_context" not in audit.attributes


def test_bridge_leaves_actor_private_memory_unchanged() -> None:
    setup = _bridge_setup()
    actor_scope = _actor_scope("char_b")
    before = setup.graph.query_nodes(
        HeavenlyNodeQuery(scope=actor_scope, valid_at=100, limit=None)
    )

    setup.bridge.validate_and_commit(_proposal(), provider_audit=_audit())

    assert setup.graph.query_nodes(
        HeavenlyNodeQuery(scope=actor_scope, valid_at=100, limit=None)
    ) == before
