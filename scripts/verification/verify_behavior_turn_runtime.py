from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.models.behavior_turn import (
    BEHAVIOR_TURN_STAGE_ORDER,
    BehaviorTurnRecordRequest,
    BehaviorTurnStageRecord,
)
from app.models.character_perceived import CharacterPerceivedEvent
from app.models.siming_heavenly_graph import (
    BehaviorTurnQuery,
    GraphProvenance,
    GraphReaderContext,
    GraphRevisionVector,
    HeavenlyGraphScope,
)
from app.services.behavior_turn_recorder import BehaviorTurnRecorder
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter
from common import (
    repo_root,
    resolve_python_exe,
    run_command,
    verification_dir,
    write_json,
    write_markdown,
)


TEST_FILES = ["backend/tests/test_behavior_turn_recorder.py"]
STAGES = list(BEHAVIOR_TURN_STAGE_ORDER)


def _result(
    result_id: str, title: str, proved: bool, evidence: list[str]
) -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
    }


def _scope(actor_id: str) -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:harness",
        session_id="session:harness",
        story_branch_id="branch:main",
        graph_namespace="actor_private",
        owner_actor_id=actor_id,
    )


def _context(actor_id: str, valid_at: int) -> GraphReaderContext:
    return GraphReaderContext(
        reader_principal=f"reader:{actor_id}",
        allowed_visibility_scopes=("actor_private",),
        world_id="world:harness",
        session_id="session:harness",
        story_branch_id="branch:main",
        valid_at=valid_at,
        recorded_at=valid_at,
        policy_revision="policy:character-runtime:v1",
    )


def _event(timestamp: int, summary: str) -> CharacterPerceivedEvent:
    return CharacterPerceivedEvent(
        actor_id="char_b",
        percept_channel="visual",
        producer_ts=timestamp,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary=summary,
        source_candidate_event_id=f"visual_fact:{timestamp}:char_b",
    )


def _stage_nodes(result: object) -> list[object]:
    return [
        node
        for node in result.nodes
        if node.attributes.get("entity_kind") == "stage"
    ]


def _settlement_outcome(nodes: list[object]) -> str:
    return str(
        next(
            node for node in nodes if node.attributes.get("stage") == "settlement"
        ).attributes["outcome"]
    )


def _replay_request() -> BehaviorTurnRecordRequest:
    return BehaviorTurnRecordRequest(
        turn_id="turn:harness:replay",
        scope=_scope("char_b"),
        valid_at=120,
        recorded_at=120,
        policy_revision="policy:character-runtime:v1",
        source_revision_vector=GraphRevisionVector(source_revision=1),
        scope_digest="scope:actor-private",
        provenance=GraphProvenance(
            source_kind="runtime_outcome",
            source_ref="harness:replay",
            causation_id="harness:replay",
            correlation_id="harness:replay",
            producer_system="behavior_turn_harness",
            actor_id="char_b",
        ),
        transaction_id="tx:harness:replay",
        idempotency_key="harness:replay",
        stages=(BehaviorTurnStageRecord(stage="context", payload={}),),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    project_root = repo_root()
    log_dir = verification_dir(project_root)
    pytest_log = log_dir / "behavior-turn-runtime-pytest.log"
    pytest_result = run_command(
        [resolve_python_exe(args.python_exe), "-m", "pytest", "-q", *TEST_FILES],
        project_root,
        pytest_log,
    )

    with tempfile.TemporaryDirectory(dir=log_dir) as temporary_directory:
        graph = SQLiteHeavenlyGraphAdapter(
            Path(temporary_directory) / "behavior-turn.sqlite3"
        )
        recorder = BehaviorTurnRecorder(graph)
        runtime = CharacterAgentRuntime(
            behavior_turn_recorder=recorder,
            behavior_turn_scope_resolver=_scope,
        )
        runtime.ingest_character_perceived_event(_event(100, "obj_letter is visible"))
        runtime.record_settlement_result(
            actor_id="char_b",
            producer_ts=101,
            payload={
                "result_id": "result:accepted",
                "result_type": "object_state_result",
                "settlement_status": "accepted",
                "change_summary": "obj_letter inspected",
                "causation_id": "cause:accepted",
                "correlation_id": "corr:accepted",
                "policy_revision": "policy:character-runtime:v1",
                "authority_event_ref": "authority:event:accepted",
                "authority_owner_ref": "esm:world",
            },
        )
        runtime.ingest_character_perceived_event(
            _event(110, "obj_letter is now out of reach")
        )
        runtime.record_settlement_result(
            actor_id="char_b",
            producer_ts=111,
            payload={
                "result_id": "result:rejected",
                "result_type": "constraint_state_result",
                "settlement_status": "rejected",
                "constraint_summary": "too far from obj_letter",
                "causation_id": "cause:rejected",
                "correlation_id": "corr:rejected",
                "policy_revision": "policy:character-runtime:v1",
            },
        )
        accepted = graph.query_semantic(
            BehaviorTurnQuery(
                context=_context("char_b", 111),
                scope=_scope("char_b"),
                correlation_id="corr:accepted",
                actor_id="char_b",
            )
        )
        rejected = graph.query_semantic(
            BehaviorTurnQuery(
                context=_context("char_b", 111),
                scope=_scope("char_b"),
                correlation_id="corr:rejected",
                actor_id="char_b",
            )
        )
        accepted_nodes = _stage_nodes(accepted)
        rejected_nodes = _stage_nodes(rejected)
        unauthorized = graph.query_semantic(
            BehaviorTurnQuery(
                context=_context("char_a", 111),
                scope=_scope("char_b"),
                correlation_id="corr:accepted",
                actor_id="char_b",
            )
        )
        recorder.record(_replay_request())
        replayed = recorder.record(_replay_request())
        trace = {
            "accepted_stages": [node.attributes["stage"] for node in accepted_nodes],
            "rejected_stages": [node.attributes["stage"] for node in rejected_nodes],
            "accepted_settlement_outcome": _settlement_outcome(accepted_nodes),
            "rejected_settlement_outcome": _settlement_outcome(rejected_nodes),
            "other_actor_visible_node_count": len(unauthorized.nodes),
            "replayed": replayed.replayed,
        }
        graph.close()

    trace_path = log_dir / "behavior-turn-runtime-trace.json"
    write_json(trace_path, trace)
    evidence = [str(trace_path)]
    results = [
        _result(
            "focused_pytest_pass",
            "Behavior turn focused pytest suite passes",
            pytest_result.returncode == 0,
            [str(pytest_log)],
        ),
        _result(
            "complete_stage_chain",
            "Accepted and rejected character turns retain all eight stages",
            trace["accepted_stages"] == STAGES and trace["rejected_stages"] == STAGES,
            evidence,
        ),
        _result(
            "accepted_committed",
            "Authority-linked settlement fixture is projected as committed",
            trace["accepted_settlement_outcome"] == "committed",
            evidence,
        ),
        _result(
            "rejected_retained",
            "Rejected Authority result remains an auditable settlement stage",
            trace["rejected_settlement_outcome"] == "rejected",
            evidence,
        ),
        _result(
            "actor_private_scope",
            "Another actor scope cannot read char_b behavior turns",
            trace["other_actor_visible_node_count"] == 0,
            evidence,
        ),
        _result(
            "idempotent_replay",
            "Identical recorder requests replay without duplicate writes",
            trace["replayed"] is True,
            evidence,
        ),
    ]
    overall = all(result["status"] == "proved" for result in results)
    report = {
        "overall_behavior_turn_runtime_passed": overall,
        "scope": "character behavior-turn vertical only; no restart, Siming, six-domain Authority, online LLM, or Godot claim",
        "results": results,
        "artifacts": {"pytest_log": str(pytest_log), "trace": str(trace_path)},
    }
    json_path = log_dir / "behavior-turn-runtime-report.json"
    markdown_path = log_dir / "behavior-turn-runtime-report.md"
    write_json(json_path, report)
    write_markdown(
        markdown_path,
        "Behavior Turn Runtime Verification Report",
        report,
        "overall_behavior_turn_runtime_passed",
    )
    print(f"behavior_turn_runtime_report_json={json_path}")
    print(f"behavior_turn_runtime_report_md={markdown_path}")
    print(f"overall_behavior_turn_runtime_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
