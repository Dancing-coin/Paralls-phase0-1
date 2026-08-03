from __future__ import annotations

import argparse

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    root = repo_root()
    log = verification_dir(root) / "gameplay-ownership-authority-pytest.log"
    result = run_command([resolve_python_exe(args.python_exe), "-m", "pytest", "-q", "backend/tests/test_ownership_runtime.py", "backend/tests/test_credential_runtime.py"], root, log)
    report = {
        "overall_gameplay_ownership_authority_passed": result.returncode == 0,
        "scope": "backend proof for event-derived exclusive full-title grant/transfer, credential issue/revoke/supersede with immutable issuance-holder attestation and current inventory validation, and read-only presentation requiring item presence plus right-holder identity; it excludes custody writes, accounts, offers, debt, contracts, privacy views, replay checkpoints, and Godot delivery",
        "results": [{"id": "ownership-title-credential-and-presentation-core", "title": "Full title is independently transferable while credential issuance records attestation and presentation requires current item presence without changing title", "status": "proved" if result.returncode == 0 else "missing", "evidence": [str(log)] if result.returncode == 0 else [], "notes": f"exit_code={result.returncode}"}],
        "artifacts": {"pytest_log": str(log)},
    }
    write_json(verification_dir(root) / "gameplay-ownership-authority-report.json", report)
    write_markdown(verification_dir(root) / "gameplay-ownership-authority-report.md", "Gameplay Ownership Authority Verification Report", report, "overall_gameplay_ownership_authority_passed")
    print(f"overall_gameplay_ownership_authority_passed={report['overall_gameplay_ownership_authority_passed']}")
    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
