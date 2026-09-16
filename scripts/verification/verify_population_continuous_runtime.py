from __future__ import annotations

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

from verify_phase3_common import root, write_report


def test_evidence(name: str, files: tuple[str, ...]) -> dict[str, object]:
    directory = root() / ".harness" / "verification"
    directory.mkdir(parents=True, exist_ok=True)
    xml_path = directory / f"{name}-tests.xml"
    # 每次重新生成证据，不能读取上次失败前遗留的 JUnit 报告。
    xml_path.unlink(missing_ok=True)
    command = [sys.executable, "-m", "pytest", "-q", "-o", "junit_family=legacy",
               f"--junitxml={xml_path}", *(f"backend/tests/{file}" for file in files)]
    env = dict(os.environ, PARALLS_HEAVENLY_GRAPH_PATH=":memory:", PYTHONPATH=str(root() / "backend"))
    result = subprocess.run(command, cwd=root(), env=env, capture_output=True, text=True)
    log_path = directory / f"{name}-tests.log"
    log_path.write_text(result.stdout + result.stderr, encoding="utf-8")
    cases = ET.parse(xml_path).findall(".//testcase") if xml_path.exists() else []
    passed = result.returncode == 0 and bool(cases) and all(
        case.find("failure") is None and case.find("error") is None and case.find("skipped") is None
        for case in cases
    )
    return {
        "overall_passed": passed,
        "command": command,
        "exit_code": result.returncode,
        "test_count": len(cases),
        "test_cases": [f"{case.get('classname')}.{case.get('name')}" for case in cases],
        "observations": {prop.get("name"): prop.get("value") for case in cases
                         for prop in case.findall("./properties/property")},
        "test_log": str(log_path.relative_to(root())),
        "junit_report": str(xml_path.relative_to(root())),
    }


def backend_report(name: str, report: dict[str, object]) -> int:
    report.update({
        "verification_scope": "backend-only",
        "implementation_status": "written_and_backend_verified" if report["overall_passed"] else "backend_verification_failed",
        "godot_status": "godot_unverified",
        "full_sgc_runtime_proof": False,
    })
    code = write_report(name, report)
    markdown = root() / ".harness" / "verification" / f"{name}-report.md"
    with markdown.open("a", encoding="utf-8") as file:
        file.write(f"\n- scope: \x60backend-only\x60\n- implementation: \x60{report['implementation_status']}\x60\n- Godot: \x60godot_unverified\x60\n")
    return code


def main() -> int:
    name = "population-continuous-runtime"
    report = test_evidence(name, (
        "test_population_continuous_runtime.py", "test_population_runtime_driver.py",
        "test_population_runtime_lifecycle.py", "test_population_continuity.py",
        "test_character_population_continuity.py", "test_siming_population_production_boundaries.py",
        "test_siming_population_authorized_cadence_publication.py",
        "test_character_agent_memory_consistency.py", "test_character_memory_consistency_flow.py",
        "test_character_memory_correction.py",
        "test_population_roster.py", "test_population_roster_import.py",
        "test_population_durable_cadence_recovery.py", "test_population_due_index.py",
        "test_population_hot_state.py", "test_population_parallel_determinism.py",
    ))
    observation = report["observations"].get("continuous_runtime_evidence")
    evidence = json.loads(observation) if observation else {}
    report["continuous_runtime"] = evidence
    configured_rosters = [json.loads(value) for key, value in report["observations"].items()
                          if key.startswith("configured_roster_")]
    report["configured_rosters"] = configured_rosters
    report["overall_passed"] = bool(report["overall_passed"] and evidence.get("window_count", 0) >= 2
                                    and evidence.get("actor_ids") and len(configured_rosters) >= 2
                                    and all(row["actor_ids"] and not row["default_fill"]
                                            and set(row["actor_ids"]) == set(row["b0_actor_ids"])
                                            and not row["character_core_actor_ids"]
                                            for row in configured_rosters))
    report["restart_scope"] = "durable_gameplay_store_reopen_and_pending_outbox_redelivery; hot_state_rebuilt_from_committed_cadence"
    return backend_report(name, report)


if __name__ == "__main__":
    raise SystemExit(main())
