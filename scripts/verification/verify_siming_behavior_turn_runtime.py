from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.models.siming_event import SimingInput
from app.models.siming_heavenly_graph import BehaviorTurnQuery, GraphReaderContext, HeavenlyGraphScope
from app.services.behavior_turn_recorder import BehaviorTurnRecorder
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.siming_runtime import SimingRuntime
from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = ["backend/tests/test_siming_heavenly_runtime_tick.py"]
STAGES = ["context", "interpretation", "goal", "intent", "execution", "settlement", "evaluation", "policy"]


def _event() -> AuthorityEvent:
    return AuthorityEvent(
        event_id="siming:harness:1", event_type="visual_fact_event", producer_ts=100,
        room_id="room:main", scene_id="scene:main", zone_id="zone:main",
        source=AuthorityEventSource(layer="L1", system="visual_fact"),
        routing=AuthorityEventRouting(audience_mode="broadcast", routing_mode="event_type", target_ids=[]),
        priority="p2", durability="replayable", causation_id="cause:harness:1", correlation_id="corr:harness:1",
        payload={"established_fact_id": "fact:harness:1"},
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    root = repo_root()
    log_dir = verification_dir(root)
    pytest_log = log_dir / "siming-behavior-turn-runtime-pytest.log"
    pytest_result = run_command([resolve_python_exe(args.python_exe), "-m", "pytest", "-q", *TEST_FILES], root, pytest_log)
    graph = InMemoryHeavenlyGraphAdapter()
    scope = HeavenlyGraphScope(world_id="world:demo", session_id="session:demo", story_branch_id="branch:main")
    event = _event()
    SimingRuntime(
        behavior_turn_recorder=BehaviorTurnRecorder(graph),
        behavior_turn_scope_resolver=lambda _event: scope,
    ).tick([SimingInput(input_type="visual_fact_event", source_event=event)])
    query = graph.query_semantic(
        BehaviorTurnQuery(
            context=GraphReaderContext(reader_principal="reader:siming", allowed_visibility_scopes=("siming_internal",), world_id="world:demo", session_id="session:demo", story_branch_id="branch:main", valid_at=100, recorded_at=100, policy_revision="policy:siming-runtime:v1"),
            scope=scope, correlation_id=event.correlation_id,
        )
    )
    stages = [node.attributes["stage"] for node in query.nodes if node.attributes.get("entity_kind") == "stage"]
    trace = {"stages": stages}
    trace_path = log_dir / "siming-behavior-turn-runtime-trace.json"
    write_json(trace_path, trace)
    results = [
        {"id": "focused_pytest_pass", "title": "Siming tick behavior tests pass", "status": "proved" if pytest_result.returncode == 0 else "missing", "evidence": [str(pytest_log)] if pytest_result.returncode == 0 else []},
        {"id": "siming_eight_stage_chain", "title": "SimingRuntime.tick records all eight stages", "status": "proved" if stages == STAGES else "missing", "evidence": [str(trace_path)] if stages == STAGES else []},
    ]
    overall = all(item["status"] == "proved" for item in results)
    report = {"overall_siming_behavior_turn_runtime_passed": overall, "scope": "Siming tick behavior-turn only; no online LLM or Godot claim", "results": results, "artifacts": {"pytest_log": str(pytest_log), "trace": str(trace_path)}}
    json_path = log_dir / "siming-behavior-turn-runtime-report.json"
    markdown_path = log_dir / "siming-behavior-turn-runtime-report.md"
    write_json(json_path, report)
    write_markdown(markdown_path, "Siming Behavior Turn Runtime Verification Report", report, "overall_siming_behavior_turn_runtime_passed")
    print(f"siming_behavior_turn_runtime_report_json={json_path}")
    print(f"overall_siming_behavior_turn_runtime_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
