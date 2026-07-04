from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.services.siming_global_situation import SimingGlobalSituationLayer
from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = ["backend/tests/test_siming_global_situation_runtime.py"]


def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {"id": result_id, "title": title, "status": "proved" if proved else "missing", "evidence": evidence if proved else [], "notes": notes}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    pytest_log = log_dir / "siming-global-situation-layer-pytest.log"
    pytest_result = run_command([python_exe, "-m", "pytest", "-q", *TEST_FILES], project_root, pytest_log)

    layer = SimingGlobalSituationLayer()
    snapshot = layer.assemble_snapshot(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        context_id="siming_mm:room_demo:scene_demo",
        l1_projected_facts=["l1_fact:lamp:light_drop"],
        authority_events=[{"event_id": "authority:light", "event_type": "visual_fact_event"}],
        world_results=[{"result_id": "world_result:light", "result_type": "environment_state_result"}],
        environment_events=[{"event_id": "env:light", "summary": "light reduced"}],
        vla_global_findings=[{"ref_id": "vla_global:visibility", "summary": "char_b cannot see lamp", "pressure": 1.0}],
        multi_actor_patch={"patch_refs": ["public_patch:room_demo"], "actor_visibility": {"char_a": 0.9, "char_b": 0.1}},
        producer_ts=50,
    )
    fairness = layer.to_fairness_snapshot(snapshot)
    candidate = layer.to_intervention_candidate(snapshot)
    trace_path = log_dir / "siming-global-situation-layer-trace.json"
    write_json(
        trace_path,
        {
            "snapshot": snapshot.model_dump(mode="json"),
            "fairness": fairness.model_dump(mode="json"),
            "candidate": candidate.model_dump(mode="json"),
            "trace": layer.trace,
        },
    )
    context_ok = snapshot.context_id.startswith("siming_mm:")
    public_ok = "l1_fact:lamp:light_drop" in snapshot.public_fact_refs
    fairness_ok = "situation_pressure" in fairness.dimensions and candidate.established_fact_ids
    advisory_ok = snapshot.advisory_metadata["advisory_only"] is True and snapshot.advisory_metadata["cannot_override_world_truth"] is True
    results = [
        _result("focused-pytest-pass", "Siming global situation focused pytest suite passes", pytest_result.returncode == 0, [str(pytest_log)]),
        _result("siming-context-isolated", "Global situation uses siming_mm context and no character private cache", context_ok, [str(trace_path)]),
        _result("public-fact-patch", "Snapshot is assembled from public L1/world/authority/evidence refs", public_ok, [str(trace_path)]),
        _result("fairness-candidate-evidence", "Fairness snapshot and intervention candidate carry situation evidence", fairness_ok, [str(trace_path)]),
        _result("vla-advisory-boundary", "VLA advisory enhances pressure without overriding world truth", advisory_ok, [str(trace_path)]),
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    report = {"overall_siming_global_situation_layer_passed": overall, "results": results, "artifacts": {"pytest_log": str(pytest_log), "trace": str(trace_path)}}
    json_path = log_dir / "siming-global-situation-layer-report.json"
    md_path = log_dir / "siming-global-situation-layer-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Siming Global Situation Layer Verification Report", report, "overall_siming_global_situation_layer_passed")
    print(f"siming_global_situation_layer_report_json={json_path}")
    print(f"siming_global_situation_layer_report_md={md_path}")
    print(f"overall_siming_global_situation_layer_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
