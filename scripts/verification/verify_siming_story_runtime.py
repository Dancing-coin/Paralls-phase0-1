from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.models.siming_heavenly_graph import GraphProvenance, HeavenlyGraphScope
from app.models.siming_story_graph import (
    AuthorityStoryOutcome,
    NarrativeAttractor,
    NarrativeObligation,
    StoryNodeBlueprint,
    StoryOutcomeEffect,
    StoryOutcomePort,
)
from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService
from app.services.siming_story_graph_runtime import (
    SimingStoryGraphRuntime,
    StoryNodeTransitionError,
)
from app.services.siming_story_obligation_runtime import SimingStoryObligationRuntime
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter
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


def _prepare_story(runtime: SimingStoryGraphRuntime, scope: HeavenlyGraphScope) -> None:
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


def main() -> int:
    project_root = repo_root()
    log_dir = verification_dir(project_root)
    scope = _scope()
    with tempfile.TemporaryDirectory(dir=log_dir) as temporary_directory:
        database_path = Path(temporary_directory) / "siming-story.sqlite3"
        graph = SQLiteHeavenlyGraphAdapter(database_path)
        memory = SimingHeavenlyMemoryService(graph)
        story = SimingStoryGraphRuntime(graph, memory)
        obligations = SimingStoryObligationRuntime(graph, memory)
        _prepare_story(story, scope)
        outcome = _outcome()
        story.apply_authority_outcome(scope=scope, outcome=outcome)
        obligations.seed(
            scope=scope,
            obligation=NarrativeObligation(
                obligation_id="O2",
                description="The time contradiction must have consequences.",
                status="open",
                pressure=0.8,
                source_fact_refs=["fact:time:contradiction"],
            ),
            provenance=_provenance("O2"),
            recorded_at=10,
        )
        obligations.transform(
            scope=scope,
            source_obligation_id="O2",
            replacement=NarrativeObligation(
                obligation_id="O6",
                description="The player cover-up must have consequences.",
                status="open",
                pressure=0.7,
                source_fact_refs=[outcome.authority_result_ref],
            ),
            authority_result_ref=outcome.authority_result_ref,
            correlation_id=outcome.correlation_id,
            recorded_at=101,
        )
        obligations.seed_attractor(
            scope=scope,
            attractor=NarrativeAttractor(
                attractor_id="A1",
                description="Reach a consequence for the destroyed evidence.",
                forbidden_terminal_node_refs=["runtime:N4:main"],
            ),
            provenance=_provenance("A1"),
            recorded_at=100,
        )
        initially_blocked = (
            obligations.evaluate_attractor(scope=scope, attractor_id="A1", valid_at=101).reachability
            == "blocked"
        )
        story.instantiate(
            scope=scope,
            blueprint_id="N4",
            node_id="runtime:N4:aftermath",
            causal_basis_refs=["fact:new:consequence"],
            recorded_at=102,
        )
        recomputed_reachable = (
            obligations.evaluate_attractor(scope=scope, attractor_id="A1", valid_at=103).reachability
            == "reachable"
        )
        graph.close()

        reopened_graph = SQLiteHeavenlyGraphAdapter(database_path)
        reopened_memory = SimingHeavenlyMemoryService(reopened_graph)
        reopened_story = SimingStoryGraphRuntime(reopened_graph, reopened_memory)
        reopened_obligations = SimingStoryObligationRuntime(reopened_graph, reopened_memory)
        try:
            blueprint_n3 = reopened_story.read_blueprint(
                scope=scope,
                blueprint_id="N3",
                valid_at=104,
            )
            n3 = reopened_story.read_runtime_node(
                scope=scope,
                node_id="runtime:N3:main",
                valid_at=104,
            )
            n4 = reopened_story.read_runtime_node(
                scope=scope,
                node_id="runtime:N4:main",
                valid_at=104,
            )
            n5 = reopened_story.read_runtime_node(
                scope=scope,
                node_id="runtime:N5:main",
                valid_at=104,
            )
            o2 = reopened_obligations.read(scope=scope, obligation_id="O2", valid_at=104)
            o6 = reopened_obligations.read(scope=scope, obligation_id="O6", valid_at=104)
            attractor = reopened_obligations.read_attractor(
                scope=scope,
                attractor_id="A1",
                valid_at=104,
            )
            try:
                reopened_story.transition(
                    scope=scope,
                    node_id="runtime:N4:main",
                    expected="aborted",
                    target="cooldown",
                    reason="retry",
                    recorded_at=104,
                )
            except StoryNodeTransitionError:
                no_resurrection = True
            else:
                no_resurrection = False
        finally:
            reopened_graph.close()

    trace = {
        "blueprint_n3": None if blueprint_n3 is None else blueprint_n3.model_dump(mode="json"),
        "n3": None if n3 is None else n3.model_dump(mode="json"),
        "n4": None if n4 is None else n4.model_dump(mode="json"),
        "n5": None if n5 is None else n5.model_dump(mode="json"),
        "o2": None if o2 is None else o2.model_dump(mode="json"),
        "o6": None if o6 is None else o6.model_dump(mode="json"),
        "attractor": None if attractor is None else attractor.model_dump(mode="json"),
        "initially_blocked": initially_blocked,
        "recomputed_reachable": recomputed_reachable,
        "no_resurrection": no_resurrection,
    }
    trace_path = log_dir / "siming-story-runtime-trace.json"
    write_json(trace_path, trace)
    results = [
        _result(
            "authored_runtime_separation",
            "Authored blueprint remains distinct from runtime node state",
            blueprint_n3 is not None
            and n3 is not None
            and blueprint_n3.blueprint_id == n3.blueprint_id
            and blueprint_n3.title == "Repair record opportunity",
            [str(trace_path)],
        ),
        _result(
            "n3_divergence_resolved",
            "N3 resolves through the Authority-confirmed divergence port",
            n3 is not None
            and n3.lifecycle == "resolved"
            and n3.outcome_port == "player_destroyed_evidence"
            and n3.outcome_semantic == "resolved_with_divergence",
            [str(trace_path)],
        ),
        _result(
            "n4_terminal_closed",
            "N4 is permanently closed by player choice",
            n4 is not None
            and n4.lifecycle == "aborted"
            and n4.closure_reason == "closed_by_player_choice"
            and n4.terminal
            and n4.reopen_policy == "never",
            [str(trace_path)],
        ),
        _result(
            "n5_unreachable",
            "N5 is unreachable by the resulting ledger",
            n5 is not None and n5.reachability == "unreachable_by_ledger",
            [str(trace_path)],
        ),
        _result(
            "o2_transformed_to_o6",
            "O2 becomes transformed while O6 remains open",
            o2 is not None
            and o2.status == "transformed"
            and o2.transformed_to_refs == ["O6"]
            and o6 is not None
            and o6.status == "open",
            [str(trace_path)],
        ),
        _result(
            "no_resurrection",
            "Terminal N4 cannot be reactivated after SQLite restart",
            no_resurrection,
            [str(trace_path)],
        ),
        _result(
            "attractor_recomputed",
            "A fresh-causal-basis N4 instance restores an alternate attractor route",
            initially_blocked and recomputed_reachable and attractor is not None and attractor.reachability == "reachable",
            [str(trace_path)],
        ),
    ]
    overall = all(result["status"] == "proved" for result in results)
    report = {
        "overall_siming_story_runtime_passed": overall,
        "results": results,
        "artifacts": {"trace": str(trace_path)},
    }
    json_path = log_dir / "siming-story-runtime-report.json"
    markdown_path = log_dir / "siming-story-runtime-report.md"
    write_json(json_path, report)
    write_markdown(
        markdown_path,
        "Siming Story Runtime Verification Report",
        report,
        "overall_siming_story_runtime_passed",
    )
    print(f"siming_story_runtime_report_json={json_path}")
    print(f"siming_story_runtime_report_md={markdown_path}")
    print(f"overall_siming_story_runtime_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
