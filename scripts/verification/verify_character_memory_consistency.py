from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = (
    "backend/tests/test_character_memory_consistency.py",
    "backend/tests/test_character_memory_consistency_flow.py",
    "backend/tests/test_character_memory_correction.py",
    "backend/tests/test_character_memory_recall_policy.py",
    "backend/tests/test_read_content_debug_privacy.py",
)
FLOW_CASE = "test_world_change_does_not_teach_actor_until_successful_recheck"
FLOW_PROPERTIES = ("world_state_after", "known_state_after", "received_source_ref", "verification_request")
CORRECTION_CASE = "test_evidence_survives_restart_and_correction_is_idempotent"
REQUIRED_CASES = {FLOW_CASE, CORRECTION_CASE,
                  "test_read_content_stays_in_actor_memory_and_out_of_debug_websocket",
                  "test_strong_actor_defers_when_even_focused_evidence_exceeds_budget"}


def _result(result_id: str, title: str, proved: bool, artifact: Path) -> dict[str, object]:
    return {"id": result_id, "title": title, "status": "proved" if proved else "missing",
            "notes": str(artifact)}


def main_verify(python_exe: str | None) -> int:
    root = repo_root()
    output = verification_dir(root)
    log = output / "character-memory-consistency-pytest.log"
    junit = output / "character-memory-consistency-pytest.xml"
    result = run_command(
        [resolve_python_exe(python_exe), "-m", "pytest", "-q", *TEST_FILES,
         "-o", "junit_family=legacy", f"--junitxml={junit}"],
        root, log,
    )
    tests: list[dict[str, object]] = []
    flow_evidence: dict[str, str] = {}
    correction_evidence: dict[str, str] = {}
    if junit.exists():
        tree = ET.parse(junit)
        for case in tree.findall(".//testcase"):
            name = str(case.get("name", ""))
            tests.append({"name": name, "passed": not any(case.find(tag) is not None for tag in ("failure", "error", "skipped"))})
            if name == FLOW_CASE and tests[-1]["passed"]:
                flow_evidence = {str(item.get("name")): str(item.get("value", ""))
                                 for item in case.findall("./properties/property")}
            if name == CORRECTION_CASE and tests[-1]["passed"]:
                correction_evidence = {str(item.get("name")): str(item.get("value", ""))
                                       for item in case.findall("./properties/property")}
    trace = {key: flow_evidence.get(key, "") for key in FLOW_PROPERTIES}
    receipt = json.loads(correction_evidence.get("correction_receipt", "{}"))
    correction_proved = (receipt.get("status") == "applied"
                         and receipt.get("after_revision", 0) == receipt.get("before_revision", 0) + 1
                         and bool(receipt.get("source_refs"))
                         and bool(correction_evidence.get("correction_source_event_id"))
                         and correction_evidence.get("correction_restart_idempotent") == "true")
    trace_path = output / "character-memory-consistency-trace.json"
    write_json(trace_path, {"flow_test": FLOW_CASE, "evidence": trace,
                            "correction_test": CORRECTION_CASE, "correction_receipt": receipt,
                            "correction_source_event_id": correction_evidence.get("correction_source_event_id", ""),
                            "restart_idempotent": correction_evidence.get("correction_restart_idempotent") == "true",
                            "test_cases": tests})
    flow_proved = (result.returncode == 0 and all(trace.values())
                   and trace["world_state_after"] == trace["known_state_after"])
    results = [
        _result("focused_tests_pass", "Memory, flow, correction, and recall tests pass",
                result.returncode == 0 and REQUIRED_CASES <= {item["name"] for item in tests if item["passed"]}
                and all(item["passed"] for item in tests), log),
        _result("actor_recheck_evidence", "World settlement and actor recheck agree after received evidence",
                flow_proved, trace_path),
        _result("siming_correction_receipt", "Applied correction has source, revision advance, and restart idempotency",
                result.returncode == 0 and correction_proved, trace_path),
    ]
    overall = all(item["status"] == "proved" for item in results)
    report = {
        "overall_character_memory_consistency_passed": overall,
        "scope": "backend-only actor memory and explicit Siming correction; no Godot or online-model proof",
        "results": results,
        "artifacts": {"pytest_log": str(log), "junit_xml": str(junit), "trace": str(trace_path)},
    }
    json_path = output / "character-memory-consistency-report.json"
    markdown_path = output / "character-memory-consistency-report.md"
    write_json(json_path, report)
    write_markdown(markdown_path, "Character Memory Consistency Verification Report", report,
                   "overall_character_memory_consistency_passed")
    print(f"character_memory_consistency_report_json={json_path}")
    print(f"overall_character_memory_consistency_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    from pathlib import Path
    from run_context import run_scope

    with run_scope(Path(__file__).resolve().parents[2]):
        parser = argparse.ArgumentParser()
        parser.add_argument("--python-exe", default=None)
        args = parser.parse_args()
        raise SystemExit(main_verify(args.python_exe))
