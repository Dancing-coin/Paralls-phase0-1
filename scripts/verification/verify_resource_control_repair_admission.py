from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    tests = [
        root / "backend/tests/test_resource_migration_control.py",
        root / "backend/tests/test_facility_repair_admission.py",
    ]
    log = Path(tempfile.gettempdir()) / "paralls-resource-control-repair-admission.log"
    result = run_command([resolve_python_exe(None), "-m", "pytest", "-q", *map(str, tests)], root, log, timeout_seconds=600)
    passed = result.returncode == 0
    log.unlink(missing_ok=True)
    report = {
        "profile": "infra-resource-control-repair-admission",
        "overall_passed": passed,
        "run_id": f"infra-resource-control-repair-admission-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "revision": evidence_revision(root),
        "focused_tests": [str(item.relative_to(root)).replace("\\", "/") for item in tests],
        "scope": "D17 durable pause/drain control owner plus fail-closed facility repair admission",
        "limitations": [
            "Does not prove a world-admin identity/grant issuer.",
            "Does not emit a facility repair event because authoritative grant, incarnation, membership, material and completion sources are absent.",
            "Does not prove centralized resource migration or global Task6 fault matrix.",
        ],
        "exit_code": result.returncode,
    }
    path = verification_dir(root) / "infra-resource-control-repair-admission-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "Resource Control and Repair Admission Report", {
        "results": [{"id": "resource-control-repair-admission", "status": "proved" if passed else "missing", "title": "D17 control and fail-closed repair admission"}],
        "overall_passed": passed,
    }, "overall_passed")
    print(f"infra_resource_control_repair_admission_report_json={path}")
    print(f"overall_infra_resource_control_repair_admission_passed={passed}")
    return 0 if passed else 1


if __name__ == "__main__":
    from run_context import run_scope

    with run_scope(Path(__file__).resolve().parents[2]):
        raise SystemExit(main())
