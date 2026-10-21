from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    test = root / "backend/tests/test_task5_private_affect_estimate.py"
    log = Path(tempfile.gettempdir()) / "paralls-task5-private-affect.log"
    result = run_command([resolve_python_exe(None), "-m", "pytest", "-q", str(test)], root, log, timeout_seconds=600)
    passed = result.returncode == 0
    log.unlink(missing_ok=True)
    report = {
        "profile": "infra-task5-private-affect",
        "overall_passed": passed,
        "run_id": f"infra-task5-private-affect-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "revision": evidence_revision(root),
        "focused_tests": [str(test.relative_to(root)).replace("\\", "/")],
        "scope": "actor-private fear/morale estimate admission with explicit provenance and privacy",
        "limitations": [
            "Does not prove canonical Soul/identity, objective relationship facts, Threat, or Target owners.",
            "Does not convert private estimates into world truth or GameplayEventStore facts.",
        ],
        "exit_code": result.returncode,
    }
    path = verification_dir(root) / "infra-task5-private-affect-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "Task5 Private Affect Report", {
        "results": [{"id": "task5-private-affect", "status": "proved" if passed else "missing", "title": "actor-private fear and morale estimate boundary"}],
        "overall_passed": passed,
    }, "overall_passed")
    print(f"task5_private_affect_report_json={path}")
    print(f"overall_task5_private_affect_passed={passed}")
    return 0 if passed else 1


if __name__ == "__main__":
    from run_context import run_scope
    with run_scope(Path(__file__).resolve().parents[2]):
        raise SystemExit(main())
