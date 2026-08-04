from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.models.siming_heavenly_graph import GraphProvenance, HeavenlyGraphScope
from app.models.siming_resource_capability import (
    ResourceMatch,
    ResourceRealizationRequest,
    StagingAck,
    StagingRequest,
)
from app.models.siming_story_graph import (
    NarrativeObligation,
    StoryDecisionCandidate,
    StoryNodeBlueprint,
)
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService
from app.services.siming_resource_capability_registry import ResourceCapabilityRegistry
from app.services.siming_story_graph_runtime import SimingStoryGraphRuntime
from app.services.siming_story_node_orchestrator import StoryNodeOrchestrator
from app.services.siming_story_node_staging import SimingStoryNodeStaging
from app.services.siming_story_obligation_runtime import SimingStoryObligationRuntime
from common import repo_root, verification_dir, write_json, write_markdown


def _result(result_id: str, title: str, proved: bool, evidence: list[str]) -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
    }


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
        correlation_id="corr:resource-staging",
        producer_system="verify_siming_resource_staging",
    )


def _request(semantic_purpose: str) -> ResourceRealizationRequest:
    return ResourceRealizationRequest(
        node_id="runtime:letter:consequence",
        actor_bindings={"speaker": "char_b", "listener": "char_c"},
        target_object_id="obj_letter",
        target_environment_id="env_lamp",
        required_realization_keys=["look_at_target", "focus_attention"],
        camera_pattern="two_actor_confrontation",
        semantic_purpose=semantic_purpose,
        location_state="throne_room:letter_removed",
    )


def _candidate(candidate_id: str, *, confirmed_fact: bool, resource_score: float) -> StoryDecisionCandidate:
    return StoryDecisionCandidate(
        candidate_id=candidate_id,
        runtime_node_ref=f"runtime:{candidate_id}",
        confirmed_fact=confirmed_fact,
        player_choice=True,
        actor_autonomy=True,
        world_feasibility=True,
        safety=True,
        playability_fairness=True,
        open_obligation=True,
        reachable_attractor=True,
        narrative_score=0.5,
        resource_score=resource_score,
    )


def _stager() -> tuple[SimingStoryNodeStaging, SimingStoryGraphRuntime, SimingStoryObligationRuntime]:
    scope = _scope()
    graph = InMemoryHeavenlyGraphAdapter()
    memory = SimingHeavenlyMemoryService(graph)
    story = SimingStoryGraphRuntime(graph, memory)
    obligations = SimingStoryObligationRuntime(graph, memory)
    story.seed_blueprint(
        scope=scope,
        blueprint=StoryNodeBlueprint(blueprint_id="N1", title="Letter consequence"),
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
            description="The letter discovery must have consequences.",
            status="open",
            pressure=0.8,
            source_fact_refs=["fact:letter:discovered"],
        ),
        provenance=_provenance("story:O1"),
        recorded_at=10,
    )
    return SimingStoryNodeStaging(story, memory, obligations), story, obligations


def _staging_request(correlation_id: str, resource_match: ResourceMatch) -> StagingRequest:
    return StagingRequest(
        scope=_scope(),
        node_id="runtime:N1:main",
        correlation_id=correlation_id,
        obligation_id="O1",
        recorded_at=20,
        resource_match=resource_match,
    )


def _acks(correlation_id: str, *, character_accepted: bool = True) -> list[StagingAck]:
    return [
        StagingAck(source="godot", correlation_id=correlation_id, accepted=True),
        StagingAck(
            source="character",
            correlation_id=correlation_id,
            accepted=character_accepted,
            reason="actor_refused" if not character_accepted else "",
        ),
        StagingAck(source="esm", correlation_id=correlation_id, accepted=True),
    ]


def _static_resources(project_root: Path) -> dict[str, bool]:
    required_sources = {
        "main_demo_scene": ("scenes/phase0/MainDemo.tscn", ("CharacterB", 'actor_id = "char_b"')),
        "letter_object": ("scripts/object/InteractiveObject.gd", ('object_id := "obj_letter"',)),
        "lamp_environment": ("scripts/environment/EnvironmentStateController.gd", ('environment_id := "env_lamp"',)),
        "realization_keys": ("backend/app/character_agent/skills/catalog.py", ('"look_at_target"', '"focus_attention"')),
        "character_assets": ("scripts/character/CharacterEmbodimentAssetRegistry.gd", ("preload_assets_for_semantics",)),
    }
    return {
        name: (path := project_root / relative_path).is_file()
        and all(token in path.read_text(encoding="utf-8") for token in tokens)
        for name, (relative_path, tokens) in required_sources.items()
    }


def main() -> int:
    project_root = repo_root()
    log_dir = verification_dir(project_root)
    static_resources = _static_resources(project_root)

    registry = ResourceCapabilityRegistry()
    reveal_request = _request("evidence_reveal")
    confrontation_request = _request("private_confrontation")
    reveal_match = registry.match(reveal_request, world_ts=20)
    confrontation_match = registry.match(confrontation_request, world_ts=20)
    registry.record_realization(reveal_request, "main_demo_throne_room", world_ts=19)
    repeated_reveal = registry.match(reveal_request, world_ts=20)
    distinct_confrontation = registry.match(confrontation_request, world_ts=20)

    ranking = StoryNodeOrchestrator().rank(
        [
            _candidate("reusable_but_false", confirmed_fact=False, resource_score=1.0),
            _candidate("fact_confirmed", confirmed_fact=True, resource_score=0.0),
        ]
    )

    stager, staged_story, _ = _stager()
    staged_request = _staging_request("corr:staged", confrontation_match)
    staged = stager.complete(staged_request, acks=_acks("corr:staged"))
    staged_node = staged_story.read_runtime_node(
        scope=staged_request.scope,
        node_id=staged_request.node_id,
        valid_at=20,
    )

    stager, refused_story, refused_obligations = _stager()
    refused_request = _staging_request("corr:refused", confrontation_match)
    refused = stager.complete(
        refused_request,
        acks=_acks("corr:refused", character_accepted=False),
    )
    refused_node = refused_story.read_runtime_node(
        scope=refused_request.scope,
        node_id=refused_request.node_id,
        valid_at=20,
    )
    open_obligation = refused_obligations.read(
        scope=refused_request.scope,
        obligation_id=refused_request.obligation_id,
        valid_at=20,
    )

    trace = {
        "static_resources": static_resources,
        "reveal_match": reveal_match.model_dump(mode="json"),
        "confrontation_match": confrontation_match.model_dump(mode="json"),
        "repeated_reveal": repeated_reveal.model_dump(mode="json"),
        "distinct_confrontation": distinct_confrontation.model_dump(mode="json"),
        "ranking": ranking.model_dump(mode="json"),
        "staged": staged.model_dump(mode="json"),
        "staged_lifecycle": None if staged_node is None else staged_node.lifecycle,
        "refused": refused.model_dump(mode="json"),
        "refused_lifecycle": None if refused_node is None else refused_node.lifecycle,
        "refused_obligation": None if open_obligation is None else open_obligation.status,
    }
    trace_path = log_dir / "siming-resource-staging-trace.json"
    write_json(trace_path, trace)

    capability = confrontation_match.capability
    results = [
        _result(
            "existing_resource_package",
            "The existing MainDemo resource package covers the requested realization",
            all(static_resources.values())
            and confrontation_match.accepted
            and capability is not None
            and capability.asset_bundle == "main_demo_throne_room"
            and capability.scene_refs == ["scenes/phase0/MainDemo.tscn"],
            [str(trace_path)],
        ),
        _result(
            "hard_gate_precedes_resource_score",
            "A high-reuse candidate cannot bypass the hard fact gate",
            [item.candidate_id for item in ranking.eligible] == ["fact_confirmed"]
            and len(ranking.rejected) == 1
            and ranking.rejected[0].reason == "fact_gate_failed",
            [str(trace_path)],
        ),
        _result(
            "semantic_reuse",
            "One loaded resource package supports distinct authored semantic purposes",
            reveal_match.accepted
            and confrontation_match.accepted
            and reveal_match.capability is not None
            and confrontation_match.capability is not None
            and reveal_match.capability.asset_bundle == confrontation_match.capability.asset_bundle
            and reveal_match.realization_signature != confrontation_match.realization_signature,
            [str(trace_path)],
        ),
        _result(
            "exact_signature_fatigue",
            "Fatigue penalizes only an exact recent realization signature",
            repeated_reveal.fatigue_penalty > 0
            and distinct_confrontation.fatigue_penalty == 0,
            [str(trace_path)],
        ),
        _result(
            "all_ack_staged",
            "Godot, Character, and ESM acknowledgements stage the selected node",
            staged.status == "staged"
            and staged_node is not None
            and staged_node.lifecycle == "staged",
            [str(trace_path)],
        ),
        _result(
            "refusal_aborted",
            "A Character refusal aborts the selected node before activation",
            refused.status == "aborted_before_activation"
            and refused.reason == "actor_refused"
            and refused_node is not None
            and refused_node.lifecycle == "aborted",
            [str(trace_path)],
        ),
        _result(
            "obligation_remains_open",
            "A pre-activation refusal does not falsely fulfill the obligation",
            refused.obligation_status == "open"
            and open_obligation is not None
            and open_obligation.status == "open",
            [str(trace_path)],
        ),
    ]
    overall = all(result["status"] == "proved" for result in results)
    report = {
        "overall_siming_resource_staging_passed": overall,
        "results": results,
        "artifacts": {"trace": str(trace_path)},
    }
    json_path = log_dir / "siming-resource-staging-report.json"
    markdown_path = log_dir / "siming-resource-staging-report.md"
    write_json(json_path, report)
    write_markdown(
        markdown_path,
        "Siming Resource Staging Verification Report",
        report,
        "overall_siming_resource_staging_passed",
    )
    print(f"siming_resource_staging_report_json={json_path}")
    print(f"siming_resource_staging_report_md={markdown_path}")
    print(f"overall_siming_resource_staging_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
