from __future__ import annotations

import argparse
import json

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = [
    "backend/tests/test_gameplay_event_store_contract.py",
    "backend/tests/test_gameplay_shared_contracts.py",
    "backend/tests/test_gameplay_active_revision.py",
    "backend/tests/test_gameplay_shared_replay_and_permission.py",
]


def _result(check_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {"id": check_id, "title": title, "status": "proved" if proved else "missing", "evidence": evidence if proved else [], "notes": notes}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    pytest_log = log_dir / "gameplay-foundation-contract-pytest.log"
    pytest_result = run_command([python_exe, "-m", "pytest", "-q", *TEST_FILES], project_root, pytest_log)
    passed = pytest_result.returncode == 0
    sections = [
        _result("G1-contract-closure", "Shared identity, semantic, settlement, permission and revision contracts", passed, [str(pytest_log)]),
        _result("G2-replay-and-package", "Replay evidence and package lifecycle are deterministic", passed, [str(pytest_log)]),
        _result("G3-zero-write-failure", "Reservation and authorization failures remain fail-closed", passed, [str(pytest_log)]),
    ]
    results = sections
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_gameplay_foundation_contract_passed": overall,
        "results": results,
        "artifacts": {
            "pytest_log": str(pytest_log),
            "ndjson": str(log_dir / "gameplay-foundation-contract-evidence.ndjson"),
        },
    }
    json_path = log_dir / "gameplay-foundation-contract-report.json"
    md_path = log_dir / "gameplay-foundation-contract-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Gameplay Foundation Contract Verification Report", report, "overall_gameplay_foundation_contract_passed")
    (log_dir / "gameplay-foundation-contract-evidence.ndjson").write_text(
        "".join(json.dumps(entry, sort_keys=True) + "\n" for entry in results), encoding="utf-8"
    )
    print(f"gameplay_foundation_contract_report_json={json_path}")
    print(f"gameplay_foundation_contract_report_md={md_path}")
    print(f"overall_gameplay_foundation_contract_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
