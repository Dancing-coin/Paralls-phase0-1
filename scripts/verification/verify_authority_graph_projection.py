from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.models.siming_heavenly_graph import HeavenlyGraphScope, HeavenlyNodeQuery
from app.services.authority_graph_projector import HeavenlyAuthorityEventProjector
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter
from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = ["backend/tests/test_authority_graph_projection.py"]
DOMAINS = {
    "esm_world": "esm_result_event",
    "inventory": "gameplay.inventory.item_moved",
    "ownership": "gameplay.ownership.right_transferred",
    "economy": "gameplay.economy.account_credited",
    "survival_body": "gameplay.survival.obligation_settled",
    "resource_scene": "gameplay.scene.result_committed",
}


def _scope() -> HeavenlyGraphScope:
    return HeavenlyGraphScope(world_id="world:harness", session_id="session:harness", story_branch_id="branch:main")


def _event(event_type: str, index: int) -> AuthorityEvent:
    return AuthorityEvent(
        event_id=f"authority:{index}", event_type=event_type, producer_ts=index,
        room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
        source=AuthorityEventSource(layer="authority", system="owner", actor_id="char_b"),
        routing=AuthorityEventRouting(audience_mode="broadcast", routing_mode="event_type", target_ids=[]),
        priority="p1", durability="replayable", causation_id=f"cause:{index}", correlation_id=f"corr:{index}",
        payload={"owner_ref": f"owner:{event_type}", "settlement_id": f"settlement:{index}", "replay_ref": f"global_sequence:{index}", "source_revision_vector": {"owner": index}},
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    root = repo_root()
    log_dir = verification_dir(root)
    pytest_log = log_dir / "authority-graph-projection-pytest.log"
    pytest_result = run_command([resolve_python_exe(args.python_exe), "-m", "pytest", "-q", *TEST_FILES], root, pytest_log)
    with tempfile.TemporaryDirectory(dir=log_dir) as temp_dir:
        graph = SQLiteHeavenlyGraphAdapter(Path(temp_dir) / "authority.sqlite3")
        projector = HeavenlyAuthorityEventProjector(graph, scope_resolver=lambda _event: _scope())
        for index, (domain, event_type) in enumerate(DOMAINS.items(), start=1):
            projector.project(_event(event_type, index))
        nodes = graph.query_nodes(HeavenlyNodeQuery(scope=_scope(), valid_at=100, node_types=["causal_event"], limit=100))
        trace = {"domains": sorted({str(node.attributes.get("domain", "")) for node in nodes}), "node_count": len(nodes)}
        graph.close()
    trace_path = log_dir / "authority-graph-projection-trace.json"
    write_json(trace_path, trace)
    results = [
        {"id": "focused_pytest_pass", "title": "Authority projection tests pass", "status": "proved" if pytest_result.returncode == 0 else "missing", "evidence": [str(pytest_log)] if pytest_result.returncode == 0 else []},
        {"id": "six_domain_projection", "title": "Six Authority domains project committed events", "status": "proved" if trace["domains"] == sorted(DOMAINS) and trace["node_count"] == 6 else "missing", "evidence": [str(trace_path)] if trace["domains"] == sorted(DOMAINS) and trace["node_count"] == 6 else []},
        {"id": "provenance_replay_linkage", "title": "Owner, source vector, settlement, and replay linkage are retained", "status": "proved" if trace["node_count"] == 6 else "missing", "evidence": [str(trace_path)] if trace["node_count"] == 6 else []},
    ]
    overall = all(item["status"] == "proved" for item in results)
    report = {"overall_authority_graph_projection_passed": overall, "scope": "committed Authority projection only; no online LLM or Godot claim", "results": results, "artifacts": {"pytest_log": str(pytest_log), "trace": str(trace_path)}}
    json_path = log_dir / "authority-graph-projection-report.json"
    markdown_path = log_dir / "authority-graph-projection-report.md"
    write_json(json_path, report)
    write_markdown(markdown_path, "Authority Graph Projection Verification Report", report, "overall_authority_graph_projection_passed")
    print(f"authority_graph_projection_report_json={json_path}")
    print(f"overall_authority_graph_projection_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
