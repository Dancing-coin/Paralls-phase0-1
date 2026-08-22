from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.storage.graph_memory_store import CharacterGraphMemoryStore
from app.character_agent.storage.memory_store import CharacterAgentMemoryStore
from app.character_agent.storage.memory_store_router import CharacterMemoryStoreRouter
from app.models.siming_actor_memory_read import ActorMemoryReadRequest
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
from common import repo_root, verification_dir, write_json, write_markdown


def _result(
    result_id: str, title: str, proved: bool, trace_path: Path
) -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": [str(trace_path)] if proved else [],
    }


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
        producer_system="verify_siming_adaptive_bridge",
    )


def _proposal(
    proposal_id: str = "proposal:private-confrontation:1",
) -> AdaptiveBridgeNodeProposal:
    return AdaptiveBridgeNodeProposal.model_validate(
        {
            "proposal_id": proposal_id,
            "pattern": "private_confrontation",
            "correlation_id": "corr:destroy:1",
            "causal_gap_ref": "fact:letter:destroyed",
            "title": "Private confrontation after the letter is destroyed",
            "target_actor_id": "char_b",
            "supporting_fact_refs": ["fact:letter:destroyed"],
            "required_actor_memory_refs": [
                "observation:char_b:authority:letter:destroyed"
            ],
            "obligation_refs": ["O6"],
            "attractor_refs": [],
            "realization_request": {
                "node_id": f"runtime:bridge:{proposal_id}",
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


def _actor_gateway(graph: InMemoryHeavenlyGraphAdapter) -> ActorMemoryReadGateway:
    router = CharacterMemoryStoreRouter(
        light_store=CharacterAgentMemoryStore(),
        graph_store=CharacterGraphMemoryStore(graph, scope_resolver=_actor_scope),
        heavy_actor_ids=frozenset({"char_b"}),
    )
    router.write_event(
        {
            "event_id": "authority:letter:destroyed",
            "event_index": 100,
            "actor_id": "char_b",
            "event_type": "character_perceived_event",
            "producer_ts": 100,
            "payload": {
                "summary": "the letter was destroyed",
                "target_actor_id": "obj_letter",
                "percept_channel": "visual",
            },
        }
    )
    return ActorMemoryReadGateway(CharacterAgentRuntime(memory_store=router))


def _node_ids(
    graph: InMemoryHeavenlyGraphAdapter,
    scope: HeavenlyGraphScope,
) -> list[str]:
    return sorted(
        node.node_id
        for node in graph.query_nodes(
            HeavenlyNodeQuery(scope=scope, valid_at=100, limit=None)
        )
    )


def _seed_terminal_node(
    graph: InMemoryHeavenlyGraphAdapter,
    scope: HeavenlyGraphScope,
) -> str:
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
            transaction_id=node.node_id,
            idempotency_key=node.node_id,
            scope=scope,
            nodes=[
                HeavenlyGraphNode(
                    node_id=node.node_id,
                    node_type="runtime_story_node",
                    scope=scope,
                    validity=GraphValidity(valid_from=100),
                    recorded_at=100,
                    revision=1,
                    provenance=_provenance(node.node_id),
                    attributes=node.model_dump(mode="json"),
                )
            ],
        )
    )
    return node.node_id


def main() -> int:
    project_root = repo_root()
    log_dir = verification_dir(project_root)
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
        recorded_at=100,
        revision=1,
        supersedes_revision=None,
        provenance=_provenance(fact.authority_result_ref),
        transaction_id="tx:letter:destroyed",
        idempotency_key=fact.entry_id,
    )
    context = SimingContextCompiler(graph).compile(
        SimingContextRequest(
            scope=scope,
            valid_at=100,
            recorded_at=100,
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
            status="open",
            pressure=0.5,
            source_fact_refs=[fact.entry_id],
        ),
        provenance=_provenance("obligation:O6"),
        recorded_at=100,
    )
    resources = ResourceCapabilityRegistry()
    gateway = _actor_gateway(graph)
    bridge = SimingAdaptiveBridge(
        graph=graph,
        compiled_context=context,
        story_runtime=story,
        obligations=obligations,
        resources=resources,
        actor_memory_gateway=gateway,
        actor_autonomy=lambda _: True,
    )
    audit = SimingLlmProposalAudit(
        provider="fake_deterministic_provider",
        route_id="verify:adaptive-bridge",
        model="fake-typed-proposal",
        request_id="request:destroy:1",
        correlation_id="corr:destroy:1",
        latency_ms=0,
        response_artifact_hash="0" * 64,
    )
    proposal = _proposal()
    terminal_node_id = _seed_terminal_node(graph, scope)
    actor_scope = _actor_scope("char_b")
    private_node_ids_before = _node_ids(graph, actor_scope)

    accepted = bridge.validate_and_commit(proposal, provider_audit=audit)
    missing_fact = bridge.validate_and_commit(
        proposal.model_copy(
            update={
                "proposal_id": "proposal:missing-fact:1",
                "supporting_fact_refs": ["fact:missing"],
            }
        ),
        provider_audit=audit,
    )
    terminal_reuse = bridge.validate_and_commit(
        proposal.model_copy(
            update={
                "proposal_id": "proposal:terminal-reuse:1",
                "causal_gap_ref": terminal_node_id,
            }
        ),
        provider_audit=audit,
    )
    private_node_ids_after = _node_ids(graph, actor_scope)
    actor_memory = gateway.read(
        ActorMemoryReadRequest(
            actor_id="char_b", story_branch_id=scope.story_branch_id, valid_at=100
        )
    )
    runtime_node = story.read_runtime_node(
        scope=scope,
        node_id=accepted.runtime_node_ref or "",
        valid_at=100,
    )
    terminal_node = story.read_runtime_node(
        scope=scope, node_id=terminal_node_id, valid_at=100
    )
    obligation = obligations.read(scope=scope, obligation_id="O6", valid_at=100)
    resource_match = resources.match(proposal.realization_request, world_ts=100)
    event_refs = {
        record.source_event_id for record in actor_memory.bundle.event_memories
    }
    observation_refs = {
        record.source_event_id for record in actor_memory.bundle.observation_memories
    }
    trace = {
        "proposal_type": type(proposal).__name__,
        "accepted_validation": accepted.model_dump(mode="json"),
        "missing_fact_validation": missing_fact.model_dump(mode="json"),
        "terminal_reuse_validation": terminal_reuse.model_dump(mode="json"),
        "runtime_node": None
        if runtime_node is None
        else runtime_node.model_dump(mode="json"),
        "terminal_node": None
        if terminal_node is None
        else terminal_node.model_dump(mode="json"),
        "o6_status": None if obligation is None else obligation.status,
        "resource_match": resource_match.model_dump(mode="json"),
        "char_b_memory_completeness": actor_memory.completeness,
        "char_b_event_refs": sorted(event_refs),
        "char_b_observation_refs": sorted(observation_refs),
        "char_b_private_node_ids_before": private_node_ids_before,
        "char_b_private_node_ids_after": private_node_ids_after,
    }
    trace_path = log_dir / "siming-adaptive-bridge-trace.json"
    write_json(trace_path, trace)
    observed_destruction = "authority:letter:destroyed" in event_refs.intersection(
        observation_refs
    )
    results = [
        _result(
            "typed_proposal",
            "The fake provider input is parsed as a strict typed bridge proposal",
            isinstance(proposal, AdaptiveBridgeNodeProposal),
            trace_path,
        ),
        _result(
            "existing_fact_only",
            "Bridge proposals use compiled facts and reject a missing fact reference",
            set(proposal.supporting_fact_refs).issubset(
                {entry.entry_id for entry in context.world_facts}
            )
            and "supporting_fact_missing" in missing_fact.reason_codes,
            trace_path,
        ),
        _result(
            "char_b_observation_gate",
            "char_b's complete Event and Observation pools prove the destruction was observed",
            actor_memory.completeness == "complete" and observed_destruction,
            trace_path,
        ),
        _result(
            "open_o6_gate",
            "The selected bridge is grounded in an open O6 obligation",
            obligation is not None and obligation.status == "open",
            trace_path,
        ),
        _result(
            "resource_gate",
            "The existing capability registry accepts the requested realization",
            resource_match.accepted,
            trace_path,
        ),
        _result(
            "no_terminal_resurrection",
            "A terminal branch is still terminal and a reuse attempt is rejected",
            terminal_node is not None
            and terminal_node.terminal
            and "terminal_node_resurrection" in terminal_reuse.reason_codes,
            trace_path,
        ),
        _result(
            "no_actor_memory_write",
            "Bridge validation does not mutate char_b's actor-private graph memory",
            private_node_ids_before == private_node_ids_after,
            trace_path,
        ),
        _result(
            "new_runtime_node_committed",
            "An accepted proposal creates one latent runtime bridge node",
            accepted.accepted
            and accepted.runtime_node_ref
            == "runtime:bridge:proposal:private-confrontation:1"
            and runtime_node is not None
            and runtime_node.lifecycle == "latent",
            trace_path,
        ),
    ]
    overall = all(result["status"] == "proved" for result in results)
    report = {
        "overall_siming_adaptive_bridge_passed": overall,
        "results": results,
        "artifacts": {"trace": str(trace_path)},
    }
    report_path = log_dir / "siming-adaptive-bridge-report.json"
    markdown_path = log_dir / "siming-adaptive-bridge-report.md"
    write_json(report_path, report)
    write_markdown(
        markdown_path,
        "Siming Adaptive Bridge Verification Report",
        report,
        "overall_siming_adaptive_bridge_passed",
    )
    print(f"siming_adaptive_bridge_report_json={report_path}")
    print(f"siming_adaptive_bridge_report_md={markdown_path}")
    print(f"overall_siming_adaptive_bridge_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
