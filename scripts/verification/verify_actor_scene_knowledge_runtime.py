from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.character_agent.reasoning.active_perception import ActivePerceptionPlanner
from app.character_agent.reasoning.actor_scene_knowledge import ActorSceneKnowledgeEntry, ActorSceneKnowledgeStore
from app.world_runtime.intelligence_upgrade import CanonicalPerceptBundle
from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = [
    "backend/tests/test_actor_scene_knowledge_runtime.py",
    "backend/tests/test_actor_active_perception_loop.py",
]


def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {"id": result_id, "title": title, "status": "proved" if proved else "missing", "evidence": evidence if proved else [], "notes": notes}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    pytest_log = log_dir / "actor-scene-knowledge-lifecycle-pytest.log"
    pytest_result = run_command([python_exe, "-m", "pytest", "-q", *TEST_FILES], project_root, pytest_log)

    store = ActorSceneKnowledgeStore()
    bundle = CanonicalPerceptBundle(
        bundle_id="bundle:char_a:ask:verify",
        consumer_kind="character",
        subject_id="char_a",
        query_id="pqf:char_a:42",
        percept_context_id="character_mm:char_a",
        local_spatial_state={"scene_id": "scene_demo", "session_id": "session_verify"},
        target_state={"target_ref": "obj_box", "summary": "box visible", "confidence": 0.8},
        structured_fact_refs=["l1_fact:obj_box:reachable"],
        uncertainty={
            "vla_advisory": {
                "subject_ref": "l1_fact:obj_box:reachable",
                "summary": "VLA advisory contests reachability",
                "confidence": 0.55,
                "source_refs": ["vla_result:verify"],
            }
        },
    )
    updates = store.apply_canonical_percept_bundle(bundle, session_id="session_verify", producer_ts=42)
    stale_update = store.mark_stale(updates[0].entry.entry_id, producer_ts=43)
    planner = ActivePerceptionPlanner()
    requests = planner.requests_for_actor(
        store,
        actor_id="char_a",
        session_id="session_verify",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
    )
    frame = requests[0].to_pqf(started_at=43, ended_at=44)
    other_actor_entries = store.entries_for_actor("char_b", session_id="session_verify", scene_id="scene_demo")
    trace_path = log_dir / "actor-scene-knowledge-lifecycle-trace.json"
    trace = {
        "updates": [update.model_dump(mode="json") for update in updates],
        "stale_update": stale_update.model_dump(mode="json"),
        "active_perception_request": requests[0].model_dump(mode="json"),
        "pqf": frame.model_dump(mode="json"),
        "store_trace": store.trace,
    }
    write_json(trace_path, trace)

    conflict_ok = any(update.operation == "conflict" for update in updates)
    isolation_ok = other_actor_entries == []
    active_ok = frame.query_id.startswith("pqf:") and bool(frame.spatial_inputs) and requests[0].must_use_provider_chain
    revision_ok = any(update.entry.revisions for update in updates) and stale_update.operation == "stale"
    results = [
        _result("focused-pytest-pass", "ASK lifecycle focused pytest suite passes", pytest_result.returncode == 0, [str(pytest_log)]),
        _result("actor-store-isolation", "ASK store is actor/session/scene isolated", isolation_ok, [str(trace_path)]),
        _result("revision-freshness-expiry", "ASK records revisions and freshness transitions", revision_ok, [str(trace_path)]),
        _result("conflict-boundary", "VLA advisory records conflict without overwriting L1 truth", conflict_ok, [str(trace_path)]),
        _result("active-perception-pqf-provider-chain", "Active perception request returns to PQF/provider refs", active_ok, [str(trace_path)]),
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_actor_scene_knowledge_lifecycle_passed": overall,
        "results": results,
        "artifacts": {"pytest_log": str(pytest_log), "trace": str(trace_path)},
    }
    json_path = log_dir / "actor-scene-knowledge-lifecycle-report.json"
    md_path = log_dir / "actor-scene-knowledge-lifecycle-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Actor Scene Knowledge Lifecycle Verification Report", report, "overall_actor_scene_knowledge_lifecycle_passed")
    print(f"actor_scene_knowledge_lifecycle_report_json={json_path}")
    print(f"actor_scene_knowledge_lifecycle_report_md={md_path}")
    print(f"overall_actor_scene_knowledge_lifecycle_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
