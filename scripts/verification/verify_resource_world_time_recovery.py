from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    tests = [
        root / "backend/tests/test_resource_recovery.py",
        root / "backend/tests/test_resource_modifier_admission.py",
        root / "backend/tests/test_resource_body_runtime.py",
        root / "backend/tests/test_population_activation_presence_service.py",
        root / "backend/tests/test_resource_recovery_application.py",
        root / "backend/tests/test_resource_template_admission.py",
        root / "backend/tests/test_resource_v2_locks.py",
        root / "backend/tests/test_resource_migration_control.py",
        root / "backend/tests/test_resource_v2_migration.py",
        root / "backend/tests/test_resource_materialization.py",
        root / "backend/tests/test_resource_conversion_service.py",
        root / "backend/tests/test_resource_conversion_application.py",
    ]
    log = Path(tempfile.gettempdir()) / "paralls-resource-world-time-recovery.log"
    result = run_command(
        [resolve_python_exe(None), "-m", "pytest", "-q", *map(str, tests)],
        root,
        log,
        timeout_seconds=1500,
    )
    passed = result.returncode == 0
    log.unlink(missing_ok=True)
    report = {
        "profile": "infra-resource-world-time-recovery",
        "overall_passed": passed,
        "run_id": f"infra-resource-world-time-recovery-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "revision": evidence_revision(root),
        "focused_tests": [str(item.relative_to(root)).replace("\\", "/") for item in tests],
        "scope": "Population confirmed boundary -> resource recovery owner -> shared GameplayEventStore; includes materialization, Equipment modifier bridge, typed Resource conversion application ingress, and Durable replay",
        "limitations": [
            "Does not prove the missing external world-admin identity issuer.",
            "Does not prove D06 centralized migration or the remaining Status/Effect/Equipment acceptance set.",
            "Conversion tests inject capability approval; they do not prove a production capability issuer or business demand source.",
        ],
        "exit_code": result.returncode,
        "pytest_output": ((result.stdout or "") + "\n" + (result.stderr or ""))[-6000:],
    }
    path = verification_dir(root) / "infra-resource-world-time-recovery-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "Resource World-Time Recovery Report", {
        "results": [{"id": "resource-world-time-recovery", "status": "proved" if passed else "missing", "title": "confirmed Population boundary, owner recovery, and Durable replay"}],
        "overall_passed": passed,
    }, "overall_passed")
    print(f"infra_resource_world_time_recovery_report_json={path}")
    print(f"overall_infra_resource_world_time_recovery_passed={passed}")
    return 0 if passed else 1


if __name__ == "__main__":
    from run_context import run_scope

    with run_scope(Path(__file__).resolve().parents[2]):
        raise SystemExit(main())
